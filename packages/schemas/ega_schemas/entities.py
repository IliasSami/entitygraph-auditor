"""Entity and Attribute-Value (EAV) schemas for EntityGraph Auditor."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ega_schemas.enums import Confidence, EAVStatus, EntityKind, ExtractionMethod


class EntityOccurrence(BaseModel):
    """Specific textual occurrence of an entity."""

    passage_id: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    sentence: str = ""


class Entity(BaseModel):
    """Extracted or mapped entity."""

    entity_id: str
    canonical_name: str
    kind: EntityKind = EntityKind.OTHER
    confidence: Confidence = Confidence.MEDIUM
    salience: float = Field(ge=0.0, le=1.0, default=0.5, description="Relative topical salience 0-1")
    occurrences: list[EntityOccurrence] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    is_central: bool = False
    method: ExtractionMethod = ExtractionMethod.DETERMINISTIC
    wikidata_id: Optional[str] = None


class EAVRow(BaseModel):
    """Entity-Attribute-Value record representing a factual assertion."""

    eav_id: str
    entity_name: str
    attribute: str
    value: Optional[str] = None
    status: EAVStatus = EAVStatus.MISSING
    evidence_excerpt: Optional[str] = None
    passage_id: Optional[str] = None
    confidence: Confidence = Confidence.MEDIUM
    notes: Optional[str] = None
    is_required_by_page_type: bool = False
