"""Integration tests for the public scoring API (PRD §9).

``run_gate_and_scores`` is the one-call entry point: it evaluates the gate once
and injects the very same result into the scorecard, so the report cannot show a
gate and a score computed from inconsistent state. These tests also lock the
legacy ``ScoringEngine`` facade (``evaluate`` / ``generate_swot`` /
``prioritize_findings``) and the profile weight helpers, plus the rule that
"not applicable" never becomes zero anywhere in the assembled report.
"""

from __future__ import annotations

import pytest
from ega_schemas.enums import GateStatus, PageType, ScoreKey
from ega_schemas.report import SwotAnalysis
from ega_schemas.scores import ComponentScore
from ega_scoring import (
    PAGE_TYPE_WEIGHTS,
    ScoringEngine,
    compute_all_scores,
    evaluate_gate,
    get_profile_weights,
    run_gate_and_scores,
)
from ega_scoring.composite import CORE_COMPONENT_ORDER
from ega_scoring.models import ScoreComponent
from ega_scoring.rubric import SCORE_HEURISTIC_DISCLAIMER
from test_scoring_fixtures import brand_pack, build_finding, empty_state, rich_state

ALL_PRESETS = ("informational", "listicle", "commercial", "case_study")


# ------------------------------------------------------ run_gate_and_scores --


def test_run_gate_and_scores_rich_state_pair() -> None:
    """Gate and scorecard are evaluated together and stay consistent."""
    gate, card = run_gate_and_scores(rich_state())
    assert gate.status is GateStatus.PASS
    assert gate.publishable is True
    assert card.gate is gate
    assert card.gate.status is GateStatus.PASS
    assert card.avr == 6.9


def test_run_gate_and_scores_empty_state_pair() -> None:
    """An empty run still yields a coherent (un-assessed) pair."""
    gate, card = run_gate_and_scores(empty_state())
    assert gate.status is GateStatus.NOT_CONFIGURED
    assert card.gate is gate
    assert card.avr is None
    assert card.scores == {}


def test_run_gate_and_scores_is_deterministic() -> None:
    """Calling the public API twice yields identical documents."""
    first = run_gate_and_scores(rich_state())
    second = run_gate_and_scores(rich_state())
    assert first[0].model_dump() == second[0].model_dump()
    assert first[1].model_dump() == second[1].model_dump()


def test_evaluate_gate_matches_run_gate_and_scores() -> None:
    """The gate in the scorecard is exactly what ``evaluate_gate`` returns."""
    gate, card = run_gate_and_scores(rich_state())
    assert evaluate_gate(rich_state()).model_dump() == gate.model_dump()
    assert card.gate.model_dump() == gate.model_dump()


# ------------------------------------------------------- report invariants ---


def test_scores_map_holds_schema_component_scores() -> None:
    """``scores`` carries schema ``ComponentScore`` (0–10), not rich components."""
    card = compute_all_scores(rich_state())
    for name, score in card.scores.items():
        assert isinstance(score, ComponentScore), name
        assert not isinstance(score, ScoreComponent), name
        assert 0.0 <= score.value <= 10.0, name


def test_not_applicable_never_becomes_zero_in_report() -> None:
    """N/A optional profiles are absent from ``scores`` — never a 0.0 entry."""
    card = compute_all_scores(rich_state())
    assert "LOCAL_FIT" not in card.scores
    assert "PAID_FIT" not in card.scores
    # ...and present as explicit N/A rich components.
    assert card.components["LOCAL_FIT"].not_applicable is True
    assert card.components["PAID_FIT"].not_applicable is True


def test_report_carries_the_heuristic_disclaimer() -> None:
    """Every scorecard is labelled an internal editorial heuristic (PRD §24)."""
    card = compute_all_scores(rich_state())
    assert "heuristic" in card.warning.lower()
    assert "heuristic" in card.disclaimer.lower()
    assert SCORE_HEURISTIC_DISCLAIMER.split(" — ")[0].lower() in card.warning.lower()


def test_report_confidence_reflects_assessed_components() -> None:
    """A rich run reports real confidence; an empty run reports not-assessed."""
    assert compute_all_scores(rich_state()).confidence.value in {"high", "medium", "low"}
    assert compute_all_scores(empty_state()).confidence.value == "not_assessed"


# ---------------------------------------------------------- ScoringEngine ----


