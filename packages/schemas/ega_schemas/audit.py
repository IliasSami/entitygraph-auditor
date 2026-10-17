"""Audit request and workflow run state schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from ega_schemas.claims import Claim, EvidenceSource
from ega_schemas.content import ParsedDocument
from ega_schemas.entities import EAVRow, Entity
from ega_schemas.enums import (
    AuditDepth,
    IntentClass,
    PageType,
    SourceProfile,
    StageStatus,
)
from ega_schemas.fanout import CoverageRow, FanoutQuery
from ega_schemas.findings import Finding
from ega_schemas.report import SwotAnalysis
from ega_schemas.scores import ComponentScore, GateResult
from ega_schemas.triples import SemanticTriple


class AuditCreateRequest(BaseModel):
    """Payload to initiate a new content audit."""

    content: str = Field(description="Raw markdown, HTML, or plain text to audit")
    project_id: Optional[str] = Field(default=None, description="Optional target project ID")
    url: Optional[str] = Field(default=None, description="Source URL if applicable")
    title: Optional[str] = Field(default=None, description="Page title")
    page_type: Optional[PageType] = Field(default=None, description="Explicit page type override")
    central_entity: Optional[str] = Field(default=None, description="Explicit central entity override")
    primary_intent: Optional[IntentClass] = Field(default=None, description="Explicit primary search intent")
    target_audience: Optional[str] = Field(default=None, description="Target ICP/audience description")
    target_action: Optional[str] = Field(default=None, description="Desired conversion action (CTA)")
    locale: str = Field(default="en", description="Target locale / language code (e.g. en, fr, bn)")
    depth: AuditDepth = Field(default=AuditDepth.STANDARD)
    source_profile: SourceProfile = Field(default=SourceProfile.OFFLINE)
    model_provider: Optional[str] = Field(default=None, description="Provider: dummy, ollama, openai, etc.")
    model_name: Optional[str] = Field(default=None, description="Model identifier")
    context_pack_ids: list[str] = Field(default_factory=list)


class AuditRunState(BaseModel):
    """Shared state contract across the LangGraph multi-agent audit graph (PRD §8.4)."""

    run_id: str
    project_id: str = "default"
    content: str
    url: Optional[str] = None
    title: Optional[str] = None
    parsed_doc: Optional[ParsedDocument] = None

    # Inferred or user-provided classification
    page_type: PageType = PageType.GENERAL
    central_entity: str = ""
    primary_intent: IntentClass = IntentClass.INFORMATIONAL
    target_audience: str = "General Audience"
    target_action: str = "Read / Learn"
    locale: str = "en"
    depth: AuditDepth = AuditDepth.STANDARD
    source_profile: SourceProfile = SourceProfile.OFFLINE
    model_provider: str = "dummy"
    model_name: str = "default"

    # Context & Rules loaded
    context_packs: list[dict[str, Any]] = Field(default_factory=list)

    # Agent outputs
    fanout_queries: list[FanoutQuery] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    eav_rows: list[EAVRow] = Field(default_factory=list)
    triples: list[SemanticTriple] = Field(default_factory=list)
    coverage_rows: list[CoverageRow] = Field(default_factory=list)
    passage_findings: list[Finding] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)

    # Gate and Scores
    gate_result: GateResult = Field(default_factory=GateResult)
    component_scores: dict[str, ComponentScore] = Field(default_factory=dict)
    composite_avr: Optional[float] = None

    # Handoff & Synthesis
    recommendations: list[Finding] = Field(default_factory=list)
    swot: SwotAnalysis = Field(default_factory=SwotAnalysis)
    measurement_plan: list[dict[str, Any]] = Field(default_factory=list)

    # Critic & QA loop state
    critic_loops: int = 0
    critic_approved: bool = False
    critic_notes: list[str] = Field(default_factory=list)

    # Execution telemetry
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    status: StageStatus = StageStatus.PENDING
    error: Optional[str] = None
