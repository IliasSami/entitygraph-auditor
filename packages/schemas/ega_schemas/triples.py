"""Semantic Triple and Knowledge Graph Readiness schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from ega_schemas.enums import Confidence, TripleStatus, TripleType


class SemanticTriple(BaseModel):
    """Subject - Predicate - Object relationship assertion."""

    triple_id: str
    subject: str
    predicate: str
    object_: str
    triple_type: TripleType = TripleType.OTHER
    status: TripleStatus = TripleStatus.EXPLICIT
    evidence_excerpt: Optional[str] = None
    passage_id: Optional[str] = None
    confidence: Confidence = Confidence.MEDIUM
    notes: Optional[str] = None
