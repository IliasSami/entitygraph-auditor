"""Google Gemini adapter (generativelanguage.googleapis.com) — optional BYOK (FR-21).

Calls ``POST /v1beta/models/{model}:generateContent`` with
``generationConfig.responseMimeType="application/json"`` and a converted
``responseSchema``. The API key travels in the ``x-goog-api-key`` header —
never in the URL, so it cannot leak into request logs.

Conversion limits of :func:`convert_json_schema` (Gemini accepts only an
OpenAPI-ish subset of JSON Schema):

* local ``$ref``s into ``$defs``/``definitions`` are inlined, then ``$defs``,
  ``$schema`` and ``$id`` are dropped (unresolvable refs are dropped, not
  guessed; ref cycles terminate safely);
* ``type`` unions like ``["string", "null"]`` become ``type`` + ``nullable``;
* ``anyOf``/``oneOf`` are supported ONLY as a null-union of two members;
  other ``anyOf``/``oneOf``/``allOf``/``not`` constraints are dropped;
* unsupported keywords are dropped rather than forwarded: ``pattern``,
  ``patternProperties``, ``additionalProperties``, ``unevaluated*``,
  ``propertyNames``, ``if``/``then``/``else``, ``dependentSchemas``,
  ``dependencies``, ``contentEncoding``, ``default``, ``examples``,
  ``$comment`` and draft-only keywords;
* supported/kept keywords: ``type``, ``format``, ``description``, ``title``,
  ``nullable``, ``enum``, ``items``, ``properties``, ``required``,
  ``minimum``, ``maximum``, ``minItems``, ``maxItems`` (``required`` is
  narrowed to the properties that survive);
* a container object without ``type`` but with ``properties``/``items`` gets
  ``type`` ``object``/``array``.

Because constraints can be dropped, callers must treat the converted schema
as best-effort enforcement — the application still validates the returned
object against the ORIGINAL schema (:func:`ega_providers.base.parse_structured`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from time import perf_counter
from typing import Any

import httpx

from ega_providers.base import (
    DEFAULT_TIMEOUT_S,
    GenerationSettings,
    HealthStatus,
    ModelProvider,
    ProviderCapabilities,
    fetch_json,
    parse_structured,
    response_json,
    split_system,
)
from ega_providers.errors import (
    MalformedOutputError,
    ProviderAuthError,
    ProviderError,
)

#: Keywords forwarded to Gemini's ``responseSchema``.
_ALLOWED_KEYWORDS: tuple[str, ...] = (
    "type",
    "format",
    "description",
    "title",
    "nullable",
    "minimum",
    "maximum",
    "minItems",
    "maxItems",
)

#: ``finishReason`` values that mean the answer was cut short.
_TRUNCATING_FINISH_REASONS: frozenset[str] = frozenset({"MAX_TOKENS"})

#: ``finishReason`` values that mean the answer was withheld.
_BLOCKING_FINISH_REASONS: frozenset[str] = frozenset(
    {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY"}
)


def _resolve_refs(node: Any, root: dict[str, Any], seen: frozenset[str]) -> Any:
    """Inline local ``$ref``s into ``$defs``/``definitions`` (cycle-safe)."""
    if isinstance(node, list):
        return [_resolve_refs(item, root, seen) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str):
        prefix = "#/$defs/"
        alt_prefix = "#/definitions/"
        if ref.startswith(prefix):
            name = ref[len(prefix) :]
        elif ref.startswith(alt_prefix):
            name = ref[len(alt_prefix) :]
        else:
            return {}  # unsupported/external ref — constraint dropped
        defs = root.get("$defs") or root.get("definitions") or {}
        if name in seen or not isinstance(defs, dict) or name not in defs:
            return {}  # cycle or unknown target — constraint dropped
        return _resolve_refs(defs[name], root, seen | {name})
    return {key: _resolve_refs(value, root, seen) for key, value in node.items()}


def _convert_node(node: Any) -> Any:
    """Recursively convert one resolved schema node to the Gemini subset."""
    if isinstance(node, list):
        return [_convert_node(item) for item in node]
    if not isinstance(node, dict):
        return node
    node = dict(node)
    nullable = bool(node.get("nullable", False))

    # Null-union combinators only; anything else is dropped (documented).
    for keyword in ("anyOf", "oneOf"):
        if keyword not in node:
            continue
        members = node.pop(keyword)
        if isinstance(members, list) and len(members) == 2:
            non_null = [
                member
                for member in members
                if not (isinstance(member, dict) and member.get("type") == "null")
            ]
            if len(non_null) == 1 and isinstance(non_null[0], dict):
                node = {**non_null[0], **node}
                nullable = True

    declared = node.get("type")
    if isinstance(declared, list):
        types = [entry for entry in declared if isinstance(entry, str)]
        if "null" in types:
            non_null_types = [entry for entry in types if entry != "null"]
            nullable = True
            if len(non_null_types) == 1:
                node["type"] = non_null_types[0]
            else:
                node.pop("type", None)
        elif types:
            node["type"] = types[0]
        else:
            node.pop("type", None)

    out: dict[str, Any] = {
        key: node[key] for key in _ALLOWED_KEYWORDS if key in node
    }
    if isinstance(node.get("properties"), dict):
        out["properties"] = {
            key: _convert_node(value) for key, value in node["properties"].items()
        }
    if "items" in node:
        out["items"] = _convert_node(node["items"])
    if isinstance(node.get("enum"), list):
        out["enum"] = list(node["enum"])
    if isinstance(node.get("required"), list):
        required = [str(key) for key in node["required"]]
        properties = out.get("properties")
        if isinstance(properties, dict) and properties:
            required = [key for key in required if key in properties]
        if required:
            out["required"] = required
    if "type" not in out:
        if "properties" in out:
            out["type"] = "object"
        elif "items" in out:
            out["type"] = "array"
    if nullable:
        out["nullable"] = True
    return out


def convert_json_schema(schema: Mapping[str, Any] | dict[str, Any]) -> dict[str, Any]:
    """Convert a JSON Schema subset into a Gemini ``responseSchema`` dict.

    See the module docstring for the exact conversion limits. The input is
    never mutated; dropped constraints are documented rather than guessed.
    """
    root = dict(schema)
    resolved = _resolve_refs(root, root, frozenset())
    converted = _convert_node(resolved)
    if not isinstance(converted, dict):  # pragma: no cover - schemas are objects
        return {}
    return converted


class GeminiProvider(ModelProvider):
    """Adapter for ``POST /v1beta/models/{model}:generateContent``."""

    name: str = "gemini"

    #: Loopback-free default; data always leaves the device for this provider.
    DEFAULT_BASE_URL: str = "https://generativelanguage.googleapis.com"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "",
        extra_headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
        default_timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        super().__init__(client=client, default_timeout_s=default_timeout_s)
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model
        #: Optional BYOK credential — never appears in repr/logs (redacted).
        self.api_key: str | None = api_key
        #: Non-secret extra headers (values are redacted from any error output).
        self.extra_headers: dict[str, str] = dict(extra_headers or {})

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ProviderAuthError(
                "No API key configured for the gemini provider "
                "(set api_key_env or provide a key).",
                provider=self.name,
            )
        headers = {"x-goog-api-key": self.api_key}
        headers.update(self.extra_headers)
        return headers

    def _secrets(self) -> tuple[str, ...]:
        values = list(self.extra_headers.values())
        if self.api_key:
            values.append(self.api_key)
        return tuple(values)

    @staticmethod
    def _model_path(model: str) -> str:
        """Normalise ``models/x`` resource names for the URL path (documented)."""
        return model.removeprefix("models/")

    def _url(self, settings: GenerationSettings) -> str:
        model_id = self._model_path(self.require_model(settings))
        return f"{self.base_url}/v1beta/models/{model_id}:generateContent"

    def _payload(
        self,
        settings: GenerationSettings,
        messages: list[dict[str, Any]],
        *,
        response_schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        system_text, rest = split_system(messages)
        contents = [
            {
                "role": "model" if message["role"] in ("assistant", "model") else "user",
                "parts": [{"text": message["content"]}],
            }
            for message in rest
        ]
        generation_config: dict[str, Any] = {
            "temperature": settings.temperature,
            "maxOutputTokens": settings.max_tokens,
        }
        if settings.top_p is not None:
            generation_config["topP"] = settings.top_p
        if response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = response_schema
        generation_config.update(dict(settings.extra))
        payload: dict[str, Any] = {"contents": contents}
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        payload["generationConfig"] = generation_config
        return payload

    @staticmethod
    def _candidate_text(data: dict[str, Any]) -> tuple[str, str]:
        """Return ``(concatenated_text, finish_reason)`` from the first candidate."""
        candidates = data.get("candidates") or []
        if not candidates or not isinstance(candidates[0], dict):
            return "", ""
        candidate = candidates[0]
        content = candidate.get("content") if isinstance(candidate.get("content"), dict) else {}
        parts = content.get("parts") or []
        text = "".join(
            str(part.get("text", ""))
            for part in parts
            if isinstance(part, dict) and "text" in part
        )
        return text, str(candidate.get("finishReason") or "")

    # ------------------------------------------------------------------ #
    # operations
    # ------------------------------------------------------------------ #

    async def generate_structured(
        self,
        *,
        schema: dict[str, Any],
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> dict[str, Any]:
        """``generateContent`` with ``responseSchema`` → parsed dict."""
        response = await fetch_json(
            self.http(),
            self._url(settings),
            provider=self.name,
            payload=self._payload(settings, messages, response_schema=convert_json_schema(schema)),
            headers=self._headers(),
            timeout_s=settings.timeout_s,
            secrets=self._secrets(),
        )
        data = response_json(response, provider=self.name, secrets=self._secrets())
        return self._parse(data, schema)

    async def generate_text(
        self,
        *,
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> str:
        """``generateContent`` without a response schema."""
        response = await fetch_json(
            self.http(),
            self._url(settings),
            provider=self.name,
            payload=self._payload(settings, messages, response_schema=None),
            headers=self._headers(),
            timeout_s=settings.timeout_s,
            secrets=self._secrets(),
        )
        data = response_json(response, provider=self.name, secrets=self._secrets())
        text, finish = self._candidate_text(data)
        if finish in _TRUNCATING_FINISH_REASONS:
            raise MalformedOutputError(
                "Gemini output was truncated at maxOutputTokens (finishReason=MAX_TOKENS).",
                provider=self.name,
                snippet=text,
            )
        if not text.strip():
            raise MalformedOutputError(
                "Gemini returned no text content.",
                provider=self.name,
                snippet=json.dumps(data, ensure_ascii=False),
            )
        return text

    def _parse(self, data: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        """Extract and validate the structured answer from a Gemini response."""
        text, finish = self._candidate_text(data)
        if finish in _TRUNCATING_FINISH_REASONS:
            raise MalformedOutputError(
                "Gemini output was truncated at maxOutputTokens before completing "
                "the JSON answer.",
                provider=self.name,
                snippet=text,
            )
        if finish in _BLOCKING_FINISH_REASONS:
            raise ProviderError(
                f"Gemini withheld the answer (finishReason={finish}).",
                provider=self.name,
                retryable=False,
                snippet=text,
            )
        if not data.get("candidates"):
            feedback = data.get("promptFeedback") if isinstance(data, dict) else None
            block = feedback.get("blockReason") if isinstance(feedback, dict) else None
            suffix = f" (blocked: {block})" if block else ""
            raise ProviderError(
                f"Gemini returned no candidates{suffix}.",
                provider=self.name,
                retryable=False,
                snippet=json.dumps(data, ensure_ascii=False),
            )
        if not text.strip():
            raise MalformedOutputError(
                "Gemini candidate contained no text parts.",
                provider=self.name,
                snippet=json.dumps(data, ensure_ascii=False),
            )
        return parse_structured(text, schema)

    async def health_check(self) -> HealthStatus:
        """Probe ``GET /v1beta/models`` for reachability and model availability."""
        started = perf_counter()

        def _elapsed() -> float:
            return (perf_counter() - started) * 1000

        model_id = self.model.removeprefix("models/")
        try:
            response = await fetch_json(
                self.http(),
                f"{self.base_url}/v1beta/models",
                provider=self.name,
                method="GET",
                headers=self._headers(),
                timeout_s=self.default_timeout_s,
                secrets=self._secrets(),
            )
            data = response_json(response, provider=self.name, secrets=self._secrets())
        except ProviderError as exc:
            return HealthStatus(
                ok=False, latency_ms=_elapsed(), detail=exc.safe_message, model_id=model_id
            )
        entries = data.get("models") if isinstance(data, dict) else None
        names = [
            str(entry.get("name") or "").removeprefix("models/")
            for entry in (entries or [])
            if isinstance(entry, dict)
        ]
        names = [name for name in names if name]
        if not model_id:
            return HealthStatus(
                ok=False,
                latency_ms=_elapsed(),
                detail=(
                    f"Gemini API reachable ({len(names)} model(s) listed) "
                    "but no model is configured."
                ),
                model_id="",
            )
        if model_id in names:
            return HealthStatus(
                ok=True,
                latency_ms=_elapsed(),
                detail=f"Gemini API reachable; model '{model_id}' is available.",
                model_id=model_id,
            )
        available = ", ".join(names[:5]) or "none listed"
        return HealthStatus(
            ok=False,
            latency_ms=_elapsed(),
            detail=(
                f"Gemini API reachable but model '{model_id}' was not listed. "
                f"Available: {available}."
            ),
            model_id=model_id,
        )

    def capabilities(self) -> ProviderCapabilities:
        """Capability/privacy metadata for the provider UI (FR-21)."""
        return ProviderCapabilities(
            provider=self.name,
            model_id=self.model,
            structured_output=True,
            tool_calls=True,
            context_window=None,
            sends_data_off_device=True,
            notes=[
                "Structured output via responseMimeType + responseSchema (JSON-Schema "
                "subset; see convert_json_schema for limits).",
                "Always sends the request text to generativelanguage.googleapis.com "
                "(off-device); the key is sent as a header, never in the URL.",
                "Context window depends on the model — see Google AI docs.",
                "Embeddings are not implemented in this adapter.",
            ],
        )
