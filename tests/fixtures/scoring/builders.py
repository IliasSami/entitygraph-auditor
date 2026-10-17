"""Deterministic fixture builders shared by the scoring / rules unit tests.

The builders intentionally return :class:`types.SimpleNamespace` objects rather
than :class:`ega_schemas.audit.AuditRunState`: the scoring engine reads state
through tolerant accessors (``ega_scoring.state``) and the tests exercise
"messy" run states that a strict pydantic model would refuse to hold. Pydantic
sub-models (entities, EAV rows, triples, claims, ...) are still constructed from
the JSON fixtures so the tests run against the real schema contract.

Everything here is pure and deterministic — no network, no LLM, no clock.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

from ega_parsers import DocumentParser
from ega_schemas.claims import Claim, EvidenceSource
from ega_schemas.content import ParsedDocument
from ega_schemas.entities import EAVRow, Entity, EntityOccurrence
from ega_schemas.enums import (
    ClaimRiskTier,
    CoverageStatus,
    EAVStatus,
    EntityKind,
    IntentClass,
    PageType,
    QueryScope,
    SensitivityTier,
    TripleStatus,
    TripleType,
    VerificationState,
)
from ega_schemas.fanout import CoverageRow, FanoutQuery
from ega_schemas.triples import SemanticTriple

FIXTURES_DIR = Path(__file__).resolve().parent


def load_json(name: str) -> dict[str, Any]:
    """Load one JSON fixture from this directory."""
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def brand_pack() -> dict[str, Any]:
    """The brand pack fixture (brand rules, banned terms, canonical facts, links)."""
    return load_json("brand_pack.json")


def _entity(data: dict[str, Any]) -> Entity:
    occurrences = [EntityOccurrence(**occ) for occ in data.get("occurrences", [])]
    payload = dict(data)
    payload["occurrences"] = occurrences
    payload["kind"] = EntityKind(payload.get("kind", "other"))
    return Entity(**payload)


def _eav(data: dict[str, Any]) -> EAVRow:
    payload = dict(data)
    payload["status"] = EAVStatus(payload.get("status", "missing"))
    return EAVRow(**payload)


def _triple(data: dict[str, Any]) -> SemanticTriple:
    payload = dict(data)
    payload["status"] = TripleStatus(payload.get("status", "explicit"))
    payload["triple_type"] = TripleType(payload.get("triple_type", "other"))
    return SemanticTriple(**payload)


def _query(data: dict[str, Any]) -> FanoutQuery:
    payload = dict(data)
    payload["intent"] = IntentClass(payload.get("intent", "informational"))
    payload["scope"] = QueryScope(payload.get("scope", "this_page"))
    return FanoutQuery(**payload)


def _coverage(data: dict[str, Any]) -> CoverageRow:
    payload = dict(data)
    payload["status"] = CoverageStatus(payload.get("status", "missing"))
    return CoverageRow(**payload)


def _claim(data: dict[str, Any]) -> Claim:
    payload = dict(data)
    payload["risk_tier"] = ClaimRiskTier(payload.get("risk_tier", "ordinary"))
    payload["verification_state"] = VerificationState(payload.get("verification_state", "not_assessed"))
    return Claim(**payload)


def _source(data: dict[str, Any]) -> EvidenceSource:
    return EvidenceSource(**data)


def parse_document(markdown: str) -> ParsedDocument:
    """Parse a Markdown/HTML blob with the deterministic parser."""
    return DocumentParser.parse(markdown)


def rich_state(**overrides: Any) -> SimpleNamespace:
    """A fully-populated commercial SERVICE run state (PRD §9 integration fixture).

    Every one of the seven core components is assessable, the brand pack is
    loaded and clean, and the local/paid optional profiles are genuinely N/A.
    Pass ``overrides`` to change any field (``page_type=``, ``claims=[]``, ...).
    """
    data = load_json("rich_state.json")
    state = SimpleNamespace(
        parsed_doc=parse_document(data["document_text"]),
        page_type=PageType(data["page_type"]),
        primary_intent=IntentClass(data["primary_intent"]),
        central_entity=data["central_entity"],
        target_action=data["target_action"],
        location_target=data.get("location_target"),
        sensitivity=SensitivityTier(data.get("sensitivity", "ordinary")),
        entities=[_entity(e) for e in data["entities"]],
        eav_rows=[_eav(r) for r in data["eav_rows"]],
        triples=[_triple(t) for t in data["triples"]],
        fanout_queries=[_query(q) for q in data["fanout_queries"]],
        coverage_rows=[_coverage(c) for c in data["coverage_rows"]],
        claims=[_claim(c) for c in data["claims"]],
        evidence_sources=[_source(s) for s in data["evidence_sources"]],
        context_packs=[brand_pack()],
    )
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def empty_state(**overrides: Any) -> SimpleNamespace:
    """A run state with no assessable inputs at all (everything is N/A)."""
    state = SimpleNamespace(
        parsed_doc=None,
        page_type=PageType.GENERAL,
        primary_intent=None,
        central_entity="",
        target_action=None,
        location_target=None,
        sensitivity=SensitivityTier.ORDINARY,
        entities=[],
        eav_rows=[],
        triples=[],
        fanout_queries=[],
        coverage_rows=[],
        claims=[],
        evidence_sources=[],
        context_packs=[],
        findings=[],
        passage_findings=[],
    )
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def gate_state(
    text: str = "",
    *,
    claims: Optional[list[Claim]] = None,
    context_packs: Optional[list[Any]] = None,
    findings: Optional[list[Any]] = None,
    sensitivity: SensitivityTier = SensitivityTier.ORDINARY,
    canonical_facts: Optional[list[Any]] = None,
    banned_terms: Optional[list[Any]] = None,
    brand_rules: Optional[list[Any]] = None,
    eav_rows: Optional[list[EAVRow]] = None,
    triples: Optional[list[SemanticTriple]] = None,
) -> SimpleNamespace:
    """A minimal state for gate-only tests (text + optional structured inputs)."""
    return SimpleNamespace(
        content=text,
        parsed_doc=None,
        claims=list(claims or []),
        evidence_sources=[],
        context_packs=list(context_packs or []),
        findings=list(findings or []),
        passage_findings=[],
        sensitivity=sensitivity,
        canonical_facts=list(canonical_facts or []),
        banned_terms=list(banned_terms or []),
        brand_rules=list(brand_rules or []),
        eav_rows=list(eav_rows or []),
        triples=list(triples or []),
        page_type=PageType.GENERAL,
    )


def build_finding(
    finding_id: str = "f1",
    *,
    severity: str = "high",
    status: str = "open",
    title: str = "Sample finding",
    category: str = "structure",
    impact: int = 3,
    confidence_numeric: int = 4,
    effort: int = 2,
) -> Any:
    """Build a schema ``Finding`` from simple strings (priority/rules tests)."""
    from ega_schemas.enums import RecommendationStatus, Severity
    from ega_schemas.findings import Finding

    return Finding(
        finding_id=finding_id,
        category=category,
        severity=Severity(severity),
        status=RecommendationStatus(status),
        title=title,
        what="Synthetic finding used by deterministic tests.",
        impact=impact,
        confidence_numeric=confidence_numeric,
        effort=effort,
    )


__all__ = [
    "FIXTURES_DIR",
    "brand_pack",
    "build_finding",
    "empty_state",
    "gate_state",
    "load_json",
    "parse_document",
    "rich_state",
]
