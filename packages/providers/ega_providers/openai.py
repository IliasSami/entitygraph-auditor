"""OpenAI API adapter (api.openai.com) — optional BYOK, never required (FR-21).

Uses ``POST /v1/chat/completions`` with ``response_format`` = strict
``json_schema`` (``strict: true``). The chat-completions endpoint is kept
instead of the newer ``/v1/responses`` API for broad compatibility (proxies,
gateways and Azure-style deployments speak chat-completions); the shared
downgrade chain (``json_schema`` → ``json_object`` → plain prompting) still
protects against servers that reject strict schemas.

Requires an API key: :func:`ega_providers.registry.build_provider` refuses to
construct this provider without one. A ChatGPT/Claude consumer subscription
is NOT API access, and provider API usage may cost money.
"""

from __future__ import annotations

from typing import Any

import httpx

from ega_providers.base import DEFAULT_TIMEOUT_S, GenerationSettings
from ega_providers.openai_compat import OpenAICompatProvider


class OpenAIProvider(OpenAICompatProvider):
    """OpenAI ``/v1/chat/completions`` with strict JSON-schema output."""

    name: str = "openai"

    #: OpenAI strict mode: schema-constrained outputs (see module docstring).
    strict_json_schema: bool = True

    def __init__(
        self,
        config: Any = None,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "",
        extra_headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
        default_timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        if config is not None:
            base_url = getattr(config, "base_url", None) or base_url
            model = getattr(config, "model_name", None) or getattr(config, "model", "") or model
            api_key = getattr(config, "api_key", None) or api_key
        super().__init__(
            base_url=base_url,
            model=model,
            api_key=api_key,
            extra_headers=extra_headers,
            client=client,
            default_timeout_s=default_timeout_s,
        )
        self.config = config

    def _payload(
        self,
        settings: GenerationSettings,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None,
        instruction: str | None,
    ) -> dict[str, Any]:
        payload = super()._payload(
            settings, messages, response_format=response_format, instruction=instruction
        )
        if payload.get("response_format", {}).get("type") == "json_schema":
            payload["response_format"]["json_schema"]["strict"] = True
        return payload


OpenAICompatibleProvider = OpenAIProvider
__all__ = ["OpenAIProvider", "OpenAICompatibleProvider"]

