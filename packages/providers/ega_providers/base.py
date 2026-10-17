"""Model provider abstractions and shared structured-output plumbing (PRD §13.3).

This module defines the small, provider-neutral interface every adapter in
``ega_providers`` implements, plus the shared pieces all adapters reuse:

* :class:`GenerationSettings` — per-call parameters (model, temperature, …).
* :class:`ProviderCapabilities` / :class:`HealthStatus` / :class:`StructuredResult`.
* :class:`ModelProvider` — the ABC (``generate_structured``, ``generate_text``,
  ``embed``, ``health_check``, ``capabilities``).
* :func:`parse_structured` / :func:`validate_required` — tolerant JSON
  extraction plus a minimal dependency-free schema check.
* :func:`fetch_json` / :func:`response_json` — HTTP helpers that enforce the
  redirect cap (5) and the 4 MB response-size cap and map transport failures
  onto the redacting exception hierarchy in :mod:`ega_providers.errors`.

Hard rules (PRD FR-21/§13.3): adapters never silently change model IDs,
never fabricate content on failure (a failed call raises), and never send
data to a provider the user did not select.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import time as _time
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field

from ega_providers.errors import (
    CapabilityError,
    MalformedOutputError,
    ProviderAuthError,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    truncate_snippet,
)

#: Maximum accepted response size (bytes) — PRD FR-21 provider hardening.
MAX_RESPONSE_BYTES: int = 4 * 1024 * 1024

#: Maximum redirects followed for any provider request.
MAX_REDIRECTS: int = 5

#: Fallback timeout when a caller does not specify one.
DEFAULT_TIMEOUT_S: float = 60.0

#: Attribute names that must never appear (unmasked) in a provider repr.
_CREDENTIAL_NAME: re.Pattern[str] = re.compile(
    r"key|secret|token|password|credential|authorization", re.IGNORECASE
)

#: Redirect statuses understood by :func:`fetch_json`.
_REDIRECT_STATUSES: frozenset[int] = frozenset({301, 302, 303, 307, 308})

#: Credential-bearing headers stripped when a redirect crosses origins.
_CREDENTIAL_HEADERS: frozenset[str] = frozenset(
    {"authorization", "proxy-authorization", "x-api-key", "x-goog-api-key"}
)


class GenerationSettings(BaseModel):
    """Per-call generation parameters.

    ``model`` is always taken verbatim from the caller: adapters never
    substitute or "fix up" model IDs (PRD FR-21).
    """

    model_config = ConfigDict(extra="forbid")

    model: str
    temperature: float = 0.0
    max_tokens: int = 2048
    timeout_s: float = Field(default=60.0, gt=0)
    top_p: float | None = None
    json_schema_name: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class ProviderCapabilities:
    """Static description of one provider/model pair for the UI (FR-21)."""

    provider: str
    model_id: str
    structured_output: bool
    tool_calls: bool
    context_window: int | None
    sends_data_off_device: bool
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HealthStatus:
    """Result of ``ModelProvider.health_check()`` (FR-22 local-mode test)."""

    ok: bool
    latency_ms: float
    detail: str
    model_id: str


@dataclass(frozen=True)
class StructuredResult:
    """Wrapper for ``generate_structured`` output plus adapter telemetry.

    ``notes`` records any structured-output fallback the adapter used
    (e.g. ``json_schema`` → ``json_object`` → plain prompting) so the UI can
    show that schema enforcement was weaker than requested.
    """

    provider: str
    model_id: str
    data: dict[str, Any]
    notes: list[str] = field(default_factory=list)
    latency_ms: float = 0.0


class ModelProvider(ABC):
    """Provider adapter contract (PRD §13.3).

    Subclasses implement three async operations plus metadata:

    * :meth:`generate_structured` — produce a ``dict`` for the caller to
      validate against the JSON schema; raises :class:`ProviderError`
      (never fabricates content) on any failure.
    * :meth:`generate_text` — plain text generation.
    * :meth:`health_check` — reachability/model probe (:class:`HealthStatus`).
    * :meth:`capabilities` — static :class:`ProviderCapabilities` for the UI.

    :meth:`embed` raises :class:`CapabilityError` by default; adapters that
    can embed override it.

    Adapters whose structured path has a fallback (e.g. ``json_schema`` →
    ``json_object``) additionally override
    :meth:`generate_structured_result` so fallback ``notes`` are visible.

    Instance ``__repr__`` is redacted: any attribute whose name looks like a
    credential (``api_key``, ``token``, …) never appears in logs or errors,
    and HTTP headers are never included in exception messages.
    """

    #: Adapter identifier (``ProviderType`` value).
    name: str = "provider"
    #: Configured default model ID — never silently changed by the adapter.
    model: str = ""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        default_timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        """Create the adapter.

        Args:
            client: Optional pre-built ``httpx.AsyncClient`` (tests inject one
                with a ``MockTransport``). When omitted, the adapter creates
                and owns its client with redirects enabled and capped at
                :data:`MAX_REDIRECTS`.
            default_timeout_s: Fallback timeout for calls without settings
                (used by :meth:`health_check`).
        """
        self._client = client
        self._owns_client = client is None
        self.default_timeout_s = float(default_timeout_s)

    # -- core operations -------------------------------------------------- #

    @abstractmethod
    async def generate_structured(
        self,
        *,
        schema: dict[str, Any],
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> dict[str, Any]:
        """Return model output parsed against ``schema``.

        Raises:
            ProviderError: on timeout, auth, availability, or malformed
                output. Never returns fabricated placeholder content.
        """

    async def generate_structured_result(
        self,
        *,
        schema: dict[str, Any],
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> StructuredResult:
        """Like :meth:`generate_structured` but with fallback/latency notes."""
        data = await self.generate_structured(
            schema=schema, messages=messages, settings=settings
        )
        return StructuredResult(provider=self.name, model_id=settings.model, data=data)

    @abstractmethod
    async def generate_text(
        self,
        *,
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> str:
        """Return raw model text. Raises :class:`ProviderError` on failure."""

    async def embed(
        self, texts: list[str], settings: GenerationSettings
    ) -> list[list[float]]:
        """Embed ``texts``. Adapters without embedding support raise."""
        raise CapabilityError(
            f"Provider '{self.name}' does not expose embeddings in this adapter.",
            provider=self.name,
        )

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Probe reachability and model availability without side effects."""

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Static capability/privacy metadata for the provider UI (FR-21)."""

    # -- plumbing --------------------------------------------------------- #

    def http(self) -> httpx.AsyncClient:
        """Return the HTTP client, creating an owned one on first use."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                follow_redirects=False,  # redirects are handled explicitly
                max_redirects=MAX_REDIRECTS,
                timeout=DEFAULT_TIMEOUT_S,
            )
            self._owns_client = True
        return self._client

    async def aclose(self) -> None:
        """Close the owned HTTP client (injected clients are left alone)."""
        if self._client is not None and self._owns_client:
            client, self._client = self._client, None
            await client.aclose()

    def require_model(self, settings: GenerationSettings) -> str:
        """Return ``settings.model`` or raise when no model ID was given.

        The model ID is used verbatim — an adapter never substitutes a
        different model (PRD FR-21).
        """
        if not settings.model:
            raise ProviderError(
                f"No model ID configured for provider '{self.name}'.",
                provider=self.name,
                retryable=False,
            )
        return settings.model

    def __repr__(self) -> str:
        """Redacted representation: credentials never appear in logs."""
        parts: list[str] = []
        for key, value in vars(self).items():
            if key.startswith("_"):
                continue
            if _CREDENTIAL_NAME.search(key):
                parts.append(f"{key}=***REDACTED***" if value else f"{key}=None")
            elif key == "extra_headers" and isinstance(value, dict):
                parts.append(f"{key}={sorted(value)!r}")
            else:
                parts.append(f"{key}={value!r}")
        return f"{type(self).__name__}({', '.join(parts)})"

    __str__ = __repr__

    # -- legacy bridge ---------------------------------------------------- #

    def call(self, request: Any) -> Any:
        """Synchronous bridge for the pre-async ``ModelCallRequest`` contract.

        Kept so existing importers of the old ``BaseModelProvider.call()``
        interface keep working; new code should await
        :meth:`generate_structured` / :meth:`generate_text` instead.
        """
        from ega_schemas.providers import ModelCallRequest, ModelCallResponse

        if not isinstance(request, ModelCallRequest):  # pragma: no cover - defensive
            raise ProviderError(
                "call() expects an ega_schemas ModelCallRequest.",
                provider=self.name,
                retryable=False,
            )
        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ]
        settings = GenerationSettings(
            model=self.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        started = _time.perf_counter()

        async def _run() -> tuple[str, dict[str, Any] | None]:
            try:
                if request.json_mode:
                    data = await self.generate_structured(
                        schema={"type": "object"},
                        messages=messages,
                        settings=settings,
                    )
                    return json.dumps(data, ensure_ascii=False), data
                text = await self.generate_text(messages=messages, settings=settings)
                return text, None
            finally:
                await self.aclose()

        def _run_blocking() -> tuple[str, dict[str, Any] | None]:
            # Runs in a worker thread with no active loop, so ``asyncio.run``
            # is always safe here regardless of the caller's loop state.
            return asyncio.run(_run())

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        else:
            loop = asyncio.get_running_loop()

        if loop is not None and loop.is_running():
            # Called from synchronous agent code *inside* a running loop
            # (workflow ``run_audit``): offload the coroutine to a worker
            # thread so it can drive its own loop without blocking the caller.
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="ega-provider-call") as pool:
                raw_text, parsed = pool.submit(_run_blocking).result()
        else:
            raw_text, parsed = _run_blocking()
        latency_ms = int((_time.perf_counter() - started) * 1000)
        return ModelCallResponse(
            raw_text=raw_text,
            parsed_json=parsed,
            latency_ms=latency_ms,
            input_tokens=max(1, len(request.user_prompt) // 4),
            output_tokens=max(1, len(raw_text) // 4),
            model_name=settings.model,
            provider=self.name,
        )


def require_model(settings: GenerationSettings, provider: str) -> str:
    """Module-level variant of :meth:`ModelProvider.require_model`."""
    if not settings.model:
        raise ProviderError(
            f"No model ID configured for provider '{provider}'.",
            provider=provider,
            retryable=False,
        )
    return settings.model


# --------------------------------------------------------------------------- #
# URL locality (privacy indicator, FR-21)
# --------------------------------------------------------------------------- #


def is_local_url(url: str | None) -> bool:
    """Return ``True`` when ``url`` points at loopback/private/link-local space.

    Conservative by design: a hostname that is not an IP literal (except
    ``localhost``) is treated as NOT local, i.e. data would leave the machine.
    DNS is never performed here (no network side effects).
    """
    if not url:
        return False
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return False
    if not host:
        return False
    host = host.lower().strip("[]")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(ip.is_loopback or ip.is_private or ip.is_link_local)


# --------------------------------------------------------------------------- #
# Message helpers
# --------------------------------------------------------------------------- #


def split_system(messages: Sequence[Mapping[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Concatenate ``system`` messages and return ``(system_text, rest)``.

    Used by adapters whose APIs take the system prompt separately
    (Anthropic ``system=`` , Gemini ``systemInstruction``).
    """
    system_parts: list[str] = []
    rest: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role", "user"))
        content = message.get("content", "")
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        if role == "system":
            system_parts.append(text)
        else:
            rest.append({"role": role, "content": text})
    return "\n\n".join(system_parts), rest


# --------------------------------------------------------------------------- #
# HTTP plumbing shared by adapters
# --------------------------------------------------------------------------- #


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    provider: str,
    method: str = "POST",
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    secrets: Iterable[str] = (),
    require_success: bool = True,
) -> httpx.Response:
    """Perform one HTTP request and return the loaded :class:`httpx.Response`.

    Enforces the shared hardening rules: redirects are followed explicitly
    and capped at :data:`MAX_REDIRECTS` (credential headers are dropped when
    a redirect crosses origins), the body must fit in
    :data:`MAX_RESPONSE_BYTES`, the timeout comes from the call's
    :class:`GenerationSettings`, and transport failures map onto
    :class:`ProviderTimeout` / :class:`ProviderUnavailable`.

    When ``require_success`` is true (default), 4xx/5xx statuses raise the
    mapped :class:`ProviderError`; set it to ``False`` to inspect an error
    response yourself (used by the ``response_format`` fallback chain).
    """
    secret_tuple = tuple(s for s in secrets if s)
    original_origin = _origin(url)
    target = url
    request_method = method.upper()
    payload_dict = dict(payload or {})
    request_headers = dict(headers or {})
    response: httpx.Response | None = None
    for hop in range(MAX_REDIRECTS + 1):
        try:
            response = await client.request(
                request_method,
                target,
                json=payload_dict if request_method not in ("GET", "HEAD") else None,
                headers=request_headers,
                timeout=timeout_s,
                follow_redirects=False,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(
                f"Request to {provider} timed out after {timeout_s:g}s.",
                provider=provider,
                secrets=secret_tuple,
            ) from exc
        except httpx.TooManyRedirects as exc:  # pragma: no cover - explicit loop below
            raise ProviderError(
                f"Request to {provider} exceeded the redirect limit of {MAX_REDIRECTS}.",
                provider=provider,
                retryable=False,
                secrets=secret_tuple,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(
                f"Could not reach {provider}: {type(exc).__name__}.",
                provider=provider,
                secrets=secret_tuple,
            ) from exc

        if response.status_code not in _REDIRECT_STATUSES:
            break
        location = response.headers.get("location")
        if not location:
            raise ProviderError(
                f"{provider} returned a redirect (HTTP {response.status_code}) "
                "without a Location header.",
                provider=provider,
                retryable=False,
                status_code=response.status_code,
                secrets=secret_tuple,
            )
        if hop == MAX_REDIRECTS:
            raise ProviderError(
                f"Request to {provider} exceeded the redirect limit of {MAX_REDIRECTS}.",
                provider=provider,
                retryable=False,
                status_code=response.status_code,
                secrets=secret_tuple,
            )
        target = urljoin(target, location)
        if _origin(target) != original_origin:
            for header in list(request_headers):
                if header.lower() in _CREDENTIAL_HEADERS:
                    del request_headers[header]
        if response.status_code in (301, 302, 303):
            request_method = "GET"
            payload_dict = {}

    if response is None:  # pragma: no cover - the loop always yields a response
        raise ProviderUnavailable(
            f"No response received from {provider}.",
            provider=provider,
            secrets=secret_tuple,
        )
    _enforce_size_limit(response, provider=provider, secrets=secret_tuple)
    if require_success:
        raise_for_provider_status(response, provider=provider, secrets=secret_tuple)
    return response


def _origin(url: str) -> str:
    """Lower-cased ``scheme://host:port`` origin of ``url`` (default ports normalized)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if port is None:
        port = 443 if scheme == "https" else 80
    return f"{scheme}://{host}:{port}"


def _enforce_size_limit(
    response: httpx.Response, *, provider: str, secrets: tuple[str, ...] = ()
) -> None:
    """Raise when the response body exceeds :data:`MAX_RESPONSE_BYTES`."""
    declared = response.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_RESPONSE_BYTES:
        raise ProviderError(
            f"{provider} response exceeds the {MAX_RESPONSE_BYTES // (1024 * 1024)} MB size cap.",
            provider=provider,
            retryable=False,
            status_code=response.status_code,
            secrets=secrets,
        )
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ProviderError(
            f"{provider} response exceeds the {MAX_RESPONSE_BYTES // (1024 * 1024)} MB size cap.",
            provider=provider,
            retryable=False,
            status_code=response.status_code,
            secrets=secrets,
        )


def raise_for_provider_status(
    response: httpx.Response, *, provider: str, secrets: Iterable[str] = ()
) -> None:
    """Map an HTTP error status onto the redacting exception hierarchy.

    The response *body* may be embedded as a truncated, redacted snippet.
    Request headers are never included (they may carry credentials).
    """
    if response.status_code < 400:
        return
    secret_tuple = tuple(s for s in secrets if s)
    snippet = truncate_snippet(response.text, secrets=secret_tuple)
    status = response.status_code
    if status in (401, 403):
        raise ProviderAuthError(
            f"{provider} rejected the credentials (HTTP {status}).",
            provider=provider,
            status_code=status,
            secrets=secret_tuple,
            snippet=snippet,
        )
    if status == 429:
        raise ProviderError(
            f"{provider} rate-limited the request (HTTP 429).",
            provider=provider,
            retryable=True,
            status_code=status,
            secrets=secret_tuple,
            snippet=snippet,
        )
    if status == 404:
        raise ProviderUnavailable(
            f"{provider} endpoint or model was not found (HTTP 404).",
            provider=provider,
            retryable=False,
            status_code=status,
            secrets=secret_tuple,
            snippet=snippet,
        )
    if status >= 500:
        raise ProviderUnavailable(
            f"{provider} server error (HTTP {status}).",
            provider=provider,
            status_code=status,
            secrets=secret_tuple,
            snippet=snippet,
        )
    raise ProviderError(
        f"{provider} rejected the request (HTTP {status}).",
        provider=provider,
        retryable=False,
        status_code=status,
        secrets=secret_tuple,
        snippet=snippet,
    )


def response_json(response: httpx.Response, *, provider: str, secrets: Iterable[str] = ()) -> Any:
    """Decode a JSON response body, raising a redacted error when invalid."""
    secret_tuple = tuple(s for s in secrets if s)
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise ProviderError(
            f"{provider} returned a non-JSON response.",
            provider=provider,
            retryable=False,
            status_code=response.status_code,
            secrets=secret_tuple,
            snippet=truncate_snippet(response.text, secrets=secret_tuple),
        ) from exc


# --------------------------------------------------------------------------- #
# Structured-output parsing and minimal schema validation (no new dependencies)
# --------------------------------------------------------------------------- #


def _strip_code_fences(text: str) -> str:
    """Remove one Markdown code fence (```json … ```) if present."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _first_balanced_json(text: str) -> str | None:
    """Return the first balanced ``{…}``/``[…]`` substring, honoring strings."""
    start = None
    opener = closer = ""
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if start is None:
            if char in "{[":
                start, opener = index, char
                closer = "}" if char == "{" else "]"
                depth = 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _malformed(raw: str, detail: str) -> MalformedOutputError:
    """Build a retryable :class:`MalformedOutputError` with a safe snippet."""
    return MalformedOutputError(
        f"{detail}",
        snippet=raw,
    )


def validate_required(obj: Any, schema: Mapping[str, Any]) -> None:
    """Recursively check required keys and primitive types against ``schema``.

    A deliberately small, dependency-free subset of JSON Schema:

    * ``type`` (string/number/integer/boolean/object/array/null, and unions
      like ``["string", "null"]``);
    * ``required`` for objects, recursing into ``properties``;
    * ``items`` for arrays.

    ``null`` values are always accepted at any position: PRD §22 mandates
    ``null`` (or ``not_assessed``) as the explicit "unavailable" answer, so
    presence of the key — not its value — is what ``required`` enforces.

    Raises:
        MalformedOutputError: on any missing required key or type mismatch.
    """
    declared_type = schema.get("type")
    if isinstance(obj, dict):
        if declared_type is not None and not _type_matches(obj, declared_type):
            raise _malformed(json.dumps(obj)[:200], "Output is not the required object type.")
        required = schema.get("required") or []
        for key in required:
            if key not in obj:
                raise _malformed(
                    json.dumps(sorted(obj.keys()))[:200],
                    f"Missing required key {key!r} in model output.",
                )
        properties = schema.get("properties") or {}
        for key, subschema in properties.items():
            if key in obj and isinstance(subschema, Mapping):
                validate_required(obj[key], subschema)
        for key in obj:
            if key not in properties and schema.get("additionalProperties") is False:
                raise _malformed(
                    json.dumps(sorted(obj.keys()))[:200],
                    f"Unexpected key {key!r} in model output.",
                )
        return
    if isinstance(obj, list):
        if declared_type is not None and not _type_matches(obj, declared_type):
            raise _malformed(json.dumps(obj)[:200], "Output is not the required array type.")
        items = schema.get("items")
        if isinstance(items, Mapping):
            for element in obj:
                validate_required(element, items)
        return
    if declared_type is not None and not _type_matches(obj, declared_type):
        raise _malformed(repr(obj)[:200], f"Output value has the wrong type (expected {declared_type!r}).")


def _type_matches(value: Any, declared: Any) -> bool:
    """Minimal JSON-Schema type check; ``None`` always matches (PRD §22)."""
    if value is None:
        return True
    types = declared if isinstance(declared, (list, tuple)) else [declared]
    for candidate in types:
        if candidate == "string" and isinstance(value, str):
            return True
        if candidate == "boolean" and isinstance(value, bool):
            return True
        if candidate == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if candidate == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if candidate == "object" and isinstance(value, dict):
            return True
        if candidate == "array" and isinstance(value, list):
            return True
        if candidate == "null" and value is None:
            return True
    return False


def parse_structured(raw: str, schema: Mapping[str, Any]) -> dict[str, Any]:
    """Extract a JSON object from model output and validate it against ``schema``.

    Tolerates Markdown fences and leading/trailing prose by scanning for the
    first balanced JSON object/array. Validation is the minimal, dependency-
    free :func:`validate_required` check (required keys + primitive types).

    Raises:
        MalformedOutputError: retryable, with a redacted snippet ≤ 200 chars,
            when the output is not parseable JSON, is not an object, or fails
            the schema check.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise _malformed(raw or "", "Model returned empty output.")
    text = _strip_code_fences(raw)
    obj: Any = None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        candidate = _first_balanced_json(text)
        if candidate is None:
            raise _malformed(raw, "Model output contains no complete JSON object.") from None
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            raise _malformed(raw, "Model output contains truncated or invalid JSON.") from None
    validate_required(obj, schema)
    return obj


BaseModelProvider = ModelProvider



