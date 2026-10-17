"""Context pack, brand book, and topical map schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ega_schemas.enums import IntentClass, Severity


class BrandRule(BaseModel):
    """Explicit brand positioning or compliance rule."""

    rule_id: str
    rule_type: str = "brand_voice"
    statement: str
    severity: Severity = Severity.HIGH


class CanonicalFact(BaseModel):
    """Ground-truth canonical attribute assertion for the organization."""

    fact_id: str
    entity: str
    attribute: str
    canonical_value: str
    verification_source: Optional[str] = None


class ApprovedClaim(BaseModel):
    """Pre-vetted legal/marketing claim statement."""

    claim_id: str
    approved_statement: str
    required_citations: list[str] = Field(default_factory=list)


class BannedTerm(BaseModel):
    """Prohibited word or phrase and acceptable substitutes."""

    term: str
    reason: str
    suggested_replacement: Optional[str] = None


class TopicalMapRow(BaseModel):
    """Topical map entry for site-level semantic architecture."""

    topic: str
    primary_entity: str
    intent: IntentClass = IntentClass.INFORMATIONAL
    target_url: Optional[str] = None


class InternalLinkTarget(BaseModel):
    """Recommended internal linking target."""

    anchor_phrase: str
    target_url: str
    entity: str


class ContextPack(BaseModel):
    """Portable context pack containing brand rules, canonical facts, and maps."""

    pack_id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    brand_rules: list[BrandRule] = Field(default_factory=list)
    canonical_facts: list[CanonicalFact] = Field(default_factory=list)
    approved_claims: list[ApprovedClaim] = Field(default_factory=list)
    banned_terms: list[BannedTerm] = Field(default_factory=list)
    topical_map: list[TopicalMapRow] = Field(default_factory=list)
    internal_links: list[InternalLinkTarget] = Field(default_factory=list)
