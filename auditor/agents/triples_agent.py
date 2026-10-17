"""Agent 4 — Semantic Triple / KG Agent (PRD §8.2)."""

from __future__ import annotations

import time
from typing import Any

from ega_providers.registry import ProviderRegistry
from ega_schemas.audit import AuditRunState
from ega_schemas.providers import ModelCallRequest
from ega_schemas.triples import SemanticTriple

from auditor.prompts.templates import TRIPLES_AGENT_PROMPT


def run_triples_agent(state: AuditRunState) -> dict[str, Any]:
    """Extract explicit and implied subject-predicate-object triples."""
    start = time.time()
    provider = ProviderRegistry.get_provider(state.model_provider, state.model_name)

    entity_names = [e.canonical_name for e in state.entities[:8]]
    user_prompt = f"""Central Entity: {state.central_entity}
Entities: {", ".join(entity_names)}

<untrusted_content>
{state.content[:3500]}
</untrusted_content>
"""
    req = ModelCallRequest(
        system_prompt=TRIPLES_AGENT_PROMPT,
        user_prompt=user_prompt,
    )
    res = provider.call(req)
    parsed = res.parsed_json or {}

    triples: list[SemanticTriple] = []
    for t in parsed.get("triples", []):
        try:
            triples.append(SemanticTriple.model_validate(t))
        except Exception:
            pass

    elapsed = int((time.time() - start) * 1000)
    timeline_entry = {
        "node": "triples_agent",
        "duration_ms": elapsed,
        "triple_count": len(triples),
    }

    current_timeline = list(state.timeline)
    current_timeline.append(timeline_entry)

    return {
        "triples": triples,
        "timeline": current_timeline,
    }
