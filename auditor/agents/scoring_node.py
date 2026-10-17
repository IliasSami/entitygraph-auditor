"""Agent 11 — Deterministic Scoring Engine Node (PRD §8.2 / §9)."""

from __future__ import annotations

import time
from typing import Any

from ega_schemas.audit import AuditRunState
from ega_scoring.engine import ScoringEngine


def run_scoring_node(state: AuditRunState) -> dict[str, Any]:
    """Execute deterministic score arithmetic and gate assessment."""
    start = time.time()

    scorecard = ScoringEngine.evaluate(
        entities=state.entities,
        eav_rows=state.eav_rows,
        triples=state.triples,
        fanout_queries=state.fanout_queries,
        coverage_rows=state.coverage_rows,
        claims=state.claims,
        parsed_doc=state.parsed_doc,
        page_type=state.page_type,
        context_packs=state.context_packs,
    )

    swot = ScoringEngine.generate_swot(scorecard)

    elapsed = int((time.time() - start) * 1000)
    timeline_entry = {
        "node": "scoring_node",
        "duration_ms": elapsed,
        "avr": scorecard.avr,
        "gate_status": scorecard.gate.status.value,
    }

    current_timeline = list(state.timeline)
    current_timeline.append(timeline_entry)

    return {
        "component_scores": scorecard.scores,
        "composite_avr": scorecard.avr,
        "gate_result": scorecard.gate,
        "swot": swot,
        "timeline": current_timeline,
    }
