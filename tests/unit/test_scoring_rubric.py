"""Unit tests for the scoring rubric primitives (PRD §9.1).

These are the pure building blocks every component uses: clamping to one
decimal, "not assessable" ratios, confidence from observation counts, and the
scale anchors. They must be deterministic and must never turn "not applicable"
into zero.
"""

from __future__ import annotations

import pytest
from ega_schemas.enums import Confidence
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

# ------------------------------------------------------------------ clamp ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(3.14, 3.1), (3.16, 3.2), (0.0, 0.0), (10.0, 10.0), (-3.0, 0.0), (42.0, 10.0)],
)
def test_clamp_bounds_and_rounds_to_one_decimal(raw: float, expected: float) -> None:
    """Scores are clamped to 0–10 and rounded to one decimal place (PRD §9.1)."""
    assert clamp(raw) == expected


def test_clamp_respects_custom_bounds() -> None:
    """Callers can clamp into a narrower range without changing the rounding."""
    assert clamp(5.0, 2.0, 4.0) == 4.0
    assert clamp(1.0, 2.0, 4.0) == 2.0


# ---------------------------------------------------------- weighted_ratio ---


def test_weighted_ratio_divides_when_denominator_present() -> None:
    assert weighted_ratio(3.0, 6.0) == pytest.approx(0.5)


def test_weighted_ratio_returns_none_for_zero_denominator() -> None:
    """A zero denominator is "not assessable", never a zero score (PRD §9.1)."""
    assert weighted_ratio(3.0, 0.0) is None
    assert weighted_ratio(0.0, 0.0) is None


# ------------------------------------------------------------------- mean ---


def test_mean_of_values_and_empty() -> None:
    assert mean([2.0, 4.0, 6.0]) == pytest.approx(4.0)
    assert mean([]) is None


# --------------------------------------------------------- confidence math ---


@pytest.mark.parametrize(
    ("observations", "expected"),
    [(0, Confidence.LOW), (3, Confidence.LOW), (4, Confidence.MEDIUM), (7, Confidence.MEDIUM), (8, Confidence.HIGH), (50, Confidence.HIGH)],
)
def test_confidence_for_thresholds(observations: int, expected: Confidence) -> None:
    """≥8 observations is high, ≥4 medium, otherwise low (PRD §9.5)."""
    assert confidence_for(observations) is expected


def test_confidence_min_is_worst_case() -> None:
    """Aggregated confidence reports the weakest contributor."""
    assert confidence_min([Confidence.HIGH, Confidence.MEDIUM]) is Confidence.MEDIUM
    assert confidence_min([Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW]) is Confidence.LOW
    assert confidence_min([Confidence.HIGH, Confidence.HIGH]) is Confidence.HIGH


# --------------------------------------------------------------- anchors ---


def test_anchors_cover_the_full_scale_without_gaps() -> None:
    """The eight anchor bands tile [0, 10] in ascending order (PRD §9.1)."""
    assert len(ANCHORS) == 8
    assert ANCHORS[0][0] == 0.0
    assert ANCHORS[-1][1] == 10.0
    for (_, high, _), (low, _, _) in zip(ANCHORS, ANCHORS[1:], strict=False):
        assert low > high  # bands are strictly ordered with no overlap
    assert all(low <= high for low, high, _ in ANCHORS)


@pytest.mark.parametrize(
    ("value", "fragment"),
    [
        (None, "not assessed"),
        (0.0, "absent or fundamentally failing"),
        (3.0, "severe gaps"),
        (5.5, "incomplete/weak"),
        (6.5, "adequate but materially limited"),
        (7.5, "good with clear gaps"),
        (8.5, "strong"),
        (9.2, "excellent with only narrow gaps"),
        (9.8, "exceptional"),
    ],
)
def test_anchor_for_maps_values_to_labels(value, fragment: str) -> None:
    """``anchor_for`` returns the PRD §9.1 band label, or a not-assessed reason."""
    assert fragment in anchor_for(value)


def test_anchor_for_rounds_before_banding() -> None:
    """A raw 8.96 rounds to 9.0 and lands in the excellent band."""
    assert "excellent" in anchor_for(8.96)


# ------------------------------------------------------- version/disclaimer ---


def test_profile_version_and_disclaimer_are_present() -> None:
    """Composite profiles are versioned and always carry the heuristic disclaimer."""
    assert PROFILE_VERSION == "1.0"
    assert "heuristic" in SCORE_HEURISTIC_DISCLAIMER.lower()
    assert heuristic_disclaimer() == SCORE_HEURISTIC_DISCLAIMER
    assert "not an official" in heuristic_disclaimer()
