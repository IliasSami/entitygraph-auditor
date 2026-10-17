"""Agent 12 — Priority & Writer-Handoff Agent (PRD §8.2 / §21)."""

from __future__ import annotations

import time
from typing import Any

from ega_providers.registry import ProviderRegistry
from ega_schemas.audit import AuditRunState
from ega_schemas.findings import Finding
from ega_schemas.providers import ModelCallRequest
from ega_scoring.engine import ScoringEngine

from auditor.prompts.templates import HANDOFF_AGENT_PROMPT


def run_handoff_agent(state: AuditRunState) -> dict[str, Any]:
    """Synthesize prioritized recommendations and writer briefs."""
    start = time.time()
    provider = ProviderRegistry.get_provider(state.model_provider, state.model_name)

    # Summarize weaknesses from SWOT or lost points
    weaknesses = state.swot.weaknesses if state.swot else []
    lost_reasons = []
    for cs in state.component_scores.values():
        lost_reasons.extend(cs.lost_points_reasons)

    user_prompt = f"""Central Entity: {state.central_entity}
Gate Status: {state.gate_result.status.value}
Critical Issues: {", ".join(state.gate_result.critical_issues)}
Weaknesses: {", ".join(weaknesses[:3])}
Key Gaps: {", ".join(lost_reasons[:4])}

<untrusted_content>
{state.content[:3000]}
</untrusted_content>
"""
    req = ModelCallRequest(
        system_prompt=HANDOFF_AGENT_PROMPT,
        user_prompt=user_prompt,
    )
    res = provider.call(req)
    parsed = res.parsed_json or {}

    raw_recs = parsed.get("recommendations", [])
    recs: list[Finding] = []
    for r in raw_recs:
        try:
            recs.append(Finding.model_validate(r))
        except Exception:
            pass

    # Include existing passage/editorial findings
    all_findings = list(state.passage_findings) + recs
    prioritized = ScoringEngine.prioritize_findings(all_findings)

    elapsed = int((time.time() - start) * 1000)
    timeline_entry = {
        "node": "handoff_agent",
        "duration_ms": elapsed,
        "recommendation_count": len(prioritized),
    }

    current_timeline = list(state.timeline)
    current_timeline.append(timeline_entry)

    return {
        "recommendations": prioritized,
        "measurement_plan": parsed.get("measurement_plan", []),
        "timeline": current_timeline,
    }
