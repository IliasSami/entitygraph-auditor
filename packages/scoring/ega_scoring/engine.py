"""Legacy ``ScoringEngine`` facade over the deterministic scoring engine.

The canonical public API lives in :mod:`ega_scoring.composite` and
:mod:`ega_scoring.gate` (``compute_all_scores``, ``evaluate_gate``,
``run_gate_and_scores``). This module keeps the older ``ScoringEngine.evaluate``
entry point working for the workflow/agent/MCP layers while they migrate:

* ``ScoringEngine.evaluate(entities, eav_rows, triples, fanout_queries,
  coverage_rows, claims, parsed_doc, page_type, context_packs)`` builds an
  equivalent run-state view and delegates to ``compute_all_scores``;
* ``ScoringEngine.generate_swot`` and ``ScoringEngine.prioritize_findings`` are
  unchanged in behaviour (the latter now uses the shared PRD §9.6 ordering).

Nothing here duplicates scoring logic — it only adapts arguments.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

from ega_schemas.claims import Claim
from ega_schemas.content import ParsedDocument
from ega_schemas.entities import EAVRow, Entity
from ega_schemas.enums import PageType, ScoreKey
from ega_schemas.fanout import CoverageRow, FanoutQuery
from ega_schemas.findings import Finding
from ega_schemas.report import SwotAnalysis
from ega_schemas.scores import Scorecard
from ega_schemas.triples import SemanticTriple

from auditor.rules.page_profiles import get_profile, weight_preset
from auditor.rules.priority import priority_sort as _prioritize
from ega_scoring.composite import compute_all_scores


def get_profile_weights(page_type: PageType) -> tuple[str, dict[ScoreKey, float]]:
    """Return the score-preset name and its per-component percentages (PRD §9.4)."""
    preset = get_profile(page_type).score_preset
    weights = {
        ScoreKey(key): round(value * 100.0, 4)
        for key, value in weight_preset(preset).items()
    }
    return preset, weights


#: Backwards-compatible percentage weight table keyed by preset name.
PAGE_TYPE_WEIGHTS: dict[str, dict[ScoreKey, float]] = {
    preset: {ScoreKey(key): round(value * 100.0, 4) for key, value in weight_preset(preset).items()}
    for preset in ("informational", "listicle", "commercial", "case_study")
}


class ScoringEngine:
    """Deterministic orchestrator facade (delegates to the rich engine)."""

    @classmethod
    def evaluate(
        cls,
        entities: list[Entity],
        eav_rows: list[EAVRow],
        triples: list[SemanticTriple],
        fanout_queries: list[FanoutQuery],
        coverage_rows: list[CoverageRow],
        claims: list[Claim],
        parsed_doc: Optional[ParsedDocument],
        page_type: PageType = PageType.GENERAL,
        context_packs: Optional[list[dict[str, Any]]] = None,
        force_renormalize: bool = True,
    ) -> Scorecard:
        """Run every component, the composite AVR and the gate, returning a ``Scorecard``."""
        state = SimpleNamespace(
            parsed_doc=parsed_doc,
            entities=list(entities or []),
            eav_rows=list(eav_rows or []),
            triples=list(triples or []),
            fanout_queries=list(fanout_queries or []),
            coverage_rows=list(coverage_rows or []),
            claims=list(claims or []),
            context_packs=list(context_packs or []),
            page_type=page_type,
        )
        return compute_all_scores(state, force_renormalize=force_renormalize)


    @classmethod
    def generate_swot(cls, scorecard: Scorecard) -> SwotAnalysis:
        """Synthesize Strengths, Weaknesses, Opportunities and Threats from a scorecard."""
        strengths: list[str] = []
        weaknesses: list[str] = []
        opportunities: list[str] = []
        threats: list[str] = []

        for key, cs in scorecard.scores.items():
            if cs.value >= 8.0:
                strengths.append(f"Strong {key} ({cs.value}/10): {cs.rationale}")
            elif cs.value < 5.5:
                weaknesses.append(f"Underperforming {key} ({cs.value}/10): {cs.rationale}")
                for reason in cs.lost_points_reasons[:2]:
                    opportunities.append(f"Improve {key}: {reason}")

        if scorecard.gate.critical_issues:
            for issue in scorecard.gate.critical_issues:
                threats.append(f"Compliance / Gate Threat: {issue}")
        else:
            threats.append("No critical gate threats detected.")

        if not strengths:
            strengths.append("Foundational content structure present.")
        if not weaknesses:
            weaknesses.append("No severe structural deficits detected.")
        if not opportunities:
            opportunities.append("Expand topical depth with supplementary sub-queries.")

        return SwotAnalysis(
            strengths=strengths,
            weaknesses=weaknesses,
            opportunities=opportunities,
            threats=threats,
        )

    @classmethod
    def prioritize_findings(cls, findings: list[Finding]) -> list[Finding]:
        """Rank recommendations with the PRD §9.6 priority formula and gate overrides."""
        return _prioritize(list(findings))


__all__ = [
    "PAGE_TYPE_WEIGHTS",
    "ScoringEngine",
    "get_profile_weights",
]
