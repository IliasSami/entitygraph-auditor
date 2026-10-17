"""Anthropic Messages API adapter (api.anthropic.com) — optional BYOK (FR-21).

Structured output uses a single forced tool: the tool's ``input_schema`` is
the caller's JSON schema and ``tool_choice`` pins the model to that tool, so
the answer arrives as a ``tool_use`` block whose ``input`` is the result.
Headers: ``x-api-key`` + ``anthropic-version`` (the key is redacted from any
error output; headers are never included in exception messages).

Failures raise — a missing ``tool_use`` block or a response stopped at
``stop_reason='max_tokens'`` becomes a retryable
:class:`MalformedOutputError`, never fabricated content.
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
    response_json,
    split_system,
    validate_required,
)
from ega_providers.errors import (
    MalformedOutputError,
    ProviderAuthError,
    ProviderError,
)

#: Default Messages API version header.
ANTHROPIC_VERSION: str = "2023-06-01"


class AnthropicProvider(ModelProvider):
    """Adapter for ``POST /v1/messages`` with a forced structured-output tool."""

    name: str = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.anthropic.com",
        model: str = "",
        api_version: str = ANTHROPIC_VERSION,
        extra_headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
        default_timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        super().__init__(client=client, default_timeout_s=default_timeout_s)
        self.base_url = base_url.rstrip("/")
        self.model = model
        #: Optional BYOK credential — never appears in repr/logs (redacted).
        self.api_key: str | None = api_key
        self.api_version = api_version
        #: Non-secret extra headers (values are redacted from any error output).
        self.extra_headers: dict[str, str] = dict(extra_headers or {})

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ProviderAuthError(
                "No API key configured for the anthropic provider "
                "(set api_key_env or provide a key).",
                provider=self.name,
            )
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
        }
        headers.update(self.extra_headers)
        return headers

    def _secrets(self) -> tuple[str, ...]:
        values = list(self.extra_headers.values())
        if self.api_key:
            values.append(self.api_key)
        return tuple(values)

    def _tool_name(self, settings: GenerationSettings) -> str:
        return settings.json_schema_name or "emit_json"

    def _payload(
        self,
        settings: GenerationSettings,
        messages: list[dict[str, Any]],
        *,
        tool: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        system_text, rest = split_system(messages)
        payload: dict[str, Any] = {
            "model": self.require_model(settings),
            "max_tokens": settings.max_tokens,
            "temperature": settings.temperature,
            "messages": rest,
        }
        if system_text:
            payload["system"] = system_text
        if settings.top_p is not None:
            payload["top_p"] = settings.top_p
        if tool is not None:
            payload["tools"] = [tool]
            payload["tool_choice"] = {"type": "tool", "name": tool["name"]}
        payload.update(dict(settings.extra))
        return payload

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
        """Call ``/v1/messages`` with the schema forced as a single tool."""
        tool_name = self._tool_name(settings)
        tool = {
            "name": tool_name,
            "description": "Emit the final answer as JSON matching the caller's schema.",
            "input_schema": dict(schema),
        }
        response = await fetch_json(
            self.http(),
            f"{self.base_url}/v1/messages",
            provider=self.name,
            payload=self._payload(settings, messages, tool=tool),
            headers=self._headers(),
            timeout_s=settings.timeout_s,
            secrets=self._secrets(),
        )
        data = response_json(response, provider=self.name, secrets=self._secrets())
        content = data.get("content") if isinstance(data, dict) else None
        blocks = [block for block in (content or []) if isinstance(block, dict)]
        stop_reason = str(data.get("stop_reason") or "") if isinstance(data, dict) else ""
        snippet = json.dumps(blocks, ensure_ascii=False)
        if stop_reason == "max_tokens":
            raise MalformedOutputError(
                "Anthropic response was truncated at max_tokens before the forced "
                "tool call completed; retry with a higher limit.",
                provider=self.name,
                snippet=snippet,
            )
        tool_blocks = [block for block in blocks if block.get("type") == "tool_use"]
        if not tool_blocks:
            raise MalformedOutputError(
                "Anthropic response did not contain the forced tool_use block "
                f"'{tool_name}'.",
                provider=self.name,
                snippet=snippet,
            )
        parsed = tool_blocks[0].get("input")
        if not isinstance(parsed, dict):
            raise MalformedOutputError(
                "Forced tool_use block did not carry a JSON object input.",
                provider=self.name,
                snippet=snippet,
            )
        validate_required(parsed, schema)
        return parsed

    async def generate_structured_result(
        self,
        *,
        schema: dict[str, Any],
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> StructuredResult:
        """Structured call with latency telemetry."""
        started = perf_counter()
        data = await self.generate_structured(
            schema=schema, messages=messages, settings=settings
        )
        return StructuredResult(
            provider=self.name,
            model_id=settings.model,
            data=data,
            latency_ms=(perf_counter() - started) * 1000,
        )

    async def generate_text(
        self,
        *,
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> str:
        """Plain ``/v1/messages`` completion (text blocks concatenated)."""
        response = await fetch_json(
            self.http(),
            f"{self.base_url}/v1/messages",
            provider=self.name,
            payload=self._payload(settings, messages),
            headers=self._headers(),
            timeout_s=settings.timeout_s,
            secrets=self._secrets(),
        )
        data = response_json(response, provider=self.name, secrets=self._secrets())
        content = data.get("content") if isinstance(data, dict) else None
        text = "".join(
            str(block.get("text", ""))
            for block in (content or [])
            if isinstance(block, dict) and block.get("type") == "text"
        )
        if not text.strip():
            raise MalformedOutputError(
                "Anthropic returned no text content.",
                provider=self.name,
                snippet=json.dumps(content or [], ensure_ascii=False),
            )
        return text

    async def health_check(self) -> HealthStatus:
        """Probe ``GET /v1/models`` for reachability and model availability."""
        started = perf_counter()

        def _elapsed() -> float:
            return (perf_counter() - started) * 1000

        model_id = self.model
        try:
            response = await fetch_json(
                self.http(),
                f"{self.base_url}/v1/models",
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
        entries = data.get("data") if isinstance(data, dict) else None
        ids = [
            str(entry.get("id") or "")
            for entry in (entries or [])
            if isinstance(entry, dict)
        ]
        ids = [model for model in ids if model]
        if not model_id:
            return HealthStatus(
                ok=False,
                latency_ms=_elapsed(),
                detail=(
                    f"Anthropic API reachable ({len(ids)} model(s) listed) "
                    "but no model is configured."
                ),
                model_id="",
            )
        if model_id in ids:
            return HealthStatus(
                ok=True,
                latency_ms=_elapsed(),
                detail=f"Anthropic API reachable; model '{model_id}' is available.",
                model_id=model_id,
            )
        available = ", ".join(ids[:5]) or "none listed"
        return HealthStatus(
            ok=False,
            latency_ms=_elapsed(),
            detail=(
                f"Anthropic API reachable but model '{model_id}' was not listed. "
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
                "Structured output via a single forced tool (input_schema = JSON schema).",
                "Always sends the request text to api.anthropic.com (off-device).",
                "Context window depends on the model — see Anthropic docs.",
                "Embeddings are not offered by the Anthropic Messages API.",
            ],
        )
