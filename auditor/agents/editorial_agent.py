"""Agent 9 — Human Utility / Editorial Agent (PRD §8.2)."""

from __future__ import annotations

import time
from typing import Any

from ega_providers.registry import ProviderRegistry
from ega_schemas.audit import AuditRunState
from ega_schemas.findings import Finding
from ega_schemas.providers import ModelCallRequest

from auditor.prompts.templates import EDITORIAL_AGENT_PROMPT


def run_editorial_agent(state: AuditRunState) -> dict[str, Any]:
    """Assess clarity, tone, and practical utility for human readers."""
    start = time.time()
    provider = ProviderRegistry.get_provider(state.model_provider, state.model_name)

    user_prompt = f"""Target Audience: {state.target_audience}
Audience Action: {state.target_action}

<untrusted_content>
{state.content[:3500]}
</untrusted_content>
"""
    req = ModelCallRequest(
        system_prompt=EDITORIAL_AGENT_PROMPT,
        user_prompt=user_prompt,
    )
    res = provider.call(req)
    parsed = res.parsed_json or {}

    findings: list[Finding] = []
    for f in parsed.get("editorial_findings", []):
        try:
            findings.append(Finding.model_validate(f))
        except Exception:
            pass

    elapsed = int((time.time() - start) * 1000)
    timeline_entry = {
        "node": "editorial_agent",
        "duration_ms": elapsed,
        "finding_count": len(findings),
    }

    current_timeline = list(state.timeline)
    current_timeline.append(timeline_entry)

    # Merge into passage_findings
    merged_findings = list(state.passage_findings) + findings

    return {
        "passage_findings": merged_findings,
        "timeline": current_timeline,
    }
