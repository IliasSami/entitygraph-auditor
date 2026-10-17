"""Unit tests for the optional profile scores (PRD §9.3).

Optional scores sit *beside* the composite. The PRD's key invariants are locked
here: every optional component carries ``weight=None`` (it can never move the
composite), it discloses :data:`OPTIONAL_DISCLAIMER`, a page the profile does not
apply to is reported as **N/A (never 0)**, and missing inputs are not-assessed
rather than zero.
"""

from __future__ import annotations

import pytest
from ega_schemas.enums import PageType, ScoreKey
from ega_scoring.models import ScoreComponent
from ega_scoring.optional import (
    CONVERSION_WEIGHTS,
    INTENT_WEIGHTS,
    LINKS_WEIGHTS,
    LOCAL_FIT_WEIGHTS,
    OPTIONAL_DISCLAIMER,
    PAID_FIT_WEIGHTS,
    TRUST_WEIGHTS,
    compute_conversion,
    compute_intent,
    compute_internal_links,
    compute_local_fit,
    compute_paid_fit,
    compute_trust,
)
from test_scoring_fixtures import empty_state, rich_state

OPTIONAL = {
    ScoreKey.INTENT: compute_intent,
    ScoreKey.LOCAL_FIT: compute_local_fit,
    ScoreKey.PAID_FIT: compute_paid_fit,
    ScoreKey.CONVERSION: compute_conversion,
    ScoreKey.TRUST: compute_trust,
    ScoreKey.LINKS: compute_internal_links,
}

ALL_OPTIONAL_WEIGHTS = {
    "INTENT": INTENT_WEIGHTS,
    "LOCAL_FIT": LOCAL_FIT_WEIGHTS,
    "PAID_FIT": PAID_FIT_WEIGHTS,
    "CONVERSION": CONVERSION_WEIGHTS,
    "TRUST": TRUST_WEIGHTS,
    "LINKS": LINKS_WEIGHTS,
}


def test_optional_weight_tables_sum_to_one() -> None:
    """Each optional sub-score weight table is a proper distribution (PRD §9.3)."""
    for name, table in ALL_OPTIONAL_WEIGHTS.items():
        assert table, name
        assert sum(table.values()) == pytest.approx(1.0), name


def test_rich_state_optional_values() -> None:
    """The rich fixture scores five optional profiles and marks two N/A."""
    assert compute_intent(rich_state()).value == 8.7
    assert compute_conversion(rich_state()).value == 9.0
    assert compute_trust(rich_state()).value == 9.2
    assert compute_internal_links(rich_state()).value == 10.0
    assert compute_local_fit(rich_state()).not_applicable is True
    assert compute_paid_fit(rich_state()).not_applicable is True


@pytest.mark.parametrize("key", list(OPTIONAL))
def test_optional_components_carry_no_composite_weight(key: ScoreKey) -> None:
    """No optional score ever gets a weight — they stay outside the composite."""
    for state in (rich_state(), empty_state()):
        assert OPTIONAL[key](state).weight is None


@pytest.mark.parametrize("key", list(OPTIONAL))
def test_optional_scorers_are_deterministic(key: ScoreKey) -> None:
    """Optional scorers are pure functions of the state."""
    assert OPTIONAL[key](rich_state()).model_dump() == OPTIONAL[key](
        rich_state()
    ).model_dump()


def test_not_applicable_is_none_and_disclosed() -> None:
    """N/A is ``value=None`` + ``not_applicable`` + a stated reason — never 0."""
    component = compute_local_fit(rich_state())
    assert component.value is None
    assert component.not_assessed is True
    assert component.not_applicable is True
    assert component.lost_points == []  # N/A is not a failure
    assert "does not apply" in component.rationale
    assert component.confidence.value == "not_assessed"


def test_local_fit_applies_to_a_local_service_page() -> None:
    """Local Fit is assessed when the page profile is location-relevant (FR-12)."""
    component = compute_local_fit(rich_state(page_type=PageType.LOCAL_SERVICE))
    assert component.not_applicable is False
    assert component.assessed is True
    assert component.value is not None


def test_local_fit_applies_with_a_location_target() -> None:
    """A configured location target alone makes Local Fit applicable."""
    component = compute_local_fit(rich_state(location_target="Berlin"))
    assert component.not_applicable is False


def test_paid_fit_applies_to_a_paid_landing_page() -> None:
    """Paid Landing Page Fit is only assessed for ``paid_landing`` pages (FR-13)."""
    component = compute_paid_fit(rich_state(page_type=PageType.PAID_LANDING))
    assert component.not_applicable is False
    assert component.assessed is True


def test_paid_fit_is_na_for_a_service_page() -> None:
    """PAID_FIT reports N/A for every other page type."""
    component = compute_paid_fit(rich_state(page_type=PageType.SERVICE))
    assert component.not_applicable is True
    assert "paid_landing" in component.rationale


def test_conversion_is_na_for_informational_profiles() -> None:
    """Conversion Readiness does not apply to informational pages (PRD §9.3)."""
    component = compute_conversion(empty_state(page_type=PageType.ARTICLE))
    assert component.not_applicable is True
    assert component.value is None


def test_conversion_is_assessed_for_commercial_pages() -> None:
    """A commercial page with a conversion expectation gets a real score."""
    component = compute_conversion(rich_state())
    assert component.not_applicable is False
    assert component.value is not None


def test_optional_disclaimer_is_disclosed() -> None:
    """Assessed optional scores disclose they are not part of the composite."""
    component = compute_intent(rich_state())
    assert OPTIONAL_DISCLAIMER in component.rationale
    assert "never folded" in OPTIONAL_DISCLAIMER


def test_empty_state_optional_scorers_are_not_zero() -> None:
    """With no inputs an optional scorer is unassessed, not a 0.0."""
    for key in (ScoreKey.INTENT, ScoreKey.TRUST, ScoreKey.LINKS):
        component = OPTIONAL[key](empty_state())
        assert component.value is None
        assert component.not_assessed is True
        assert component.not_applicable is False


def test_unassessed_optional_scores_are_explicit_reasons() -> None:
    """Every unassessed optional scorer states why it could not be evaluated."""
    component = compute_intent(empty_state())
    assert isinstance(component, ScoreComponent)
    assert "intent" in component.rationale.lower()


def test_optional_scorers_never_raise_on_bare_state() -> None:
    """A truly empty state never crashes any optional scorer."""
    for key in OPTIONAL:
        assert OPTIONAL[key](empty_state()) is not None
