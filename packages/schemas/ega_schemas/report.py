"""Audit Report Contract per PRD §22."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from ega_schemas.claims import Claim, EvidenceSource
from ega_schemas.entities import EAVRow, Entity
from ega_schemas.enums import IntentClass, PageType
from ega_schemas.fanout import CoverageRow, FanoutQuery
from ega_schemas.findings import Finding, Swot
from ega_schemas.scores import (
    GateIssue,
    GateResult,
    Scorecard,
    ScoreComponent,
)
from ega_schemas.triples import SemanticTriple


class SourceCitation(BaseModel):
    """External or internal reference citation."""

    source_id: str = ""
    title: str = ""
    url: Optional[str] = None
    publisher: Optional[str] = None
    access_date: Optional[str] = None
    verification_state: Optional[str] = None


class AuditMetadata(BaseModel):
    """Audit run provenance and execution parameters."""

    project_id: str
    run_id: str
    page_type: PageType = PageType.GENERAL
    page_type_source: str = "classifier"
    language: str = "en"
    central_entity: str = ""
    primary_intent: Optional[IntentClass] = IntentClass.INFORMATIONAL
    primary_query: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    content_hash: str
    score_profile_version: str = "1.0"
    provider_model: Optional[str] = "local"
    context_pack_versions: list[str] = Field(default_factory=list)
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    skipped_stages: list[str] = Field(default_factory=list)
    deterministic_only: bool = True
    depth: str = "standard"


class SwotAnalysis(BaseModel):
    """SWOT analysis of content performance and visibility readiness."""

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)


class PassageFinding(BaseModel):
    """Passage-level retrieval finding."""

    passage_id: str = ""
    issue: str = ""
    severity: str = "medium"


class AuditReport(BaseModel):
    """Full Structured Audit Report Contract (PRD §22)."""

    model_config = ConfigDict(validate_assignment=True)

    audit_metadata: AuditMetadata
    gate: GateResult = Field(default_factory=GateResult)
    scores: Scorecard = Field(default_factory=Scorecard)
    composite_avr: Optional[float] = None

    entities: list[Entity] = Field(default_factory=list)
    entity_missing_groups: list[str] = Field(default_factory=list)
    eav_rows: list[EAVRow] = Field(default_factory=list)
    triples: list[SemanticTriple] = Field(default_factory=list)
    fanout: list[FanoutQuery] = Field(default_factory=list)
    coverage_rows: list[CoverageRow] = Field(default_factory=list)
    passage_findings: list[Finding] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[Finding] = Field(default_factory=list)
    swot: SwotAnalysis | Swot | dict[str, Any] = Field(default_factory=SwotAnalysis)
    writer_handoff: Optional[dict[str, Any]] = None
    measurement_plan: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[SourceCitation] | list[EvidenceSource] = Field(default_factory=list)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    technical_flags: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    not_assessed: list[str] = Field(default_factory=list)
    stage_records: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("scores", mode="before")
    @classmethod
    def _coerce_scores(cls, value: Any) -> Any:
        """Accept a ``Scorecard``, its JSON dump, or the PRD §22 flat component map.

        The report is persisted as JSON and re-read, so the field must round-trip.
        """
        if value is None or isinstance(value, Scorecard):
            return value
        if isinstance(value, dict):
            # A serialized Scorecard carries its own ``scores``/``components`` map.
            if isinstance(value.get("scores"), dict) or isinstance(value.get("components"), dict):
                return value
            # PRD §22 flat map: {"EOS": {...}, ..., "AVR": {"value": 5.9, "profile": ...}}
            avr = value.get("AVR")
            card = Scorecard(scores={k: v for k, v in value.items() if k != "AVR"})
            avr_value: Any = None
            if isinstance(avr, dict):
                avr_value = avr.get("value")
                if avr.get("profile"):
                    card.profile_name = str(avr["profile"])
                if avr.get("warning"):
                    card.warning = str(avr["warning"])
            elif avr is not None:
                avr_value = getattr(avr, "value", avr)
            if avr_value is not None:
                try:
                    card.avr = float(avr_value)
                except (TypeError, ValueError):
                    card.avr = None
            return card
        return value

    @field_serializer("scores", when_used="always")
    def _serialize_scores(self, value: Any) -> dict[str, Any]:
        """Emit the flat PRD §22 map: ``{EOS: {...}, …, AVR: {value, profile, warning}}``."""
        if isinstance(value, dict):
            return {
                key: component.model_dump(mode="json")
                if hasattr(component, "model_dump")
                else component
                for key, component in value.items()
            }
        flat: dict[str, Any] = {
            key: component.model_dump(mode="json")
            for key, component in value.scores.items()
            if key != "AVR"
        }
        avr_component = value.scores.get("AVR")
        avr_value = value.avr
        if avr_value is None and value.composite is not None:
            avr_value = value.composite.value
        # Only surface an AVR entry when one actually exists, so a report with no
        # composite round-trips byte-for-byte.
        if avr_component is not None:
            avr_entry = avr_component.model_dump(mode="json")
            if avr_value is not None:
                avr_entry["value"] = avr_value
            avr_entry.setdefault("profile", value.profile_name)
            avr_entry.setdefault("warning", value.warning)
            flat["AVR"] = avr_entry
        elif avr_value is not None:
            flat["AVR"] = {
                "value": avr_value,
                "profile": value.profile_name,
                "warning": value.warning,
            }
        return flat


__all__ = [
    "AuditMetadata",
    "AuditReport",
    "GateIssue",
    "GateResult",
    "PassageFinding",
    "Scorecard",
    "ScoreComponent",
    "SourceCitation",
    "SwotAnalysis",
]

