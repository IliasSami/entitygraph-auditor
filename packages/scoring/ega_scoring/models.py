"""Rich score component models used by the deterministic engine.

The schema package exposes ``ComponentScore`` (always 0–10) for report output;
the engine additionally needs to express *not assessed* and *not applicable*
states, sub-score weights, and observation counts. ``ScoreComponent`` adds
those; ``Scorecard`` extends the schema scorecard with the rich components and
the score-profile version, while remaining an ``ega_schemas.Scorecard`` so it
plugs straight into ``AuditRunState``/``AuditReport``.
"""

from __future__ import annotations

from typing import Optional

from ega_schemas.enums import Confidence, ScoreKey
from ega_schemas.scores import ComponentScore
from ega_schemas.scores import GateResult as _SchemaGateResult
from ega_schemas.scores import Scorecard as _SchemaScorecard
from pydantic import BaseModel, Field

from ega_scoring.rubric import SCORE_HEURISTIC_DISCLAIMER, clamp, confidence_min


class ScoreComponent(BaseModel):
    """0–10 heuristic component with full epistemology (PRD §9.1).

    ``value=None`` together with ``not_assessed=True`` marks a component that
    could not be evaluated from the available run state; such components are
    never coerced to zero and are excluded from the composite denominator.
    """

    score_key: ScoreKey
    label: str = ""
    value: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    not_assessed: bool = False
    not_applicable: bool = False
    weight: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    sub_scores: dict[str, float] = Field(default_factory=dict)
    sub_weights: dict[str, float] = Field(default_factory=dict)
    renormalized: bool = False
    lost_points: list[str] = Field(default_factory=list)
    rationale: str = ""
    confidence: Confidence = Confidence.MEDIUM
    observations: int = 0
    observed_queries: Optional[int] = None
    simulated_queries: Optional[int] = None
    notes: list[str] = Field(default_factory=list)

    def __init__(self, /, **data: object) -> None:
        super().__init__(**data)
        if not self.label:
            self.label = self.score_key.value
        if self.value is not None:
            self.value = clamp(float(self.value))  # type: ignore[arg-type]

    # -- constructors ------------------------------------------------------
    @classmethod
    def unassessed(
        cls,
        score_key: ScoreKey,
        label: str,
        reason: str,
        weight: Optional[float] = None,
        observations: int = 0,
        not_applicable: bool = False,
        observed_queries: Optional[int] = None,
        simulated_queries: Optional[int] = None,
    ) -> "ScoreComponent":
        """Build a not-assessed (or not-applicable) component with its reason."""
        return cls(
            score_key=score_key,
            label=label,
            value=None,
            not_assessed=True,
            not_applicable=not_applicable,
            weight=weight,
            rationale=reason,
            confidence=Confidence.NOT_ASSESSED,
            observations=observations,
            observed_queries=observed_queries,
            simulated_queries=simulated_queries,
            lost_points=[] if not_applicable else [reason],
        )

    # -- helpers -----------------------------------------------------------
    @property
    def assessed(self) -> bool:
        """True when the component carries an actual value."""
        return self.value is not None and not self.not_assessed

    def to_component_score(self) -> Optional[ComponentScore]:
        """Convert to the schema ``ComponentScore`` (None when not assessed)."""
        if not self.assessed:
            return None
        return ComponentScore(
            score_key=self.score_key,
            value=float(self.value),  # type: ignore[arg-type]
            weight=float(self.weight or 0.0),
            confidence=self.confidence,
            rationale=self.rationale,
            sub_scores={k: clamp(v) for k, v in self.sub_scores.items()},
            lost_points_reasons=self.lost_points,
            observed_queries=self.observed_queries,
            simulated_queries=self.simulated_queries,
        )


class GateResult(_SchemaGateResult):
    """Schema gate result (status, issue lists, publishable, rationale).

    Kept as a distinct class so ``ega_scoring.models.GateResult`` remains a
    stable import for callers even if the schema module is refactored again.
    """


class Scorecard(_SchemaScorecard):
    """Schema scorecard extended with rich components and score-profile version.

    ``components`` holds the rich :class:`ScoreComponent` objects (including
    not-assessed ones) while the inherited ``scores`` map is derived from the
    assessed components as schema ``ComponentScore`` objects.
    """

    components: dict[str, ScoreComponent] = Field(default_factory=dict)
    renormalized: bool = False

    def model_post_init(self, __context: object) -> None:
        """Derive ``scores``/``composite`` from the assessed rich components.

        This deliberately replaces the base-class fallback, which would have
        copied the rich components straight into the schema ``scores`` map
        (breaking its 0–10 contract) whenever no schema scores were supplied.
        """
        schema_scores: dict[str, ComponentScore] = {}
        for name, component in self.components.items():
            converted = component.to_component_score()
            if converted is not None:
                schema_scores[name] = converted
        if schema_scores or not self.scores:
            self.scores = schema_scores
        if self.composite is None:
            self.composite = self.scores.get(ScoreKey.AVR.value)

    def component(self, key: "ScoreKey | str") -> Optional[ScoreComponent]:
        """Fetch a rich component by enum or string key."""
        name = key.value if isinstance(key, ScoreKey) else key
        return self.components.get(name)


def combine_sub_scores(
    sub_scores: dict[str, float],
    sub_weights: dict[str, float],
    *,
    floor: float = 0.0,
    cap: float = 10.0,
) -> tuple[Optional[float], bool, dict[str, float]]:
    """Combine sub-scores over the weights of the *included* sub-scores.

    Sub-scores absent from ``sub_scores`` are treated as not applicable and
    excluded; the remaining weights are re-normalized to sum to 1 (PRD §9.4:
    never silently count N/A as zero). Returns
    ``(value, re-normalized, used_weights)``. Value is ``None`` when no
    sub-score carries any weight.
    """
    used = {k: w for k, w in sub_weights.items() if k in sub_scores and w > 0}
    total = sum(used.values())
    if total <= 0:
        return None, False, {}
    re_normalized = abs(total - 1.0) > 1e-9
    weighted = sum(sub_scores[k] * (w / total) for k, w in used.items())
    return clamp(weighted, floor, cap), re_normalized, {k: round(w / total, 4) for k, w in used.items()}


def overall_confidence(components: list[ScoreComponent]) -> Confidence:
    """Aggregate component confidences: worst of the assessed components."""
    confidences = [c.confidence for c in components if c.assessed]
    if not confidences:
        return Confidence.NOT_ASSESSED
    return confidence_min(confidences)


__all__ = [
    "GateResult",
    "SCORE_HEURISTIC_DISCLAIMER",
    "ScoreComponent",
    "Scorecard",
    "combine_sub_scores",
    "overall_confidence",
]
