"""Unit tests for the composite AVR and scorecard assembly (PRD §9.4).

The composite is where the PRD's two hard rules live:

* a weight table that always sums to 1.0, selected by page-type profile;
* *never silently count N/A as zero* — a missing component blocks the composite
  unless the narrow auto re-normalization (a single absent FCS) applies, or the
  caller explicitly forces a labelled reduced denominator.
"""

from __future__ import annotations

import pytest
from ega_schemas.enums import PageType, ScoreKey
from ega_schemas.scores import ComponentScore
from ega_scoring.composite import (
    AUTO_RENORMALIZABLE,
    CORE_COMPONENT_ORDER,
    MAX_AUTO_MISSING,
    OPTIONAL_COMPONENT_ORDER,
    build_scorecard,
    component_weights,
    compute_all_scores,
    compute_avr,
    compute_components,
    missing_components,
    resolve_preset,
)
from ega_scoring.models import Scorecard, combine_sub_scores, overall_confidence
from test_scoring_fixtures import empty_state, gate_state, rich_state

ALL_PRESETS = ("informational", "listicle", "commercial", "case_study")


# --------------------------------------------------------------- presets -----


def test_preset_resolves_from_page_type() -> None:
    """The page-type profile selects the AVR weight preset (PRD §9.4)."""
    assert resolve_preset(rich_state()) == "commercial"
    assert resolve_preset(empty_state(page_type=PageType.ARTICLE)) == "informational"
    assert resolve_preset(empty_state(page_type=PageType.LISTICLE)) == "listicle"
    assert resolve_preset(empty_state(page_type=PageType.CASE_STUDY)) == "case_study"


def test_score_profile_override_wins() -> None:
    """A user-supplied ``score_profile`` overrides the page-type preset."""
    state = rich_state(score_profile="informational")
    assert resolve_preset(state) == "informational"


def test_unknown_preset_override_raises() -> None:
    """An explicit but invalid preset is a programming error, not silence."""
    with pytest.raises(ValueError, match="Unknown score preset"):
        resolve_preset(rich_state(score_profile="bogus"))


@pytest.mark.parametrize("preset", ALL_PRESETS)
def test_component_weights_sum_to_100(preset: str) -> None:
    """Every preset's percentage weights sum to exactly 100."""
    state = rich_state(score_profile=preset)
    weights = component_weights(state)
    assert set(weights) == {key.value for key in CORE_COMPONENT_ORDER}
    assert sum(weights.values()) == pytest.approx(100.0)


def test_commercial_weight_table_is_the_prd_one() -> None:
    """The commercial preset carries the exact PRD §9.4 fractions."""
    assert component_weights(rich_state()) == {
        "EOS": 15.0,
        "ERS": 15.0,
        "KGR": 15.0,
        "FCS": 10.0,
        "PRS": 15.0,
        "CWS": 15.0,
        "HRS": 15.0,
    }


def test_case_study_weight_table_is_the_prd_one() -> None:
    """The case-study preset is CWS-heavy and FCS-light (PRD §9.4)."""
    assert component_weights(empty_state(page_type=PageType.CASE_STUDY)) == {
        "EOS": 10.0,
        "ERS": 15.0,
        "KGR": 10.0,
        "FCS": 5.0,
        "PRS": 10.0,
        "CWS": 35.0,
        "HRS": 15.0,
    }


# ------------------------------------------------------------------ AVR -----


def test_compute_avr_rich_state() -> None:
    """The fully-assessed rich state yields AVR 6.9 with no re-normalization."""
    components = compute_components(rich_state())
    avr = compute_avr(components, "commercial")
    assert avr.value == 6.9
    assert avr.renormalized is False
    assert avr.assessed is True
    assert set(avr.sub_weights) == {key.value for key in CORE_COMPONENT_ORDER}


