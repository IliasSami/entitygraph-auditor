"""Agent 3 — Entity & EAV Extraction Agent (PRD §8.2)."""

from __future__ import annotations

import time
from typing import Any

from ega_providers.registry import ProviderRegistry
from ega_schemas.audit import AuditRunState
from ega_schemas.entities import EAVRow, Entity
from ega_schemas.providers import ModelCallRequest

from auditor.prompts.templates import ENTITY_EAV_PROMPT


def run_entity_eav_agent(state: AuditRunState) -> dict[str, Any]:
    """Extract entities, salience, and EAV rows."""
    start = time.time()
    provider = ProviderRegistry.get_provider(state.model_provider, state.model_name)

    user_prompt = f"""Central Entity: {state.central_entity}
Page Type: {state.page_type.value}

<untrusted_content>
{state.content[:4000]}
</untrusted_content>
"""
    req = ModelCallRequest(
        system_prompt=ENTITY_EAV_PROMPT,
        user_prompt=user_prompt,
    )
    res = provider.call(req)
    parsed = res.parsed_json or {}

    entities: list[Entity] = []
    for e in parsed.get("entities", []):
        try:
            entities.append(Entity.model_validate(e))
        except Exception:
            pass

    eav_rows: list[EAVRow] = []
    for r in parsed.get("eav_rows", []):
        try:
            eav_rows.append(EAVRow.model_validate(r))
        except Exception:
            pass

    # Ensure central entity is marked
    if not any(e.is_central for e in entities) and state.central_entity:
        entities.insert(0, Entity(
            entity_id="ent-central-inferred",
            canonical_name=state.central_entity,
            is_central=True,
            salience=1.0,
        ))

    elapsed = int((time.time() - start) * 1000)
    timeline_entry = {
        "node": "entity_eav_agent",
        "duration_ms": elapsed,
        "entity_count": len(entities),
        "eav_count": len(eav_rows),
    }

    current_timeline = list(state.timeline)
    current_timeline.append(timeline_entry)

    return {
        "entities": entities,
        "eav_rows": eav_rows,
        "timeline": current_timeline,
    }
