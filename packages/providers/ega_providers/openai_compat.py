"""Generic OpenAI-compatible ``/chat/completions`` adapter (PRD §13.3).

Used for Ollama's OpenAI mode, vLLM, LM Studio, llama.cpp server, LocalAI and
any other endpoint that speaks the OpenAI chat-completions dialect.

Structured output requests ``response_format`` with automatic downgrade:

1. ``{"type": "json_schema", "json_schema": {…, "strict": …}}``
2. ``{"type": "json_object"}`` — when the server answers HTTP 400 for #1
3. plain prompting (the schema is appended as an instruction) — when the
   server also answers HTTP 400 for #2

Every downgrade is recorded in :class:`StructuredResult.notes` so the UI can
show that schema enforcement was weaker than requested. The API key is
optional (self-hosted endpoints often need none) and is redacted from reprs,
logs and exception messages.
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
from ega_providers.errors import (
    MalformedOutputError,
    ProviderError,
)


def _schema_instruction(schema: dict[str, Any]) -> str:
    """Plain-prompting instruction embedding the requested JSON schema."""
    return (
        "Respond with a single JSON object that matches this JSON schema exactly "
        "(no prose, no code fences):\n" + json.dumps(schema, ensure_ascii=False)
    )


class OpenAICompatProvider(ModelProvider):
    """Adapter for any OpenAI-compatible chat-completions endpoint."""

    name: str = "openai_compatible"

    #: Send ``strict: true`` in the ``json_schema`` response_format (OpenAI strict mode).
    strict_json_schema: bool = False

    def __init__(
        self,
        *,
        base_url: str,
        model: str = "",
        api_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
        default_timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        super().__init__(client=client, default_timeout_s=default_timeout_s)
        if not base_url:
            raise ProviderError(
                "base_url is required for the openai_compatible provider "
                "(e.g. http://localhost:11434/v1).",
                provider=self.name,
                retryable=False,
            )
        self.base_url = base_url.rstrip("/")
        self.model = model
        #: Optional BYOK credential — never appears in repr/logs (redacted).
        self.api_key: str | None = api_key
        #: Non-secret extra headers (values are redacted from any error output).
        self.extra_headers: dict[str, str] = dict(extra_headers or {})

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _headers(self) -> dict[str, str]:
        headers = dict(self.extra_headers)
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _secrets(self) -> tuple[str, ...]:
        values = list(self.extra_headers.values())
        if self.api_key:
            values.append(self.api_key)
        return tuple(values)

    def _payload(
        self,
        settings: GenerationSettings,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None,
        instruction: str | None,
    ) -> dict[str, Any]:
        out_messages = [dict(message) for message in messages]
        if instruction:
            out_messages.append({"role": "user", "content": instruction})
        payload: dict[str, Any] = {
            "model": self.require_model(settings),
            "messages": out_messages,
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
        }
        if settings.top_p is not None:
            payload["top_p"] = settings.top_p
        if response_format is not None:
            payload["response_format"] = response_format
        payload.update(dict(settings.extra))
        return payload

    @staticmethod
    def _choice_text(data: dict[str, Any]) -> tuple[str, str | None]:
        """Return ``(content, finish_reason)`` from the first choice."""
        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices or not isinstance(choices[0], dict):
            return "", None
        choice = choices[0]
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = message.get("content", "")
        if isinstance(content, list):  # OpenAI content-part arrays
            content = "".join(
                str(part.get("text", "")) for part in content if isinstance(part, dict)
            )
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        finish = choice.get("finish_reason")
        return content, str(finish) if finish is not None else None

    def _attempts(
        self, settings: GenerationSettings, schema: dict[str, Any]
    ) -> list[tuple[str, dict[str, Any] | None, str | None]]:
        """The response_format downgrade chain ``(label, response_format, instruction)``."""
        return [
            (
                "json_schema",
                {
                    "type": "json_schema",
                    "json_schema": {
                        "name": settings.json_schema_name or "response",
                        "strict": self.strict_json_schema,
                        "schema": dict(schema),
                    },
                },
                None,
            ),
            ("json_object", {"type": "json_object"}, "Respond with a single JSON object only."),
            ("plain_prompt", None, _schema_instruction(schema)),
        ]

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
        """Structured call following the ``response_format`` downgrade chain."""
        notes: list[str] = []
        started = perf_counter()
        url = f"{self.base_url}/chat/completions"
        attempts = self._attempts(settings, schema)
        response: httpx.Response | None = None
        for index, (label, response_format, instruction) in enumerate(attempts):
            payload = self._payload(
                settings,
                messages,
                response_format=response_format,
                instruction=instruction,
            )
            response = await fetch_json(
                self.http(),
                url,
                provider=self.name,
                payload=payload,
                headers=self._headers(),
                timeout_s=settings.timeout_s,
                secrets=self._secrets(),
                require_success=False,
            )
            if response.status_code == 400 and index < len(attempts) - 1:
                next_label = attempts[index + 1][0]
                notes.append(
                    f"response_format '{label}' rejected with HTTP 400; "
                    f"fell back to '{next_label}'."
                )
                continue
            break
        if response is None:  # pragma: no cover - attempts is never empty
            raise ProviderError(
                f"{self.name} produced no response for the request.",
                provider=self.name,
                retryable=False,
            )
        raise_for_provider_status(response, provider=self.name, secrets=self._secrets())
        data = response_json(response, provider=self.name, secrets=self._secrets())
        content, finish = self._choice_text(data)
        if finish == "length":
            raise MalformedOutputError(
                "Model output was truncated at max_tokens; retry with a higher limit.",
                provider=self.name,
                snippet=content,
            )
        if not content.strip():
            raise MalformedOutputError(
                f"{self.name} returned an empty completion.",
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
        """Parse a schema-constrained completion into a dict."""
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
        """Plain completion without a ``response_format`` constraint."""
        url = f"{self.base_url}/chat/completions"
        payload = self._payload(settings, messages, response_format=None, instruction=None)
        response = await fetch_json(
            self.http(),
            url,
            provider=self.name,
            payload=payload,
            headers=self._headers(),
            timeout_s=settings.timeout_s,
            secrets=self._secrets(),
        )
        data = response_json(response, provider=self.name, secrets=self._secrets())
        content, finish = self._choice_text(data)
        if finish == "length":
            raise MalformedOutputError(
                "Model output was truncated at max_tokens; retry with a higher limit.",
                provider=self.name,
                snippet=content,
            )
        if not content.strip():
            raise MalformedOutputError(
                f"{self.name} returned an empty completion.",
                provider=self.name,
                snippet=json.dumps(data, ensure_ascii=False),
            )
        return content

    async def health_check(self) -> HealthStatus:
        """Probe ``GET {base}/models`` for reachability and model availability."""
        started = perf_counter()

        def _elapsed() -> float:
            return (perf_counter() - started) * 1000

        model_id = self.model
        try:
            response = await fetch_json(
                self.http(),
                f"{self.base_url}/models",
                provider=self.name,
                method="GET",
                headers=self._headers(),
                timeout_s=self.default_timeout_s,
                secrets=self._secrets(),
            )
            data = response_json(response, provider=self.name, secrets=self._secrets())
        except ProviderError as exc:
            if exc.status_code in (404, 405) and model_id:
                return HealthStatus(
                    ok=True,
                    latency_ms=_elapsed(),
                    detail=(
                        f"Endpoint is reachable, but /models is not supported "
                        f"(HTTP {exc.status_code}); availability of '{model_id}' "
                        "was not verified."
                    ),
                    model_id=model_id,
                )
            return HealthStatus(
                ok=False,
                latency_ms=_elapsed(),
                detail=exc.safe_message,
                model_id=model_id,
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
                    f"Endpoint is reachable ({len(ids)} model(s) listed) "
                    "but no model is configured."
                ),
                model_id="",
            )
        if model_id in ids:
            return HealthStatus(
                ok=True,
                latency_ms=_elapsed(),
                detail=f"Endpoint is reachable; model '{model_id}' is available.",
                model_id=model_id,
            )
        available = ", ".join(ids[:5]) or "none listed"
        return HealthStatus(
            ok=False,
            latency_ms=_elapsed(),
            detail=(
                f"Endpoint is reachable but model '{model_id}' was not found in "
                f"/models. Available: {available}."
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
            sends_data_off_device=not is_local_url(self.base_url),
            notes=[
                "OpenAI-compatible /chat/completions with json_schema → json_object → "
                "plain-prompting fallback.",
                "Tool calling is supported by OpenAI-compatible servers; this adapter "
                "enforces JSON instead of issuing tools.",
                "Loopback/private base_url values keep text on this machine; anything "
                "else sends data off-device.",
            ],
        )
