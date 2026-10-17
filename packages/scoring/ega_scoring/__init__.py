"""Deterministic scoring engine for EntityGraph Auditor (PRD §9).

Public API
----------

* :func:`compute_all_scores` — ``state -> Scorecard`` (components, composite
  AVR, gate).
* :func:`evaluate_gate` — ``state -> GateResult`` (PRD §9.5).
* :func:`run_gate_and_scores` — ``state -> (GateResult, Scorecard)``.

Supporting modules:

* :mod:`ega_scoring.rubric` — scale anchors, clamping, confidence, disclaimer;
* :mod:`ega_scoring.components` — the seven core component scorers (PRD §9.2);
* :mod:`ega_scoring.optional` — PRD §9.3 optional profile scores;
* :mod:`ega_scoring.composite` — AVR weights, composite and scorecard assembly;
* :mod:`ega_scoring.gate` — brand/claim/compliance gate;
* :mod:`ega_scoring.state` — tolerant accessors over the shared run state.

Every score produced here is an *internal editorial heuristic* — never an
official Google, Bing, OpenAI, Anthropic or Perplexity metric, and never an
LLM judgement. The engine is pure and deterministic: it never touches the
network and never calls a model.
"""

from __future__ import annotations

from typing import Any

from ega_schemas.scores import GateResult

from ega_scoring.components import (
    CWS_WEIGHTS,
    EOS_LOCAL_WEIGHTS,
    EOS_WEIGHTS,
    ERS_WEIGHTS,
    HRS_WEIGHTS,
    KGR_WEIGHTS,
    PRS_WEIGHTS,
    compute_cws,
    compute_eos,
    compute_ers,
    compute_fcs,
    compute_hrs,
    compute_kgr,
    compute_prs,
    label_for,
)
from ega_scoring.composite import (
    CORE_COMPONENT_ORDER,
    OPTIONAL_COMPONENT_ORDER,
    build_scorecard,
    component_weights,
    compute_all_scores,
    compute_avr,
    compute_components,
    missing_components,
    resolve_preset,
)
from ega_scoring.engine import PAGE_TYPE_WEIGHTS, ScoringEngine, get_profile_weights
from ega_scoring.gate import build_gate_result, evaluate_gate, gate_is_publishable
from ega_scoring.models import Scorecard, ScoreComponent, combine_sub_scores, overall_confidence
from ega_scoring.optional import (
    compute_conversion,
    compute_intent,
    compute_internal_links,
    compute_local_fit,
    compute_paid_fit,
    compute_trust,
)
from ega_scoring.rubric import (
    ANCHORS,
    PROFILE_VERSION,
    SCORE_HEURISTIC_DISCLAIMER,
    anchor_for,
    clamp,
    confidence_for,
    confidence_min,
    heuristic_disclaimer,
    mean,
    weighted_ratio,
)
from ega_scoring.rubrics import (
    calculate_cws,
    calculate_eos,
    calculate_ers,
    calculate_fcs,
    calculate_hrs,
    calculate_kgr,
    calculate_prs,
)


def run_gate_and_scores(state: Any) -> tuple[GateResult, Scorecard]:
    """Evaluate the gate and compute the scorecard for ``state``.

    The gate is evaluated once and injected into the scorecard, so callers get a
    single consistent pair (PRD §9.4/§9.5).
    """
    gate = evaluate_gate(state)
    scorecard = build_scorecard(state, gate=gate)
    return gate, scorecard


__all__ = [
    "ANCHORS",
    "CORE_COMPONENT_ORDER",
    "CWS_WEIGHTS",
    "EOS_LOCAL_WEIGHTS",
    "EOS_WEIGHTS",
    "ERS_WEIGHTS",
    "HRS_WEIGHTS",
    "KGR_WEIGHTS",
    "OPTIONAL_COMPONENT_ORDER",
    "PAGE_TYPE_WEIGHTS",
    "PROFILE_VERSION",
    "PRS_WEIGHTS",
    "SCORE_HEURISTIC_DISCLAIMER",
    "ScoreComponent",
    "Scorecard",
    "ScoringEngine",
    "anchor_for",
    "build_gate_result",
    "build_scorecard",
    "calculate_cws",
    "calculate_eos",
    "calculate_ers",
    "calculate_fcs",
    "calculate_hrs",
    "calculate_kgr",
    "calculate_prs",
    "clamp",
    "combine_sub_scores",
    "component_weights",
    "compute_all_scores",
    "compute_avr",
    "compute_components",
    "compute_conversion",
    "compute_cws",
    "compute_eos",
    "compute_ers",
    "compute_fcs",
    "compute_hrs",
    "compute_intent",
    "compute_internal_links",
    "compute_kgr",
    "compute_local_fit",
    "compute_paid_fit",
    "compute_prs",
    "compute_trust",
    "confidence_for",
    "confidence_min",
    "evaluate_gate",
    "gate_is_publishable",
    "get_profile_weights",
    "heuristic_disclaimer",
    "label_for",
    "mean",
    "missing_components",
    "overall_confidence",
    "resolve_preset",
    "run_gate_and_scores",
    "weighted_ratio",
]