def test_compute_avr_is_weighted_sum() -> None:
    """AVR equals the weighted sum over the preset fractions."""
    components = compute_components(rich_state())
    weights = {key: value / 100.0 for key, value in component_weights(rich_state()).items()}
    expected = sum(
        components[ScoreKey(name)].value * weights[name] for name in weights
    )
    assert compute_avr(components, "commercial").value == pytest.approx(round(expected, 1))


def test_compute_avr_auto_renormalizes_single_missing_fcs() -> None:
    """A lone absent FCS re-normalizes automatically and is labelled (PRD §9.4)."""
    components = {k: v for k, v in compute_components(rich_state()).items() if k is not ScoreKey.FCS}
    avr = compute_avr(components, "commercial")
    assert avr.value == 7.0
    assert avr.renormalized is True
    assert "FCS" not in avr.sub_weights
    assert any("Composite re-normalized because FCS" in reason for reason in avr.lost_points)
    assert "Modified denominator" in avr.rationale


def test_compute_avr_blocks_two_missing_components() -> None:
    """Two missing weighted components block the composite instead of counting zero."""
    components = {
        k: v
        for k, v in compute_components(rich_state()).items()
        if k not in (ScoreKey.ERS, ScoreKey.FCS)
    }
    avr = compute_avr(components, "commercial")
    assert avr.value is None
    assert avr.not_assessed is True
    assert "Composite blocked" in avr.rationale


def test_compute_avr_force_renormalize_overrides_block() -> None:
    """``force_renormalize`` computes over a labelled reduced denominator."""
    components = {
        k: v
        for k, v in compute_components(rich_state()).items()
        if k not in (ScoreKey.ERS, ScoreKey.FCS)
    }
    avr = compute_avr(components, "commercial", force_renormalize=True)
    assert avr.value == 7.3
    assert avr.renormalized is True


def test_compute_avr_without_any_assessed_component_is_not_assessed() -> None:
    """No assessable core component means no composite at all."""
    avr = compute_avr({}, "commercial")
    assert avr.value is None
    assert avr.not_assessed is True
    assert "No core component" in avr.rationale


def test_auto_renormalizable_is_only_fcs() -> None:
    """Only FCS is expected enough to auto re-normalize, and only one of it."""
    assert AUTO_RENORMALIZABLE == frozenset({ScoreKey.FCS})
    assert MAX_AUTO_MISSING == 1


def test_missing_components_lists_absent_weighted_keys() -> None:
    """``missing_components`` names the weighted keys that are not assessed."""
    assert missing_components(compute_components(rich_state()), "commercial") == []
    partial = {k: v for k, v in compute_components(rich_state()).items() if k is not ScoreKey.FCS}
    assert missing_components(partial, "commercial") == [ScoreKey.FCS]


# ------------------------------------------------------------- scorecard -----


def test_build_scorecard_assigns_weight_percentages() -> None:
    """Core components carry their profile weight as a percentage (PRD §9.4)."""
    card = compute_all_scores(rich_state())
    for name, percent in component_weights(rich_state()).items():
        component = card.component(name)
        assert component is not None
        assert component.weight == percent


def test_build_scorecard_optional_components_carry_no_weight() -> None:
    """PRD §9.3 optional components never carry a composite weight."""
    card = compute_all_scores(rich_state())
    for key in OPTIONAL_COMPONENT_ORDER:
        component = card.component(key)
        assert component is not None
        assert component.weight is None


def test_build_scorecard_avr_is_the_composite() -> None:
    """The scorecard surfaces AVR both as a component and as the composite."""
    card = compute_all_scores(rich_state())
    assert card.avr == 6.9
    assert card.composite is not None
    assert isinstance(card.composite, ComponentScore)
    assert card.composite.value == 6.9
    assert card.profile == "commercial"
    assert card.profile_name == "commercial"
    assert card.profile_version == "1.0"


