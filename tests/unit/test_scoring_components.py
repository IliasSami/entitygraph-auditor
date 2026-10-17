"""Unit tests for the seven core component scorers (PRD §9.2).

Every assertion here is pinned to the deterministic sample state built by
``tests/fixtures/scoring/builders.py`` or to a hand-built structured state, so
the tests double as a regression lock on the rubric outputs. The suite also
checks the *epistemology* the PRD demands: missing inputs are never scored as
zero, values stay on the 0–10 scale, and repeated runs are bit-identical.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from ega_schemas.enums import (
    Confidence,
    CoverageStatus,
    EAVStatus,
    PageType,
    QueryScope,
    ScoreKey,
)
from ega_schemas.fanout import CoverageRow, FanoutQuery
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
from ega_scoring.models import ScoreComponent
from test_scoring_fixtures import empty_state, rich_state

CORE = {
    ScoreKey.EOS: compute_eos,
    ScoreKey.ERS: compute_ers,
    ScoreKey.KGR: compute_kgr,
    ScoreKey.FCS: compute_fcs,
    ScoreKey.PRS: compute_prs,
    ScoreKey.CWS: compute_cws,
    ScoreKey.HRS: compute_hrs,
}

#: Values the rich fixture state produces today; a change means the rubric moved.
RICH_VALUES = {
    ScoreKey.EOS: 8.7,
    ScoreKey.ERS: 5.2,
    ScoreKey.KGR: 6.9,
    ScoreKey.FCS: 6.5,
    ScoreKey.PRS: 8.8,
    ScoreKey.CWS: 6.1,
    ScoreKey.HRS: 6.0,
}

ALL_WEIGHT_TABLES = {
    "EOS": EOS_WEIGHTS,
    "EOS_LOCAL": EOS_LOCAL_WEIGHTS,
    "ERS": ERS_WEIGHTS,
    "KGR": KGR_WEIGHTS,
    "PRS": PRS_WEIGHTS,
    "CWS": CWS_WEIGHTS,
    "HRS": HRS_WEIGHTS,
}


# --------------------------------------------------------------- rich state ---


@pytest.mark.parametrize("key", list(CORE))
def test_core_scorer_assessed_on_rich_state(key: ScoreKey) -> None:
    """Every core scorer returns an assessed 0–10 component on the rich state."""
    component = CORE[key](rich_state())
    assert component.assessed is True
    assert component.not_assessed is False
    assert component.value is not None
    assert 0.0 <= component.value <= 10.0
    assert component.score_key is key


@pytest.mark.parametrize("key,expected", list(RICH_VALUES.items()))
def test_core_scorer_rich_values(key: ScoreKey, expected: float) -> None:
    """The rich fixture produces the exact, deterministic published values."""
    assert CORE[key](rich_state()).value == expected


@pytest.mark.parametrize("key", list(CORE))
def test_core_scorer_rationale_is_present(key: ScoreKey) -> None:
    """Each assessed component explains itself (no bare numbers in reports)."""
    component = CORE[key](rich_state())
    assert component.rationale.strip()
    assert component.label.strip()
    assert component.observations > 0
    assert isinstance(component.confidence, Confidence)


# -------------------------------------------------------------- empty state ---


@pytest.mark.parametrize("key", list(CORE))
def test_core_scorer_unassessed_on_empty_state(key: ScoreKey) -> None:
    """With no inputs a core scorer is not-assessed, never a 0.0 score."""
    component = CORE[key](empty_state())
    assert component.value is None
    assert component.not_assessed is True
    assert component.assessed is False
    assert component.not_applicable is False  # it *could* apply, it just has no data
    assert component.rationale.strip()
    assert component.confidence is Confidence.NOT_ASSESSED


# ------------------------------------------------------------------- FCS -----


def _fcs_state(queries, rows):
    return SimpleNamespace(
        fanout_queries=list(queries),
        coverage_rows=list(rows),
        page_type=PageType.ARTICLE,
    )


def test_fcs_importance_weighted_formula() -> None:
    """FCS = 10 × Σ(importance × coverage_credit) / Σ(importance) (PRD §9.2.D)."""
    queries = [
        FanoutQuery(query_id="q1", query_text="what", importance=3),
        FanoutQuery(query_id="q2", query_text="cost", importance=2),
        FanoutQuery(query_id="q3", query_text="oss", importance=1),
    ]
    rows = [
        CoverageRow(query_id="q1", query_text="what", status=CoverageStatus.COVERED),
        CoverageRow(query_id="q2", query_text="cost", status=CoverageStatus.PARTIAL),
        CoverageRow(query_id="q3", query_text="oss", status=CoverageStatus.MISSING),
    ]
    # numerator = 3×1.0 + 2×0.5 + 1×0.0 = 4.0 over denominator 6.0 → 6.7
    component = compute_fcs(_fcs_state(queries, rows))
    assert component.value == 6.7
    assert component.sub_scores["weighted_coverage"] == 6.7


def test_fcs_excludes_excluded_rows_and_out_of_scope_queries() -> None:
    """Excluded rows and out-of-scope queries leave the denominator (PRD §9.2.D)."""
    queries = [
        FanoutQuery(query_id="q1", query_text="what", importance=3),
        FanoutQuery(query_id="q2", query_text="cost", importance=2),
        FanoutQuery(query_id="q3", query_text="off", importance=3, scope=QueryScope.OUT_OF_SCOPE),
    ]
    rows = [
        CoverageRow(query_id="q1", query_text="what", status=CoverageStatus.COVERED),
        CoverageRow(query_id="q2", query_text="cost", status=CoverageStatus.MISSING),
        CoverageRow(query_id="q3", query_text="off", status=CoverageStatus.COVERED),
        CoverageRow(query_id="qx", query_text="x", status=CoverageStatus.EXCLUDED),
    ]
    # Only q1 (importance 3, covered) and q2 (importance 2, missing) remain:
    # 10 × 3.0 / 5.0 = 6.0.
    component = compute_fcs(_fcs_state(queries, rows))
    assert component.value == 6.0


def test_fcs_zero_rows_is_not_assessed() -> None:
    """A missing coverage matrix is not-assessed, not a zero score (PRD §9.4)."""
    component = compute_fcs(_fcs_state([], []))
    assert component.value is None
    assert component.not_assessed is True


def test_fcs_all_excluded_is_not_assessed() -> None:
    """When every in-scope row is excluded the denominator vanishes → not-assessed."""
    queries = [
        FanoutQuery(query_id="q1", query_text="off", importance=3, scope=QueryScope.OUT_OF_SCOPE)
    ]
    rows = [CoverageRow(query_id="q1", query_text="off", status=CoverageStatus.COVERED)]
    component = compute_fcs(_fcs_state(queries, rows))
    assert component.value is None
    assert component.not_assessed is True


def test_fcs_provenance_counts_observed_and_simulated() -> None:
    """FCS labels observed vs simulated coverage and never blends them silently."""
    component = compute_fcs(rich_state())
    assert component.observed_queries == 0
    assert component.simulated_queries == 4
    assert any("Provenance" in reason for reason in component.lost_points)


# --------------------------------------------------------------- integrity ---


@pytest.mark.parametrize("key", list(CORE))
def test_core_scorers_are_deterministic(key: ScoreKey) -> None:
    """Repeated evaluation of the same state yields identical components."""
    first = CORE[key](rich_state())
    second = CORE[key](rich_state())
    assert first.model_dump() == second.model_dump()


def test_core_weight_tables_sum_to_one() -> None:
    """Every PRD §9.2 sub-score weight table is a valid probability distribution."""
    for name, table in ALL_WEIGHT_TABLES.items():
        assert table, name
        assert sum(table.values()) == pytest.approx(1.0), name
        assert all(0.0 < weight <= 1.0 for weight in table.values()), name


def test_eos_local_table_adds_local_relevance() -> None:
    """Local pages reallocate weight to a local_relevance dimension (PRD §9.2.A)."""
    assert "local_relevance" in EOS_LOCAL_WEIGHTS
    assert "local_relevance" not in EOS_WEIGHTS


def test_label_for_covers_every_core_and_optional_key() -> None:
    """``label_for`` gives a human label for all thirteen score keys."""
    for key in ScoreKey:
        label = label_for(key)
        assert label
        assert isinstance(label, str)


def test_component_value_rounds_to_one_decimal() -> None:
    """The component constructor rounds an in-range value to one decimal place."""
    assert ScoreComponent(score_key=ScoreKey.EOS, value=8.666_667).value == 8.7


def test_component_value_out_of_range_is_rejected() -> None:
    """The schema bound keeps a component value strictly on the 0–10 scale."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ScoreComponent(score_key=ScoreKey.EOS, value=42.0)
    with pytest.raises(ValidationError):
        ScoreComponent(score_key=ScoreKey.EOS, value=-3.0)


