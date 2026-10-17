"""Workspace read-model schemas (Entity Hub, Brief Builder, Optimizer).

These back the Aentio UI screens with **deterministic, provenance-labelled**
data derived from stored audits and context packs — no model call is required
and no value is fabricated. Every fact carries the source it came from so the
UI can render "where this came from" honestly (PRD "no hallucinated evidence").
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ------------------------------------------------------------------ entity hub


class EntityFact(BaseModel):
    """A single attribute-value assertion about an entity with provenance."""

    property: str
    value: str
    source: str
    date: str | None = None
    verified: bool = False


class EntitySourceRef(BaseModel):
    """A provenance reference for an entity (pack file, audit, etc.)."""

    title: str
    url: str | None = None


class WorkspaceEntity(BaseModel):
    """An entity in the project knowledge registry, merged from real sources."""

    entity_id: str
    canonical_id: str
    name: str
    kind: str = "Concept"  # display bucket: Organization|Service|Person|Place|Concept|Platform
    entity_kind: str = "other"  # raw EntityKind value
    aliases: list[str] = Field(default_factory=list)
    pages_used: int = 0
    facts_count: int = 0
    last_verified: str | None = None
    status: str = "healthy"  # healthy | conflict | needs_review
    conflict_detail: str | None = None
    definition: str = ""
    at_id: str = ""
    schema_type: str = "schema.org/Thing"
    facts: list[EntityFact] = Field(default_factory=list)
    sources: list[EntitySourceRef] = Field(default_factory=list)
    origins: list[str] = Field(default_factory=list)  # provenance labels


class WorkspaceEntitiesResponse(BaseModel):
    project_id: str | None = None
    entities: list[WorkspaceEntity] = Field(default_factory=list)
    generated_at: str = ""
    source_audits: int = 0
    source_packs: int = 0
    disclaimer: str = ""


# ---------------------------------------------------------------------- briefs


class BriefSourceItem(BaseModel):
    """A mined research input for a writer brief with explicit provenance."""

    id: str
    kind: str  # question | fact | gap
    title: str
    source: str
    tag: str
    provenance: str


class BriefEntityRef(BaseModel):
    name: str
    kind: str = "Concept"


class BriefSection(BaseModel):
    id: str
    h2_number: int
    title: str
    badge: str = "Answer"
    entities: list[BriefEntityRef] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    directive: str = ""
    word_range: str = "150–250 words"


class BriefConstraints(BaseModel):
    audience: str | None = None
    tone: str | None = None
    reading_level: str = "Grade 8–10 (Flesch-Kincaid)"
    intent: str | None = None


class BriefInformationGain(BaseModel):
    directive: str
    polarity: str = "do"  # do | avoid


class BriefBasis(BaseModel):
    audit_id: str | None = None
    audit_created_at: str | None = None
    context_pack_ids: list[str] = Field(default_factory=list)
    context_pack_versions: list[str] = Field(default_factory=list)


class BriefGenerateRequest(BaseModel):
    project_id: str
    target_query: str | None = None
    audit_id: str | None = None
    context_pack_ids: list[str] = Field(default_factory=list)
    max_sections: int = Field(default=6, ge=1, le=12)


class BriefResponse(BaseModel):
    project_id: str
    target_query: str
    sources: list[BriefSourceItem] = Field(default_factory=list)
    sections: list[BriefSection] = Field(default_factory=list)
    constraints: BriefConstraints = Field(default_factory=BriefConstraints)
    information_gain: list[BriefInformationGain] = Field(default_factory=list)
    basis: BriefBasis = Field(default_factory=BriefBasis)
    generated_at: str = ""
    disclaimer: str = ""


# ------------------------------------------------------------------- optimizer


class AnalyzeRequest(BaseModel):
    text: str = Field(description="Draft markdown/plain text to analyse")
    primary_query: str | None = None
    page_type: str | None = None
    target_entities: list[str] = Field(default_factory=list)
    banned_terms: list[str] = Field(default_factory=list)
    context_pack_ids: list[str] = Field(default_factory=list)
    word_target: int = Field(default=900, ge=50, le=10_000)


class AnalyzeHeading(BaseModel):
    level: int
    text: str
    is_question: bool = False


class AnalyzeEntityHit(BaseModel):
    name: str
    count: int = 0
    expected: bool = True
    status: str = "ok"  # ok | thin | missing


class AnalyzeViolation(BaseModel):
    term: str
    count: int = 0
    replacement: str | None = None


class AnalyzeDimension(BaseModel):
    key: str
    label: str
    score: int = Field(ge=0, le=100)
    band: str = "fair"  # weak | fair | strong
    note: str = ""


class AnalyzeRecommendation(BaseModel):
    id: str
    title: str
    detail: str
    dimension: str
    impact: str = "medium"  # high | medium | low
    action: str = ""


class AnalyzeMetrics(BaseModel):
    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0
    reading_time_minutes: int = 0
    reading_ease: float = 0.0
    flesch_kincaid_grade: float = 0.0


class AnalyzeResponse(BaseModel):
    metrics: AnalyzeMetrics = Field(default_factory=AnalyzeMetrics)
    headings: list[AnalyzeHeading] = Field(default_factory=list)
    entities: list[AnalyzeEntityHit] = Field(default_factory=list)
    violations: list[AnalyzeViolation] = Field(default_factory=list)
    dimensions: list[AnalyzeDimension] = Field(default_factory=list)
    recommendations: list[AnalyzeRecommendation] = Field(default_factory=list)
    overall_score: int = Field(default=0, ge=0, le=100)
    disclaimer: str = ""
