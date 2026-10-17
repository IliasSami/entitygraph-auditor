"""Finding and Recommendation contracts per PRD §21."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ega_schemas.enums import Confidence, RecommendationStatus, Severity


class FindingWhere(BaseModel):
    """Exact spatial anchor within the audited document."""

    section_id: Optional[str] = None
    passage_id: Optional[str] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    excerpt: Optional[str] = None


class FindingWhy(BaseModel):
    """Epistemological justification for the finding."""

    intent_or_query: Optional[str] = None
    layer: Optional[str] = None
    entity: Optional[str] = None
    attribute: Optional[str] = None
    eav_status: Optional[str] = None
    rule_id: Optional[str] = None


class FindingHow(BaseModel):
    """Prescriptive guidance for the writer / developer."""

    suggested_rewrite: Optional[str] = None
    verification_condition: Optional[str] = None
    implementation_steps: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    """Structured Finding Contract (PRD §21).

    Priority Formula: Priority = (Impact × ConfidenceNumeric) / Effort
    """

    finding_id: str
    category: str
    severity: Severity = Severity.MEDIUM
    title: str
    what: str
    where: Optional[FindingWhere] = None
    why: Optional[FindingWhy] = None
    how: Optional[FindingHow] = None
    evidence: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    impact: int = Field(ge=1, le=5, default=3, description="1-5 rating of search/user impact")
    confidence_numeric: int = Field(ge=1, le=5, default=4, description="1-5 rating of analytical certainty")
    effort: int = Field(ge=1, le=5, default=2, description="1-5 rating of editorial effort to resolve")
    priority_score: float = Field(default=6.0, description="(Impact × ConfidenceNumeric) / Effort")
    status: RecommendationStatus = RecommendationStatus.OPEN

    def calculate_priority(self) -> float:
        """Compute priority score using the PRD §9.6 formula."""
        effort_val = max(1, self.effort)
        score = (float(self.impact) * float(self.confidence_numeric)) / float(effort_val)
        self.priority_score = round(score, 1)
        return self.priority_score


class Recommendation(Finding):
    """Alias for Finding for writer-handoffs."""
    pass


class Swot(BaseModel):
    """SWOT analysis of content performance."""

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)

