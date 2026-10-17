"""Scoring rubric primitives (PRD §9.1).

Everything in this module is deterministic and pure: scale anchors, clamping,
weighted ratios, confidence derivation from observation counts, and the
standing disclaimer that scores are internal editorial heuristics.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Optional, Sequence

from ega_schemas.enums import Confidence

#: Score-profile version stamped on every composite (PRD §9.4 "profiles must be versioned").
PROFILE_VERSION = "1.0"

#: Standing disclaimer shown beside every score (PRD §9.1/§24: never present
#: heuristic numbers as official platform metrics).
SCORE_HEURISTIC_DISCLAIMER = (
    "Internal editorial heuristic — not an official Google, Bing, OpenAI, "
    "Anthropic, or Perplexity metric."
)

#: 0–10 scale anchors from PRD §9.1.
ANCHORS: tuple[tuple[float, float, str], ...] = (
    (0.0, 1.9, "absent or fundamentally failing"),
    (2.0, 3.9, "severe gaps"),
    (4.0, 5.9, "incomplete/weak"),
    (6.0, 6.9, "adequate but materially limited"),
    (7.0, 7.9, "good with clear gaps"),
    (8.0, 8.9, "strong"),
    (9.0, 9.5, "excellent with only narrow gaps"),
    (9.6, 10.0, "exceptional; use very sparingly and only with evidence"),
)

def clamp(value: float, lo: float = 0.0, hi: float = 10.0) -> float:
    """Clamp a raw score into [lo, hi] and round to one decimal place (PRD §9.5)."""
    val = max(lo, min(hi, float(value)))
    return float(Decimal(str(val)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def weighted_ratio(numerator: float, denominator: float) -> Optional[float]:
    """Return ``numerator / denominator`` or ``None`` when the denominator is 0.

    ``None`` means "not assessable" — callers must never coerce it to zero
    (PRD §9.1: "Not applicable" is not zero).
    """
    if not denominator:
        return None
    return float(numerator) / float(denominator)


def mean(values: Sequence[float]) -> Optional[float]:
    """Arithmetic mean of a non-empty sequence, else ``None``."""
    if not values:
        return None
    return sum(values) / len(values)


def confidence_for(observations: int) -> Confidence:
    """Confidence from observation counts: ≥8 high, ≥4 medium, else low (PRD §9.5)."""
    if observations >= 8:
        return Confidence.HIGH
    if observations >= 4:
        return Confidence.MEDIUM
    return Confidence.LOW


def confidence_min(values: Iterable[Confidence]) -> Confidence:
    """The lowest confidence among the given values (worst-case reporting)."""
    order = [Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW, Confidence.NOT_ASSESSED]
    worst = Confidence.HIGH
    for value in values:
        if order.index(value) > order.index(worst):
            worst = value
    return worst


def anchor_for(value: Optional[float]) -> str:
    """Human-readable anchor label for a value, or why it was not assessed."""
    if value is None:
        return "not assessed — insufficient evidence"
    clamped = clamp(value)
    for low, high, label in ANCHORS:
        if low <= clamped <= high:
            return f"{clamped} → {label}"
    return f"{clamped} → unanchored"


def heuristic_disclaimer() -> str:
    """The standing editorial-heuristic disclaimer text."""
    return SCORE_HEURISTIC_DISCLAIMER
