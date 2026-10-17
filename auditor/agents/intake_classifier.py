"""Agent 1 — Intake & Page-Type Classifier (PRD §8.2)."""

from __future__ import annotations

import time
from typing import Any

from ega_providers.registry import ProviderRegistry
from ega_schemas.audit import AuditRunState
from ega_schemas.enums import IntentClass, PageType
from ega_schemas.providers import ModelCallRequest

from auditor.prompts.templates import INTAKE_CLASSIFIER_PROMPT


def run_intake_classifier(state: AuditRunState) -> dict[str, Any]:
    """Execute classification of page type, central entity, and search intent."""
    start = time.time()
    provider = ProviderRegistry.get_provider(state.model_provider, state.model_name)

    user_prompt = f"""Analyze this content:
<untrusted_content>
{state.content[:4000]}
</untrusted_content>
"""
    req = ModelCallRequest(
        system_prompt=INTAKE_CLASSIFIER_PROMPT,
        user_prompt=user_prompt,
    )
    res = provider.call(req)
    parsed = res.parsed_json or {}

    updates: dict[str, Any] = {}
    
    # User-specified overrides take precedence per PRD §5
    if state.page_type == PageType.GENERAL and parsed.get("page_type"):
        try:
            updates["page_type"] = PageType(parsed["page_type"])
        except ValueError:
            pass

    if not state.central_entity and parsed.get("central_entity"):
        updates["central_entity"] = parsed["central_entity"]

    if parsed.get("primary_intent"):
        try:
            updates["primary_intent"] = IntentClass(parsed["primary_intent"])
        except ValueError:
            pass

    if parsed.get("target_audience"):
        updates["target_audience"] = parsed["target_audience"]

    if parsed.get("target_action"):
        updates["target_action"] = parsed["target_action"]

    elapsed = int((time.time() - start) * 1000)
    timeline_entry = {
        "node": "intake_classifier",
        "duration_ms": elapsed,
        "page_type": updates.get("page_type", state.page_type).value,
        "central_entity": updates.get("central_entity", state.central_entity),
    }

    current_timeline = list(state.timeline)
    current_timeline.append(timeline_entry)
    updates["timeline"] = current_timeline

    return updates
