"""Claim and Evidence Ledger schemas for EntityGraph Auditor."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from ega_schemas.enums import ClaimRiskTier, EvidenceLabel, VerificationState


class EvidenceSource(BaseModel):
    """External or internal source referenced by a claim."""

    source_id: str
    label: EvidenceLabel = EvidenceLabel.UNVERIFIED
    title: str
    url: Optional[str] = None
    publisher: Optional[str] = None
    publication_date: Optional[str] = None
    excerpt: Optional[str] = None


class Claim(BaseModel):
    """Factual, empirical, or competitive claim made in content."""

    claim_id: str
    statement: str
    risk_tier: ClaimRiskTier = ClaimRiskTier.ORDINARY
    verification_state: VerificationState = VerificationState.NOT_ASSESSED
    passage_id: Optional[str] = None
    evidence_source_ids: list[str] = []
    requires_substantiation: bool = False
    issue: Optional[str] = None