def test_build_scorecard_excludes_not_assessed_from_scores() -> None:
    """Not-assessed / not-applicable components never appear in ``scores``."""
    card = compute_all_scores(rich_state())
    assert "LOCAL_FIT" not in card.scores
    assert "PAID_FIT" not in card.scores
    assert set(card.scores).issubset(set(card.components))
    assert all(0.0 <= score.value <= 10.0 for score in card.scores.values())


def test_not_applicable_is_never_zero() -> None:
    """N/A stays ``None`` in the rich components and never leaks as 0.0."""
    card = compute_all_scores(empty_state())
    assert card.avr is None
    assert card.scores == {}
    for component in card.components.values():
        assert component.value is None
        assert component.not_assessed is True
    assert card.components["LOCAL_FIT"].not_applicable is True


def test_empty_state_blocks_composite_but_keeps_components() -> None:
    """An empty run still returns every component key, all explicitly unassessed."""
    card = compute_all_scores(empty_state())
    assert "AVR" in card.components
    assert card.components["AVR"].not_assessed is True
    assert card.confidence.value == "not_assessed"


def test_build_scorecard_accepts_injected_gate() -> None:
    """A pre-evaluated gate is reused rather than re-run (single source of truth)."""
    from ega_schemas.enums import GateStatus
    from ega_scoring.gate import evaluate_gate

    # The rich state would gate PASS, but we inject the empty-state (NOT_CONFIGURED)
    # result and assert the scorecard reports exactly that — proving no re-run.
    injected = evaluate_gate(empty_state())
    card = build_scorecard(rich_state(), gate=injected)
    assert card.gate is injected
    assert card.gate.status is GateStatus.NOT_CONFIGURED


def test_include_optional_false_omits_optional_components() -> None:
    """``include_optional=False`` computes only the seven core components."""
    card = compute_all_scores(rich_state(), include_optional=False)
    for key in OPTIONAL_COMPONENT_ORDER:
        assert key.value not in card.components
    for key in CORE_COMPONENT_ORDER:
        assert key.value in card.components


def test_compute_all_scores_is_deterministic() -> None:
    """The full scorecard is a pure function of the run state."""
    first = compute_all_scores(rich_state())
    second = compute_all_scores(rich_state())
    assert first.model_dump() == second.model_dump()


def test_scorecard_component_helper() -> None:
    """``Scorecard.component`` resolves both enum and string keys."""
    card = compute_all_scores(rich_state())
    assert card.component(ScoreKey.EOS) is card.components["EOS"]
    assert card.component("EOS") is card.components["EOS"]
    assert card.component("NOT_A_KEY") is None


# ------------------------------------------------------------- primitives ----


def test_combine_sub_scores_renormalizes_included_weights() -> None:
    """Only included sub-scores count; their weights are re-normalized to 1."""
    value, re_normalized, used = combine_sub_scores({"a": 8.0}, {"a": 0.5, "b": 0.5})
    assert value == 8.0
    assert re_normalized is True
    assert used == {"a": 1.0}


def test_combine_sub_scores_without_any_weight_is_none() -> None:
    """No usable sub-score means not-assessable, never zero."""
    assert combine_sub_scores({}, {"a": 1.0}) == (None, False, {})


def test_overall_confidence_is_worst_assessed_component() -> None:
    """Aggregate confidence reports the weakest assessed component."""
    components = compute_components(rich_state())
    assert overall_confidence(list(components.values())) is not None
    assert overall_confidence([]).value == "not_assessed"


def test_scorecard_defaults_have_no_scores() -> None:
    """A hand-built scorecard starts empty and un-assessed."""
    card = Scorecard()
    assert card.scores == {}
    assert card.composite is None


def test_gate_state_is_usable_for_scorecard() -> None:
    """A minimal gate-only state still produces a coherent (empty) scorecard."""
    card = compute_all_scores(gate_state("just some text"))
    assert isinstance(card, Scorecard)
    assert card.avr is None
