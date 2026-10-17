"""Scoring and Rubric contracts per PRD §9."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from ega_schemas.enums import Confidence, GateStatus, ScoreKey


class ComponentScore(BaseModel):
    """0-10 Heuristic component score with full epistemological rationale."""

    score_key: Optional[ScoreKey | str] = None
    key: Optional[str] = None
    label: Optional[str] = None
    value: Optional[float] = Field(default=None, ge=0.0, le=10.0, description="0.0 - 10.0 rating")
    weight: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Percentage weight in composite")

    confidence: Confidence = Confidence.MEDIUM
    rationale: str = ""
    sub_scores: dict[str, float] = Field(default_factory=dict)
    lost_points_reasons: list[str] = Field(default_factory=list)
    observed_queries: Optional[int] = None
    simulated_queries: Optional[int] = None


ScoreComponent = ComponentScore


class GateIssue(BaseModel):
    """Gate failure or warning issue."""

    category: str = "compliance"
    severity: str = "critical"
    message: str = ""
    rule_id: Optional[str] = None
    issue_id: Optional[str] = None
    title: Optional[str] = None
    detail: Optional[str] = None


class GateResult(BaseModel):
    """Brand, Claim, and Compliance Gate Result (PRD §9.5)."""

    status: GateStatus = GateStatus.NOT_CONFIGURED
    critical_issues: list[str | GateIssue] = Field(default_factory=list)
    noncritical_issues: list[str | GateIssue] = Field(default_factory=list)
    publishable: bool = True
    rationale: str = ""



class Scorecard(BaseModel):
    """Complete score breakdown with component scores and composite AVR."""

    scores: dict[str, ComponentScore] = Field(default_factory=dict)
    components: dict[str, ComponentScore] = Field(default_factory=dict)
    gate: GateResult = Field(default_factory=GateResult)
    avr: Optional[float] = Field(default=None, description="Composite AI Visibility Readiness (0-10)")
    composite: Optional[ComponentScore] = None
    profile: str = "default"
    profile_name: str = "default"
    profile_version: str = "1.0"
    renormalized: Optional[bool] = None
    confidence: Confidence = Confidence.MEDIUM
    warning: str = "Internal editorial heuristic — not an official Google, Bing, OpenAI, Anthropic, or Perplexity metric."
    disclaimer: str = "All scores are internal editorial heuristics, never search-engine platform ranking guarantees."

    def model_post_init(self, __context: Any) -> None:
        if not self.components and self.scores:
            self.components = dict(self.scores)
        elif not self.scores and self.components:
            self.scores = dict(self.components)

    def items(self):
        return (self.scores or self.components).items()

    def values(self):
        return self.scores.values()

    def keys(self):
        return self.scores.keys()

    def get(self, key, default=None):
        return self.scores.get(key, default)

    def __iter__(self):
        return iter(self.scores)

    def __getitem__(self, item):
        return self.scores[item]


class ScoreProfile(BaseModel):
    """Profile-specific weighting for composite AVR (PRD §9.4)."""

    profile_name: str
    weights: dict[str, float] = Field(default_factory=dict)
    description: str = ""
