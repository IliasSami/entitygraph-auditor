"""Agent 8 — Coverage & Gap Agent (PRD §8.2)."""

from __future__ import annotations

import time
from typing import Any

from ega_providers.registry import ProviderRegistry
from ega_schemas.audit import AuditRunState
from ega_schemas.fanout import CoverageRow, CoverageStatus
from ega_schemas.providers import ModelCallRequest

from auditor.prompts.templates import COVERAGE_AGENT_PROMPT


def run_coverage_agent(state: AuditRunState) -> dict[str, Any]:
    """Map candidate fan-out queries against passages."""
    start = time.time()
    provider = ProviderRegistry.get_provider(state.model_provider, state.model_name)

    queries_summary = [f"{q.query_id}: {q.query_text} (importance={q.importance})" for q in state.fanout_queries]
    user_prompt = f"""Queries to match:
{chr(10).join(queries_summary)}

<untrusted_content>
{state.content[:3500]}
</untrusted_content>
"""
    req = ModelCallRequest(
        system_prompt=COVERAGE_AGENT_PROMPT,
        user_prompt=user_prompt,
    )
    res = provider.call(req)
    parsed = res.parsed_json or {}

    rows: list[CoverageRow] = []
    for r in parsed.get("coverage_rows", []):
        try:
            row = CoverageRow.model_validate(r)
        except Exception:
            continue
        # A 'covered'/'partial' claim must name the passage it was matched to;
        # an uncited claim is unsubstantiated (PRD §8.8, guardrails) and is
        # dropped so fabricated coverage cannot inflate FCS.
        if row.status in (CoverageStatus.COVERED, CoverageStatus.PARTIAL) and not row.matched_passage_ids:
            continue
        rows.append(row)

    elapsed = int((time.time() - start) * 1000)
    timeline_entry = {
        "node": "coverage_agent",
        "duration_ms": elapsed,
        "coverage_row_count": len(rows),
    }

    current_timeline = list(state.timeline)
    current_timeline.append(timeline_entry)

    return {
        "coverage_rows": rows,
        "timeline": current_timeline,
    }
