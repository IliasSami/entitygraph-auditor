"""Audit run request + shared workflow state (PRD §8.4)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ega_schemas.claims import Claim, EvidenceSource
from ega_schemas.content import ContentSourceMeta, ParsedDocument
from ega_schemas.entities import EAVRow, Entity
from ega_schemas.enums import (
    AuditDepth,
    GateStatus,
    IntentClass,
    PageType,
    ResultOrigin,
    SensitivityTier,
    Severity,
    SourceProfile,
    StageStatus,
)
from ega_schemas.fanout import CoverageRow, FanoutQuery
from ega_schemas.findings import Finding, Recommendation, Swot
from ega_schemas.report import GateIssue, Scorecard
from ega_schemas.triples import SemanticTriple


class AuditCreateRequest(BaseModel):
    """POST /api/v1/audits request body."""

    project_id: str
    content_version_id: str | None = None  # reference an imported version…
    content_text: str | None = None  # …or provide text directly
    content_url: str | None = None
    page_type: PageType | None = None  # user selection overrides classifier
    primary_query: str | None = None
    secondary_queries: list[str] = Field(default_factory=list)
    audience_icp: str | None = None
    location_target: str | None = None
    conversion_goal: str | None = None
    page_url: str | None = None
    competitor_urls: list[str] = Field(default_factory=list)
    lifecycle: str = "draft"  # draft | published
    target_platforms: list[str] = Field(default_factory=list)
    sensitivity: SensitivityTier = SensitivityTier.ORDINARY
    source_profile: SourceProfile = SourceProfile.OFFLINE
    context_pack_ids: list[str] = Field(default_factory=list)
    score_profile: str | None = None  # override default profile for page type
    depth: AuditDepth = AuditDepth.STANDARD
    content_format: str = "markdown"  # markdown | html | text
    language: str | None = None
    disable_cache: bool = False


class StageRecord(BaseModel):
    node: str
    label: str
    status: StageStatus = StageStatus.PENDING
    origin: ResultOrigin = ResultOrigin.DETERMINISTIC
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    retries: int = 0
    attempts: int = 0
    error: str | None = None
    detail: str | None = None
    cached: bool = False
    tokens_estimated: int | None = None


class AuditRunState(BaseModel):
    """Typed shared state passed between workflow nodes (PRD §8.4)."""

    run_id: str
    project_id: str
    request: AuditCreateRequest

    # parsing
    content_version_id: str = ""
    content_hash: str = ""
    document: ParsedDocument | None = None
    source_meta: ContentSourceMeta | None = None

    # classification
    page_type: PageType = PageType.GENERAL
    page_type_source: str = "classifier"
    page_type_confidence: float = 0.0
    page_type_rationale: str = ""
    primary_intent: IntentClass | None = None
    central_entity: str | None = None
    audience: str | None = None
    target_action: str | None = None
    language: str = "en"
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    skipped_stages: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    # context packs
    context_pack_ids: list[str] = Field(default_factory=list)
    context_pack_versions: dict[str, str] = Field(default_factory=dict)
    brand_rules: list[dict] = Field(default_factory=list)
    canonical_facts: list[dict] = Field(default_factory=list)
    banned_terms: list[dict] = Field(default_factory=list)
    approved_claims: list[dict] = Field(default_factory=list)
    internal_link_targets: list[dict] = Field(default_factory=list)
    topical_map_rows: list[dict] = Field(default_factory=list)

    # agent outputs
    fanout: list[FanoutQuery] = Field(default_factory=list)
    coverage_rows: list[CoverageRow] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    eav_rows: list[EAVRow] = Field(default_factory=list)
    triples: list[SemanticTriple] = Field(default_factory=list)
    passage_findings: list[Finding] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    swot: Swot = Field(default_factory=Swot)
    technical_flags: list[dict] = Field(default_factory=list)

    # gate + scores
    gate_status: GateStatus = GateStatus.NOT_CONFIGURED
    gate_issues: list[GateIssue] = Field(default_factory=list)
    noncritical_gate_issues: list[GateIssue] = Field(default_factory=list)
    scorecard: Scorecard | None = None

    # ops
    model_provider: str | None = None
    model_id: str | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    deterministic_only: bool = False
    stages: list[StageRecord] = Field(default_factory=list)
    token_estimate: int = 0
    latency_ms: int = 0
    critic_loops: int = 0
    critic_notes: list[str] = Field(default_factory=list)
    measurement_plan: list[dict[str, Any]] = Field(default_factory=list)
    writer_handoff: dict | None = None
    depth: AuditDepth = AuditDepth.STANDARD
    created_at: str = ""
    completed_at: str | None = None

    def add_warning(self, text: str) -> None:
        if text not in self.warnings:
            self.warnings.append(text)

    def skip_stage(self, node: str, reason: str) -> None:
        if node not in self.skipped_stages:
            self.skipped_stages.append(node)
        self.add_warning(reason)

    def highest_severity(self) -> Severity | None:
        order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
        sevs = {i.severity for i in self.gate_issues}
        for s in order:
            if s in sevs:
                return s
        return None