def test_component_unassessed_factory() -> None:
    """``ScoreComponent.unassessed`` marks the component and records the reason."""
    component = ScoreComponent.unassessed(ScoreKey.KGR, "Knowledge-Graph Readiness", "no data")
    assert component.value is None
    assert component.not_assessed is True
    assert component.not_applicable is False
    assert component.confidence is Confidence.NOT_ASSESSED
    assert component.lost_points == ["no data"]


def test_component_not_applicable_has_no_lost_points() -> None:
    """A not-applicable component is not a failure, so it carries no lost points."""
    component = ScoreComponent.unassessed(
        ScoreKey.LOCAL_FIT, "Local Fit", "does not apply", not_applicable=True
    )
    assert component.not_applicable is True
    assert component.lost_points == []


def test_component_intent_evidence_uses_intent_kinds() -> None:
    """A rich commercial state still assesses INTENT's declared-intent sub-score."""
    from ega_scoring.optional import compute_intent

    component = compute_intent(rich_state())
    assert component.assessed is True
    assert component.sub_scores["declared_intent_fit"] == 10.0


def test_local_service_eos_uses_local_weight_table() -> None:
    """A local_service page is scored with the local EOS weight table."""
    state = rich_state(page_type=PageType.LOCAL_SERVICE)
    component = compute_eos(state)
    assert "local_relevance" in component.sub_weights
    assert component.sub_weights["local_relevance"] > 0.0


def test_eav_not_applicable_rows_are_excluded_from_eos_completeness() -> None:
    """NOT_APPLICABLE attribute rows never dilute the attribute-completeness sub-score."""
    state = rich_state()
    state.eav_rows = [
        *state.eav_rows,
        type(state.eav_rows[0])(
            eav_id="eav-na",
            entity_name="Acme Analytics Engine",
            attribute="obsolete_field",
            status=EAVStatus.NOT_APPLICABLE,
        ),
    ]
    # Adding a not-applicable row must not change the component value.
    assert compute_eos(state).value == compute_eos(rich_state()).value
