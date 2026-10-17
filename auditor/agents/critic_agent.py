"""Agent 13 — Critic / QA Agent (PRD §8.2)."""

from __future__ import annotations

import time
from typing import Any

from ega_providers.registry import ProviderRegistry
from ega_schemas.audit import AuditRunState
from ega_schemas.providers import ModelCallRequest

from auditor.prompts.templates import CRITIC_AGENT_PROMPT


def run_critic_agent(state: AuditRunState) -> dict[str, Any]:
    """Validate draft audit integrity and enforce maximum 2 repair loops."""
    start = time.time()
    provider = ProviderRegistry.get_provider(state.model_provider, state.model_name)

    loop_count = state.critic_loops + 1

    user_prompt = f"""Audit Review:
Loop: {loop_count}
Central Entity: {state.central_entity}
Page Type: {state.page_type.value}
Composite AVR: {state.composite_avr}
Gate Status: {state.gate_result.status.value}
Total Findings: {len(state.recommendations)}
"""
    req = ModelCallRequest(
        system_prompt=CRITIC_AGENT_PROMPT,
        user_prompt=user_prompt,
    )
    res = provider.call(req)
    parsed = res.parsed_json or {}

    approved = parsed.get("critic_approved", True)
    raw_notes = parsed.get("notes", "Validated draft.")
    if isinstance(raw_notes, list):
        notes_str = "; ".join(str(n) for n in raw_notes)
    else:
        notes_str = str(raw_notes)

    # Guardrail: Maximum 2 repair loops
    if loop_count >= 2:
        approved = True
        notes_str += " (Approved after reaching maximum 2 critic iterations)."

    elapsed = int((time.time() - start) * 1000)
    timeline_entry = {
        "node": "critic_agent",
        "duration_ms": elapsed,
        "loop": loop_count,
        "approved": approved,
    }

    current_timeline = list(state.timeline)
    current_timeline.append(timeline_entry)

    return {
        "critic_loops": loop_count,
        "critic_approved": approved,
        "critic_notes": list(state.critic_notes) + [notes_str],
        "timeline": current_timeline,
    }

