"""Tolerant accessors over the shared audit run state (PRD §8.4).

The schema package is being consolidated concurrently (see AGENTS.md): field
names such as ``document``/``parsed_doc``, ``fanout``/``fanout_queries`` and
``findings``/``recommendations`` exist in more than one design. The scoring
engine therefore reads state through these accessors, which accept either
spelling, plus plain namespace-like objects in tests. Brand-pack data is read
from explicit state attributes when present and otherwise flattened out of
``context_packs`` entries (dicts or ``ContextPack`` models).
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Optional, Sequence

from ega_schemas.claims import Claim, EvidenceSource
from ega_schemas.content import ParsedDocument, Passage
from ega_schemas.entities import EAVRow, Entity
from ega_schemas.enums import (
    ClaimRiskTier,
    IntentClass,
    PageType,
    SensitivityTier,
    VerificationState,
)
from ega_schemas.fanout import CoverageRow, FanoutQuery
from ega_schemas.findings import Finding
from ega_schemas.triples import SemanticTriple


def get_attr(state: Any, *names: str, default: Any = None) -> Any:
    """Return the first non-``None`` attribute among ``names``."""
    for name in names:
        value = getattr(state, name, None)
        if value is not None:
            return value
    return default


def get_request_attr(state: Any, *names: str, default: Any = None) -> Any:
    """Read an attribute from the nested create request, if present."""
    request = getattr(state, "request", None)
    if request is not None:
        for name in names:
            value = getattr(request, name, None)
            if value is not None:
                return value
    return default


def as_mapping(item: Any) -> Mapping[str, Any]:
    """Normalize dicts and pydantic pack models into a mapping."""
    if isinstance(item, Mapping):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(vars(item))


def _flatten_pack_key(state: Any, key: str) -> list[Any]:
    """Flatten ``key`` out of every ``context_packs`` entry."""
    items: list[Any] = []
    for pack in get_attr(state, "context_packs", default=[]) or []:
        try:
            data = as_mapping(pack)
        except (TypeError, ValueError):
            continue
        items.extend(data.get(key) or [])
    return items


def get_document(state: Any) -> Optional[ParsedDocument]:
    """The parsed document (``document`` or ``parsed_doc``)."""
    return get_attr(state, "document", "parsed_doc")


def get_page_type(state: Any) -> PageType:
    value = get_attr(state, "page_type", default=PageType.GENERAL)
    return value if isinstance(value, PageType) else PageType(str(value))


def get_primary_intent(state: Any) -> Optional[IntentClass]:
    value = get_attr(state, "primary_intent") or get_request_attr(state, "primary_intent")
    if value is None:
        return None
    return value if isinstance(value, IntentClass) else IntentClass(str(value))


def get_central_entity(state: Any) -> str:
    return str(get_attr(state, "central_entity", default="") or get_request_attr(state, "central_entity", default="") or "")


def get_language(state: Any) -> str:
    return str(get_attr(state, "language", "locale", default="en") or "en")


def get_location_target(state: Any) -> Optional[str]:
    return get_attr(state, "location_target") or get_request_attr(state, "location_target")


def get_target_action(state: Any) -> Optional[str]:
    return get_attr(state, "target_action") or get_request_attr(state, "target_action")


def get_conversion_goal(state: Any) -> Optional[str]:
    return (
        get_attr(state, "conversion_goal")
        or get_request_attr(state, "conversion_goal")
        or get_target_action(state)
    )


def get_audience(state: Any) -> Optional[str]:
    return get_attr(state, "audience", "target_audience") or get_request_attr(state, "target_audience", "audience_icp")


def get_sensitivity(state: Any) -> SensitivityTier:
    value = get_attr(state, "sensitivity") or get_request_attr(state, "sensitivity")
    if value is None:
        return SensitivityTier.ORDINARY
    return value if isinstance(value, SensitivityTier) else SensitivityTier(str(value))


def get_score_profile_override(state: Any) -> Optional[str]:
    return get_attr(state, "score_profile") or get_request_attr(state, "score_profile")


def get_entities(state: Any) -> list[Entity]:
    return list(get_attr(state, "entities", default=[]) or [])


def get_eav_rows(state: Any) -> list[EAVRow]:
    return list(get_attr(state, "eav_rows", default=[]) or [])


def get_triples(state: Any) -> list[SemanticTriple]:
    return list(get_attr(state, "triples", default=[]) or [])


def get_claims(state: Any) -> list[Claim]:
    return list(get_attr(state, "claims", default=[]) or [])


def get_evidence_sources(state: Any) -> list[EvidenceSource]:
    return list(get_attr(state, "evidence_sources", default=[]) or [])


def get_fanout(state: Any) -> list[FanoutQuery]:
    """Fan-out queries (``fanout`` or ``fanout_queries``)."""
    return list(get_attr(state, "fanout", "fanout_queries", default=[]) or [])


def get_coverage_rows(state: Any) -> list[CoverageRow]:
    return list(get_attr(state, "coverage_rows", default=[]) or [])


def get_findings(state: Any) -> list[Finding]:
    """Synthesis findings (``findings``, else ``recommendations``)."""
    return list(get_attr(state, "findings", "recommendations", default=[]) or [])


def get_passage_findings(state: Any) -> list[Finding]:
    return list(get_attr(state, "passage_findings", default=[]) or [])


def get_brand_rules(state: Any) -> list[Any]:
    return list(get_attr(state, "brand_rules", default=[]) or []) + _flatten_pack_key(state, "brand_rules")


def get_banned_terms(state: Any) -> list[Any]:
    return list(get_attr(state, "banned_terms", default=[]) or []) + _flatten_pack_key(state, "banned_terms")


def get_canonical_facts(state: Any) -> list[Any]:
    return list(get_attr(state, "canonical_facts", default=[]) or []) + _flatten_pack_key(state, "canonical_facts")


def get_approved_claims(state: Any) -> list[Any]:
    return list(get_attr(state, "approved_claims", default=[]) or []) + _flatten_pack_key(state, "approved_claims")


def get_internal_link_targets(state: Any) -> list[Any]:
    targets = list(get_attr(state, "internal_link_targets", default=[]) or [])
    if targets:
        return targets
    return _flatten_pack_key(state, "internal_links") + _flatten_pack_key(state, "internal_link_targets")


def get_warnings(state: Any) -> list[str]:
    return [str(w) for w in (get_attr(state, "warnings", default=[]) or [])]


def document_text(state: Any) -> str:
    """Best available raw text: document text, else the provided content."""
    document = get_document(state)
    if document is not None:
        return document.raw_text or document.normalized_text or ""
    return str(get_attr(state, "content", default="") or "")


# --------------------------------------------------------------------------
# Text / entity helpers
# --------------------------------------------------------------------------

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def normalize_name(value: Any) -> str:
    """Aggressive normalization for entity-name comparisons."""
    return _NORMALIZE_RE.sub(" ", str(value or "").casefold()).strip()


def build_entity_index(entities: Iterable[Entity]) -> dict[str, Entity]:
    """Map normalized canonical names and aliases to their entity."""
    index: dict[str, Entity] = {}
    for entity in entities:
        keys = [entity.canonical_name, *entity.aliases]
        for key in keys:
            normalized = normalize_name(key)
            if normalized and normalized not in index:
                index[normalized] = entity
    return index


def resolve_entity(index: Mapping[str, Entity], name: Any) -> Optional[Entity]:
    """Resolve a subject/object string to an entity via exact or containment match."""
    normalized = normalize_name(name)
    if not normalized:
        return None
    if normalized in index:
        return index[normalized]
    candidates = [
        (len(key), key) for key in index if len(key) >= 4 and (key in normalized or normalized in key)
    ]
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return index[candidates[0][1]]


def entity_by_flag(entities: Sequence[Entity]) -> Optional[Entity]:
    """The explicitly flagged central entity, if any."""
    for entity in entities:
        if entity.is_central:
            return entity
    return None


def central_entity_node(state: Any) -> Optional[Entity]:
    """Best-effort central entity: flagged entity, else name match against the inventory."""
    entities = get_entities(state)
    flagged = entity_by_flag(entities)
    if flagged is not None:
        return flagged
    central_name = normalize_name(get_central_entity(state))
    if not central_name:
        return None
    index = build_entity_index(entities)
    return index.get(central_name)


def passage_index(document: Optional[ParsedDocument]) -> dict[str, Passage]:
    if document is None:
        return {}
    return {p.passage_id: p for p in document.passages}


def passage_section_map(document: Optional[ParsedDocument]) -> dict[str, str]:
    """Map passage_id → section_id (falls back to the passage's own section_id)."""
    if document is None:
        return {}
    mapping: dict[str, str] = {}
    for section in document.sections:
        for passage in section.passages:
            mapping[passage.passage_id] = section.section_id
    for passage in document.passages:
        mapping.setdefault(passage.passage_id, passage.section_id)
    return mapping


def passages_by_section(document: Optional[ParsedDocument]) -> dict[str, list[str]]:
    """Ordered passage ids grouped by section, preserving document order."""
    if document is None:
        return {}
    grouped: dict[str, list[str]] = {}
    for passage in document.passages:
        grouped.setdefault(passage.section_id or "_root", []).append(passage.passage_id)
    return grouped


# --------------------------------------------------------------------------
# Claim helpers
# --------------------------------------------------------------------------

_NUMERIC_RE = re.compile(r"\d+(?:[.,]\d+)*%?")
_DATE_IN_TEXT_RE = re.compile(r"\b(?:19|20)\d{2}\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.IGNORECASE)
_FABRICATION_RE = re.compile(r"fabricat|invented|made[\s-]?up|unsupported number|no source|falsif", re.IGNORECASE)


def claim_numbers(claim: Claim) -> list[str]:
    """Numeric tokens present in a claim statement."""
    return _NUMERIC_RE.findall(claim.statement or "")


def is_numeric_claim(claim: Claim) -> bool:
    """True when the statement asserts at least one number/percentage."""
    return bool(claim_numbers(claim))


def claim_is_fabrication_risk(claim: Claim) -> bool:
    """Fabrication-risk heuristic (PRD §9.5 fabricated data/quotes/credentials).

    The schema has no ``is_fabrication_risk`` flag, so risk is derived
    deterministically: an agent-supplied ``issue`` mentioning fabrication or a
    ``conflicting`` verification state on a claim that requires substantiation.
    """
    if claim.issue and _FABRICATION_RE.search(claim.issue):
        return True
    if claim.verification_state == VerificationState.CONFLICTING and claim.requires_substantiation:
        return True
    return False


def claim_is_unverified(claim: Claim) -> bool:
    """Unverified means no evidence links and not in a verified state."""
    return not claim.evidence_source_ids and claim.verification_state in (
        VerificationState.UNVERIFIED,
        VerificationState.NOT_ASSESSED,
        VerificationState.CONFLICTING,
    )


def claim_is_high_stakes(claim: Claim) -> bool:
    return claim.risk_tier in (ClaimRiskTier.HIGH_STAKES, ClaimRiskTier.REGULATED)


def claim_has_dated_context(claim: Claim, sources: Sequence[EvidenceSource] = ()) -> bool:
    """A claim is dated when a linked source carries a date or the statement does."""
    if _DATE_IN_TEXT_RE.search(claim.statement or ""):
        return True
    source_ids = set(claim.evidence_source_ids or [])
    for source in sources:
        if source.source_id in source_ids and (source.publication_date or ""):
            return True
    return False


def evidence_label_is_first_party(source: EvidenceSource) -> bool:
    from ega_schemas.enums import EvidenceLabel

    return source.label == EvidenceLabel.FIRST_PARTY


__all__ = [
    "as_mapping",
    "build_entity_index",
    "central_entity_node",
    "claim_has_dated_context",
    "claim_is_fabrication_risk",
    "claim_is_high_stakes",
    "claim_is_unverified",
    "claim_numbers",
    "document_text",
    "entity_by_flag",
    "get_audience",
    "get_approved_claims",
    "get_attr",
    "get_banned_terms",
    "get_canonical_facts",
    "get_claims",
    "get_conversion_goal",
    "get_coverage_rows",
    "get_document",
    "get_eav_rows",
    "get_entities",
    "get_evidence_sources",
    "get_fanout",
    "get_findings",
    "get_internal_link_targets",
    "get_language",
    "get_location_target",
    "get_page_type",
    "get_passage_findings",
    "get_primary_intent",
    "get_request_attr",
    "get_score_profile_override",
    "get_sensitivity",
    "get_target_action",
    "get_triples",
    "get_warnings",
    "is_numeric_claim",
    "normalize_name",
    "passage_index",
    "passage_section_map",
    "passages_by_section",
    "resolve_entity",
]