def test_scoring_engine_evaluate_full_run() -> None:
    """The legacy facade builds a full scorecard from schema lists."""
    state = rich_state()
    card = ScoringEngine.evaluate(
        entities=state.entities,
        eav_rows=state.eav_rows,
        triples=state.triples,
        fanout_queries=state.fanout_queries,
        coverage_rows=state.coverage_rows,
        claims=state.claims,
        parsed_doc=state.parsed_doc,
        page_type=PageType.SERVICE,
        context_packs=[brand_pack()],
    )
    assert card.gate.status is GateStatus.PASS
    assert card.avr is not None and card.avr > 0.0
    assert card.scores[ScoreKey.EOS.value].value > 6.0


def test_scoring_engine_evaluate_detects_compliance_failure() -> None:
    """The facade surfaces forbidden-claim triggers as a failing gate."""
    from ega_parsers import DocumentParser
    from ega_schemas.claims import Claim
    from ega_schemas.enums import ClaimRiskTier, VerificationState

    claim = Claim(
        claim_id="c1",
        statement="This secret herb 100% cures cancer without chemotherapy.",
        risk_tier=ClaimRiskTier.HIGH_STAKES,
        verification_state=VerificationState.UNVERIFIED,
        requires_substantiation=True,
    )
    doc = DocumentParser.parse("This secret herb 100% cures cancer without chemotherapy.")
    card = ScoringEngine.evaluate(
        entities=[],
        eav_rows=[],
        triples=[],
        fanout_queries=[],
        coverage_rows=[],
        claims=[claim],
        parsed_doc=doc,
    )
    assert card.gate.status is GateStatus.FAIL
    assert card.gate.publishable is False


def test_generate_swot_returns_all_sections() -> None:
    """SWOT synthesis yields non-empty sections for a rich scorecard."""
    card = compute_all_scores(rich_state())
    swot = ScoringEngine.generate_swot(card)
    assert isinstance(swot, SwotAnalysis)
    assert swot.strengths and swot.weaknesses and swot.opportunities and swot.threats
    assert all(isinstance(item, str) for item in swot.strengths)


def test_generate_swot_reports_gate_threats_when_failing() -> None:
    """A failing gate shows up as a threat in the SWOT."""
    failing = compute_all_scores(
        rich_state(content="We are 100% guaranteed to cure everyone.", parsed_doc=None)
    )
    swot = ScoringEngine.generate_swot(failing)
    assert any("Gate Threat" in item for item in swot.threats)


def test_prioritize_findings_uses_gate_override() -> None:
    """The facade uses the shared PRD §9.6 ordering with the gate override."""
    findings = [
        build_finding("low", severity="low", impact=2, confidence_numeric=3, effort=5),
        build_finding("crit", severity="critical", status="open", impact=1, confidence_numeric=1, effort=5),
        build_finding("high", severity="high", impact=5, confidence_numeric=5, effort=1),
    ]
    ordered = ScoringEngine.prioritize_findings(findings)
    assert [f.finding_id for f in ordered] == ["crit", "high", "low"]


# --------------------------------------------------------- profile helpers ---


def test_get_profile_weights_for_service_page() -> None:
    preset, weights = get_profile_weights(PageType.SERVICE)
    assert preset == "commercial"
    assert weights[ScoreKey.CWS] == 15.0
    assert weights[ScoreKey.FCS] == 10.0
    assert sum(weights.values()) == pytest.approx(100.0)


def test_page_type_weights_cover_all_presets() -> None:
    """The legacy percentage table exposes all four PRD §9.4 presets."""
    assert set(PAGE_TYPE_WEIGHTS) == set(ALL_PRESETS)
    for preset in ALL_PRESETS:
        table = PAGE_TYPE_WEIGHTS[preset]
        assert set(table) == set(CORE_COMPONENT_ORDER)
        assert sum(table.values()) == pytest.approx(100.0)


def test_profile_override_reaches_the_scorecard() -> None:
    """A user override reaches both the preset and the printed profile name."""
    card = compute_all_scores(rich_state(score_profile="case_study"))
    assert card.profile == "case_study"
    assert card.profile_name == "case_study"


def test_public_api_entry_points_are_exported() -> None:
    """The documented public API is importable from the package root."""
    import ega_scoring as pkg

    for name in (
        "compute_all_scores",
        "evaluate_gate",
        "run_gate_and_scores",
        "build_scorecard",
        "compute_avr",
        "ScoringEngine",
    ):
        assert hasattr(pkg, name), name
    assert callable(pkg.compute_all_scores)
    assert callable(pkg.run_gate_and_scores)
