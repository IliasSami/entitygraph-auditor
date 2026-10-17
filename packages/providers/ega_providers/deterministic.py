"""Deterministic-only mode providers (PRD FR-22, §25 "Model mode: local-first").

Two adapters:

* :class:`NullProvider` — the honest "no model configured" adapter.
  ``health_check()`` reports ``ok=False`` with
  ``"No model configured — deterministic-only mode"`` and every generation
  call raises :class:`CapabilityError`. The workflow marks semantic stages
  skipped/failed; nothing is ever fabricated to fill the gap.

* :class:`EchoSchemaProvider` — **TEST-ONLY** canned responder used by unit
  tests and demos. It is excluded from :data:`ega_providers.registry.PROVIDER_CATALOG`
  and :func:`ega_providers.registry.get_provider` refuses ``type="test"``
  unless ``allow_test=True``.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ega_providers.base import (
    DEFAULT_TIMEOUT_S,
    GenerationSettings,
    HealthStatus,
    ModelProvider,
    ProviderCapabilities,
    StructuredResult,
)
from ega_providers.errors import CapabilityError


class NullProvider(ModelProvider):
    """Deterministic-only mode: no model configured, no semantic inference."""

    name: str = "null"
    model: str = ""

    async def generate_structured(
        self,
        *,
        schema: dict[str, Any],
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> dict[str, Any]:
        """Always raises — a failed stage is reported, never fabricated."""
        raise CapabilityError(
            "No model configured.", provider=self.name
        )

    async def generate_text(
        self,
        *,
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> str:
        """Always raises — deterministic-only mode has no generator."""
        raise CapabilityError(
            "No model configured.", provider=self.name
        )

    async def health_check(self) -> HealthStatus:
        """Report deterministic-only mode as unhealthy-for-LLM-stages."""
        return HealthStatus(
            ok=False,
            latency_ms=0.0,
            detail="No model configured — deterministic-only mode",
            model_id="",
        )

    def capabilities(self) -> ProviderCapabilities:
        """No generation capability; nothing leaves this machine."""
        return ProviderCapabilities(
            provider=self.name,
            model_id="",
            structured_output=False,
            tool_calls=False,
            context_window=None,
            sends_data_off_device=False,
            notes=[
                "Deterministic-only mode: semantic model stages are skipped and "
                "reported as not_assessed (PRD FR-22).",
                "No data ever leaves this machine.",
            ],
        )


class EchoSchemaProvider(ModelProvider):
    """TEST-ONLY provider returning a canned dict (never real model output).

    Do not use in production paths: it is absent from ``PROVIDER_CATALOG`` and
    ``get_provider("test", allow_test=True)`` is the only registry entry point.
    Every result carries a note marking it as canned/test-only.
    """

    name: str = "test"

    def __init__(
        self,
        *,
        model: str = "echo-schema-test",
        canned: dict[str, Any] | None = None,
        client: httpx.AsyncClient | None = None,
        default_timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        super().__init__(client=client, default_timeout_s=default_timeout_s)
        self.model = model
        #: Canned payload returned by generate_structured (test fixture data).
        self.canned: dict[str, Any] = dict(canned) if canned is not None else {"status": "ok"}

    async def generate_structured(
        self,
        *,
        schema: dict[str, Any],
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> dict[str, Any]:
        """Return the canned dict — clearly NOT model-generated content."""
        return dict(self.canned)

    async def generate_structured_result(
        self,
        *,
        schema: dict[str, Any],
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> StructuredResult:
        """Canned dict plus a test-only marker note."""
        return StructuredResult(
            provider=self.name,
            model_id=settings.model or self.model,
            data=dict(self.canned),
            notes=["EchoSchemaProvider is test-only; output is canned, not model-generated."],
            latency_ms=0.0,
        )

    async def generate_text(
        self,
        *,
        messages: list[dict[str, Any]],
        settings: GenerationSettings,
    ) -> str:
        """Return a canned string (test-only)."""
        return json.dumps(self.canned, ensure_ascii=False)

    async def health_check(self) -> HealthStatus:
        """Always healthy — it is a local canned responder."""
        return HealthStatus(
            ok=True,
            latency_ms=0.0,
            detail="EchoSchemaProvider (test-only canned responses)",
            model_id=self.model,
        )

    def capabilities(self) -> ProviderCapabilities:
        """Marked test-only everywhere it can be."""
        return ProviderCapabilities(
            provider=self.name,
            model_id=self.model,
            structured_output=True,
            tool_calls=False,
            context_window=None,
            sends_data_off_device=False,
            notes=[
                "TEST-ONLY adapter: returns canned fixtures, never real model output.",
            ],
        )
