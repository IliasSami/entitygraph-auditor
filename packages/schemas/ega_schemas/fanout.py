"""Query Fan-out simulator and Coverage Matrix schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ega_schemas.enums import (
    AnswerShape,
    CoverageStatus,
    IntentClass,
    QueryOrigin,
    QueryScope,
    QuerySource,
)


class FanoutQuery(BaseModel):
    """Candidate or observed sub-query in the topical fan-out."""

    query_id: str
    query_text: str
    origin: QueryOrigin = QueryOrigin.SIMULATED
    source: QuerySource = QuerySource.GENERATED
    intent: IntentClass = IntentClass.INFORMATIONAL
    importance: int = Field(ge=1, le=3, default=2, description="3=Core, 2=Common follow-up, 1=Edge")
    answer_shape: AnswerShape = AnswerShape.DEFINITION
    scope: QueryScope = QueryScope.THIS_PAGE


class CoverageRow(BaseModel):
    """Evaluation of how well the page covers a fan-out query."""

    query_id: str
    query_text: str
    status: CoverageStatus = CoverageStatus.MISSING
    matched_passage_ids: list[str] = Field(default_factory=list)
    coverage_score: float = Field(ge=0.0, le=1.0, default=0.0)
    gap_reason: Optional[str] = None
    destination_page: Optional[str] = None
