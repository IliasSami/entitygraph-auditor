"""Agent 2 — Query / Fan-out Research Agent (PRD §8.2)."""

from __future__ import annotations

import time
from typing import Any

from ega_providers.registry import ProviderRegistry
from ega_schemas.audit import AuditRunState
from ega_schemas.fanout import FanoutQuery
from ega_schemas.providers import ModelCallRequest

from auditor.prompts.templates import FANOUT_AGENT_PROMPT


def run_fanout_agent(state: AuditRunState) -> dict[str, Any]:
    """Generate or retrieve query fan-out candidate questions."""
    start = time.time()
    provider = ProviderRegistry.get_provider(state.model_provider, state.model_name)

    user_prompt = f"""Central Entity: {state.central_entity}
Page Type: {state.page_type.value}
Primary Intent: {state.primary_intent.value}
Audience: {state.target_audience}

<untrusted_content>
{state.content[:3000]}
</untrusted_content>
"""
    req = ModelCallRequest(
        system_prompt=FANOUT_AGENT_PROMPT,
        user_prompt=user_prompt,
    )
    res = provider.call(req)
    parsed = res.parsed_json or {}

    raw_queries = parsed.get("fanout_queries", [])
    queries: list[FanoutQuery] = []
    for q in raw_queries:
        try:
            queries.append(FanoutQuery.model_validate(q))
        except Exception:
            pass

    elapsed = int((time.time() - start) * 1000)
    timeline_entry = {
        "node": "fanout_agent",
        "duration_ms": elapsed,
        "query_count": len(queries),
    }

    current_timeline = list(state.timeline)
    current_timeline.append(timeline_entry)

    return {
        "fanout_queries": queries,
        "timeline": current_timeline,
    }
