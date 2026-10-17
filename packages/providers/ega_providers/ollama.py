"""Ollama local-server adapter (PRD §13.3, FR-22 offline/local mode).

Talks to ``POST /api/chat`` with ``format`` set to the requested JSON schema
(Ollama accepts a schema object in ``format``); servers that reject schema
objects fall back to ``format: "json"`` (recorded in the result ``notes``).
``GET /api/tags`` powers ``list_models()`` and ``health_check()``.

No model ID is ever substituted: ``settings.model`` is sent verbatim.
Truncated output (``done_reason == "length"`` or ``done == false``) raises a
retryable :class:`MalformedOutputError` — never silently produced content.
"""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any

import httpx

from ega_providers.base import (
    DEFAULT_TIMEOUT_S,
    GenerationSettings,
    HealthStatus,
    ModelProvider,
    ProviderCapabilities,
    StructuredResult,
    fetch_json,
    is_local_url,
    parse_structured,
    raise_for_provider_status,
    response_json,
)
from ega_providers.errors import MalformedOutputError, ProviderError


class OllamaProvider(ModelProvider):
    """Adapter for a self-hosted Ollama server (default ``http://localhost:11434``)."""

    name: str = "ollama"

    #: Loopback default used when no ``base_url`` is configured (FR-22).
    DEFAULT_BASE_URL: str = "http://localhost:11434"

    def __init__(
        self,
        config: Any = None,
        *,
        base_url: str | None = None,
        model: str = "",
        extra_headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
        default_timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        if config is not None:
            base_url = getattr(config, "base_url", None) or base_url
            model = getattr(config, "model_name", None) or getattr(config, "model", "") or model
        super().__init__(client=client, default_timeout_s=default_timeout_s)
        self.config = config
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model
        #: Non-secret extra headers (values are redacted from any error output).
        self.extra_headers: dict[str, str] = dict(extra_headers or {})


    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _headers(self) -> dict[str, str]:
        return dict(self.extra_headers)

    def _secrets(self) -> tuple[str, ...]:
        return tuple(self.extra_headers.values())

    def _payload(
        self,
        settings: GenerationSettings,
        messages: list[dict[str, Any]],
        format_value: Any,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {
            "temperature": settings.temperature,
            "num_predict": settings.max_tokens,
        }
        if settings.top_p is not None:
            options["top_p"] = settings.top_p
        payload: dict[str, Any] = {
            "model": self.require_model(settings),
            "messages": [dict(message) for message in messages],
            "stream": False,
            "options": options,
        }
        if format_value is not None:
            payload["format"] = format_value
        return payload

    @staticmethod
    def _message_text(data: dict[str, Any]) -> tuple[str, bool]:
        """Return ``(content, truncated)`` from an ``/api/chat`` response."""
        message = data.get("message") or {}
        content = message.get("content", "") if isinstance(message, dict) else ""
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        done_reason = str(data.get("done_reason") or "").lower()
        truncated = done_reason == "length" or data.get("done") is False
        return content, truncated

    @staticmethod
    def _model_matches(configured: str, available: str) -> bool:
        """True when ``configured`` selects the installed ``available`` model.

        Exact IDs always match; an untagged ID (``llama3.2``) matches any tag
        of the same base name (``llama3.2:latest``), while two different
        explicit tags do not match.
        """
        if configured == available:
            return True
        config_base, _, config_tag = configured.partition(":")
        avail_base, _, avail_tag = available.partition(":")
        if config_base != avail_base:
            return False
        return not config_tag or not avail_tag

    # ------------------------------------------------------------------ #
    # operations
    # ------------------------------------------------------------------ #

    async def generate_structured_result(
        self,
        *,
        schema: dict[str, Any],
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> StructuredResult:
        """Structured chat call with schema → ``json`` fallback notes."""
        notes: list[str] = []
        started = perf_counter()
        url = f"{self.base_url}/api/chat"
        response = await fetch_json(
            self.http(),
            url,
            provider=self.name,
            payload=self._payload(settings, messages, schema),
            headers=self._headers(),
            timeout_s=settings.timeout_s,
            secrets=self._secrets(),
            require_success=False,
        )
        if response.status_code == 400:
            notes.append(
                "JSON-schema `format` rejected by the server (HTTP 400); "
                "fell back to format='json'."
            )
            response = await fetch_json(
                self.http(),
                url,
                provider=self.name,
                payload=self._payload(settings, messages, "json"),
                headers=self._headers(),
                timeout_s=settings.timeout_s,
                secrets=self._secrets(),
                require_success=False,
            )
        raise_for_provider_status(response, provider=self.name, secrets=self._secrets())
        data = response_json(response, provider=self.name, secrets=self._secrets())
        content, truncated = self._message_text(data)
        if truncated:
            raise MalformedOutputError(
                "Ollama output was truncated before completion "
                "(done_reason='length'); retry with a higher max_tokens.",
                provider=self.name,
                snippet=content,
            )
        if not content.strip():
            raise MalformedOutputError(
                "Ollama returned an empty message.",
                provider=self.name,
                snippet=json.dumps(data, ensure_ascii=False),
            )
        parsed = parse_structured(content, schema)
        return StructuredResult(
            provider=self.name,
            model_id=settings.model,
            data=parsed,
            notes=notes,
            latency_ms=(perf_counter() - started) * 1000,
        )

    async def generate_structured(
        self,
        *,
        schema: dict[str, Any],
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> dict[str, Any]:
        """Parse a schema-constrained ``/api/chat`` answer into a dict."""
        result = await self.generate_structured_result(
            schema=schema, messages=messages, settings=settings
        )
        return result.data

    async def generate_text(
        self,
        *,
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> str:
        """Plain ``/api/chat`` completion (no ``format`` constraint)."""
        url = f"{self.base_url}/api/chat"
        response = await fetch_json(
            self.http(),
            url,
            provider=self.name,
            payload=self._payload(settings, messages, None),
            headers=self._headers(),
            timeout_s=settings.timeout_s,
            secrets=self._secrets(),
        )
        data = response_json(response, provider=self.name, secrets=self._secrets())
        content, truncated = self._message_text(data)
        if truncated:
            raise MalformedOutputError(
                "Ollama output was truncated before completion (done_reason='length').",
                provider=self.name,
                snippet=content,
            )
        if not content.strip():
            raise MalformedOutputError(
                "Ollama returned an empty message.",
                provider=self.name,
                snippet=json.dumps(data, ensure_ascii=False),
            )
        return content

    async def list_models(self) -> list[str]:
        """Return installed model names from ``GET /api/tags`` (sorted)."""
        response = await fetch_json(
            self.http(),
            f"{self.base_url}/api/tags",
            provider=self.name,
            method="GET",
            timeout_s=self.default_timeout_s,
            secrets=self._secrets(),
        )
        data = response_json(response, provider=self.name, secrets=self._secrets())
        raw_models = data.get("models") if isinstance(data, dict) else None
        names = [
            str(entry.get("name") or entry.get("model") or "")
            for entry in (raw_models or [])
            if isinstance(entry, dict)
        ]
        return sorted(name for name in names if name)

    async def health_check(self) -> HealthStatus:
        """Reachability + model-availability probe (FR-22 health test)."""
        started = perf_counter()
        model_id = self.model

        def _elapsed() -> float:
            return (perf_counter() - started) * 1000

        try:
            names = await self.list_models()
        except ProviderError as exc:
            return HealthStatus(
                ok=False, latency_ms=_elapsed(), detail=exc.safe_message, model_id=model_id
            )
        latency_ms = _elapsed()
        if not names:
            return HealthStatus(
                ok=False,
                latency_ms=latency_ms,
                detail="Ollama is reachable but no models are installed.",
                model_id=model_id,
            )
        if not model_id:
            return HealthStatus(
                ok=False,
                latency_ms=latency_ms,
                detail=f"Ollama is reachable ({len(names)} model(s)) but no model is configured.",
                model_id="",
            )
        if any(self._model_matches(model_id, name) for name in names):
            return HealthStatus(
                ok=True,
                latency_ms=latency_ms,
                detail=(
                    f"Ollama is reachable; model '{model_id}' is installed "
                    f"({len(names)} model(s) available)."
                ),
                model_id=model_id,
            )
        available = ", ".join(names[:5])
        return HealthStatus(
            ok=False,
            latency_ms=latency_ms,
            detail=f"Ollama is reachable but model '{model_id}' is not installed. Available: {available}.",
            model_id=model_id,
        )

    def capabilities(self) -> ProviderCapabilities:
        """Local-first capability metadata (FR-21)."""
        return ProviderCapabilities(
            provider=self.name,
            model_id=self.model,
            structured_output=True,
            tool_calls=True,
            context_window=None,
            sends_data_off_device=not is_local_url(self.base_url),
            notes=[
                "Requests go only to the configured base_url (local by default).",
                "Structured output via /api/chat `format` (JSON schema), with format='json' fallback.",
                "Tool calling is supported by Ollama; this adapter enforces JSON instead of issuing tools.",
                "Context window depends on the loaded model — check `ollama show <model>`.",
            ],
        )
