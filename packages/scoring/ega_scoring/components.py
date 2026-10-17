"""Deterministic sub-score computations for the seven core components (PRD §9.2).

Every ``compute_*`` function is a pure function from structured workflow state
(entities, EAV rows, triples, fan-out/coverage, passages, claims, findings) to
a ``ScoreComponent``. Nothing here calls an LLM, touches the network, or
guesses: when the state lacks evidence for a component the result is
``value=None, not_assessed=True`` with the reason recorded, and sub-dimensions
without evidence are excluded and their weights re-normalized (PRD §9.4:
"Never silently count N/A as zero").
"""

from __future__ import annotations

import re
from typing import Any, Optional, Sequence

from ega_parsers.metrics import detect_repeated_phrases, extract_sentences
from ega_schemas.entities import Entity
from ega_schemas.enums import (
    Confidence,
    CoverageStatus,
    EAVStatus,
    EntityKind,
    IntentClass,
    PageType,
    QueryOrigin,
    QueryScope,
    ScoreKey,
    TripleStatus,
    TripleType,
    VerificationState,
)
from ega_schemas.triples import SemanticTriple

from auditor.rules.attributes import REQUIRED_ATTRIBUTES, satisfied_attribute_keys
from auditor.rules.brand_rules import detect_banned_terms, detect_canonical_fact_conflicts
from auditor.rules.page_profiles import get_profile
from ega_scoring.models import ScoreComponent, combine_sub_scores
from ega_scoring.rubric import clamp, confidence_for
from ega_scoring.state import (
    build_entity_index,
    central_entity_node,
    claim_has_dated_context,
    claim_is_fabrication_risk,
    claim_is_unverified,
    document_text,
    get_banned_terms,
    get_canonical_facts,
    get_claims,
    get_coverage_rows,
    get_document,
    get_eav_rows,
    get_entities,
    get_evidence_sources,
    get_fanout,
    get_findings,
    get_language,
    get_location_target,
    get_page_type,
    get_triples,
    get_warnings,
    is_numeric_claim,
    normalize_name,
    passage_index,
    passage_section_map,
    passages_by_section,
    resolve_entity,
)

# --------------------------------------------------------------------------
# Sub-score weight tables (PRD §9.2 A–G, exact defaults)
# --------------------------------------------------------------------------

EOS_WEIGHTS: dict[str, float] = {
    "central_entity_clarity": 0.20,
    "supporting_entity_relevance": 0.15,
    "attribute_value_completeness": 0.15,
    "primary_intent_coverage": 0.15,
    "naming_consistency": 0.10,
    "trust_authority_entities": 0.10,
    "page_type_fit": 0.10,
    "semantic_coherence": 0.05,
}

#: Local pages reallocate up to 10 percentage points toward local relevance (PRD §9.2.A).
EOS_LOCAL_WEIGHTS: dict[str, float] = {
    "central_entity_clarity": 0.18,
    "supporting_entity_relevance": 0.14,
    "attribute_value_completeness": 0.14,
    "primary_intent_coverage": 0.13,
    "naming_consistency": 0.10,
    "trust_authority_entities": 0.09,
    "page_type_fit": 0.09,
    "semantic_coherence": 0.03,
    "local_relevance": 0.10,
}

ERS_WEIGHTS: dict[str, float] = {
    "problem_solution": 0.15,
    "capability_outcome": 0.15,
    "process_mechanism_result": 0.15,
    "entity_attribute_clarity": 0.15,
    "cause_effect_accuracy": 0.15,
    "claim_evidence_connection": 0.15,
    "local_context_relationships": 0.05,
    "section_continuity": 0.05,
}

KGR_WEIGHTS: dict[str, float] = {
    "central_entity_triples": 0.30,
    "required_attribute_values": 0.20,
    "canonical_naming": 0.15,
    "brand_consistency": 0.15,
    "entity_type_coherence": 0.10,
    "proof_source_links": 0.10,
}

PRS_WEIGHTS: dict[str, float] = {
    "answer_first_opening": 0.20,
    "named_subject_anchors": 0.15,
    "standalone_passage_comprehension": 0.20,
    "evidence_adjacency": 0.15,
    "answer_shape_fit": 0.10,
    "priority_information_early": 0.10,
    "hierarchy_redundancy_control": 0.10,
}

CWS_WEIGHTS: dict[str, float] = {
    "original_first_party": 0.25,
    "verifiable_evidence_sourcing": 0.20,
    "information_beyond_restatement": 0.20,
    "first_hand_expertise": 0.15,
    "claim_precision_dating": 0.10,
    "attribution_quality": 0.10,
}

HRS_WEIGHTS: dict[str, float] = {
    "clarity_plain_language": 0.20,
    "structure_scannability": 0.15,
    "practical_completeness": 0.20,
    "relevance_no_filler": 0.15,
    "tone_terminology": 0.10,
    "examples_decision_support": 0.10,
    "conversion_next_step": 0.10,
}

# --------------------------------------------------------------------------
# Static entity/intent maps
# --------------------------------------------------------------------------

TRUST_KINDS: frozenset[EntityKind] = frozenset(
    {EntityKind.PROOF, EntityKind.STANDARD, EntityKind.REGULATION, EntityKind.PERSON}
)

RELEVANT_KINDS: dict[PageType, frozenset[EntityKind]] = {
    PageType.HOMEPAGE: frozenset({EntityKind.BRAND, EntityKind.ORGANIZATION, EntityKind.PRODUCT_SERVICE, EntityKind.CTA}),
    PageType.ABOUT: frozenset({EntityKind.ORGANIZATION, EntityKind.BRAND, EntityKind.PERSON, EntityKind.DATE, EntityKind.OUTCOME}),
    PageType.SERVICE: frozenset({EntityKind.PRODUCT_SERVICE, EntityKind.PROCESS, EntityKind.PRICE, EntityKind.OUTCOME, EntityKind.AUDIENCE, EntityKind.USE_CASE, EntityKind.PROBLEM}),
    PageType.LOCAL_SERVICE: frozenset({EntityKind.LOCATION, EntityKind.PRODUCT_SERVICE, EntityKind.PROCESS, EntityKind.PRICE, EntityKind.AUDIENCE, EntityKind.PROBLEM, EntityKind.OUTCOME}),
    PageType.ARTICLE: frozenset({EntityKind.CONCEPT, EntityKind.PERSON, EntityKind.PROBLEM, EntityKind.OUTCOME, EntityKind.PROCESS, EntityKind.METRIC, EntityKind.TOOL, EntityKind.DATE}),
    PageType.GLOSSARY: frozenset({EntityKind.CONCEPT, EntityKind.PROCESS, EntityKind.TOOL, EntityKind.MATERIAL, EntityKind.STANDARD, EntityKind.OUTCOME, EntityKind.PROBLEM}),
    PageType.LISTICLE: frozenset({EntityKind.PRODUCT_SERVICE, EntityKind.CONCEPT, EntityKind.COMPETITOR, EntityKind.USE_CASE, EntityKind.PRICE, EntityKind.METRIC}),
    PageType.COMPARISON: frozenset({EntityKind.COMPETITOR, EntityKind.PRODUCT_SERVICE, EntityKind.CONCEPT, EntityKind.METRIC, EntityKind.PRICE, EntityKind.USE_CASE}),
    PageType.CASE_STUDY: frozenset({EntityKind.ORGANIZATION, EntityKind.PERSON, EntityKind.METRIC, EntityKind.PROCESS, EntityKind.OUTCOME, EntityKind.PROBLEM, EntityKind.PRODUCT_SERVICE, EntityKind.DATE}),
    PageType.SAAS_B2B: frozenset({EntityKind.PRODUCT_SERVICE, EntityKind.AUDIENCE, EntityKind.USE_CASE, EntityKind.PRICE, EntityKind.PROBLEM, EntityKind.OUTCOME, EntityKind.PLATFORM, EntityKind.STANDARD}),
    PageType.INTEGRATION: frozenset({EntityKind.PLATFORM, EntityKind.TOOL, EntityKind.PROCESS, EntityKind.PRODUCT_SERVICE, EntityKind.STANDARD, EntityKind.CONCEPT}),
    PageType.PAID_LANDING: frozenset({EntityKind.PRODUCT_SERVICE, EntityKind.CTA, EntityKind.PRICE, EntityKind.AUDIENCE, EntityKind.PROOF, EntityKind.USE_CASE}),
    PageType.PRODUCT_CATEGORY: frozenset({EntityKind.PRODUCT_SERVICE, EntityKind.PRICE, EntityKind.MATERIAL, EntityKind.METRIC, EntityKind.USE_CASE, EntityKind.COMPETITOR}),
    PageType.TRUST_POLICY: frozenset({EntityKind.STANDARD, EntityKind.REGULATION, EntityKind.ORGANIZATION, EntityKind.PROOF, EntityKind.PERSON}),
    PageType.DOCS: frozenset({EntityKind.PROCESS, EntityKind.TOOL, EntityKind.PLATFORM, EntityKind.CONCEPT, EntityKind.PROBLEM, EntityKind.PRODUCT_SERVICE}),
    PageType.GENERAL: frozenset(
        {EntityKind.CONCEPT, EntityKind.PROCESS, EntityKind.PRODUCT_SERVICE, EntityKind.PERSON,
         EntityKind.ORGANIZATION, EntityKind.LOCATION, EntityKind.PROBLEM, EntityKind.OUTCOME, EntityKind.METRIC}
    ),
}

EXPECTED_CENTRAL_KINDS: dict[PageType, frozenset[EntityKind]] = {
    PageType.HOMEPAGE: frozenset({EntityKind.BRAND, EntityKind.ORGANIZATION}),
    PageType.ABOUT: frozenset({EntityKind.ORGANIZATION, EntityKind.BRAND}),
    PageType.SERVICE: frozenset({EntityKind.PRODUCT_SERVICE, EntityKind.BRAND}),
    PageType.LOCAL_SERVICE: frozenset({EntityKind.PRODUCT_SERVICE, EntityKind.LOCATION, EntityKind.BRAND}),
    PageType.ARTICLE: frozenset({EntityKind.CONCEPT}),
    PageType.GLOSSARY: frozenset({EntityKind.CONCEPT}),
    PageType.LISTICLE: frozenset({EntityKind.CONCEPT, EntityKind.USE_CASE}),
    PageType.COMPARISON: frozenset({EntityKind.COMPETITOR, EntityKind.PRODUCT_SERVICE, EntityKind.CONCEPT}),
    PageType.CASE_STUDY: frozenset({EntityKind.ORGANIZATION, EntityKind.PRODUCT_SERVICE}),
    PageType.SAAS_B2B: frozenset({EntityKind.PRODUCT_SERVICE, EntityKind.BRAND}),
    PageType.INTEGRATION: frozenset({EntityKind.PLATFORM, EntityKind.PRODUCT_SERVICE}),
    PageType.PAID_LANDING: frozenset({EntityKind.PRODUCT_SERVICE, EntityKind.BRAND}),
    PageType.PRODUCT_CATEGORY: frozenset({EntityKind.PRODUCT_SERVICE, EntityKind.CONCEPT}),
    PageType.TRUST_POLICY: frozenset({EntityKind.ORGANIZATION, EntityKind.STANDARD}),
    PageType.DOCS: frozenset({EntityKind.CONCEPT, EntityKind.PROCESS, EntityKind.PRODUCT_SERVICE}),
    PageType.GENERAL: frozenset(),
}

#: Which entity kinds evidence which search intent.
INTENT_ENTITY_KINDS: dict[IntentClass, frozenset[EntityKind]] = {
    IntentClass.INFORMATIONAL: frozenset({EntityKind.CONCEPT, EntityKind.PROCESS}),
    IntentClass.COMMERCIAL: frozenset({EntityKind.PRICE, EntityKind.PRODUCT_SERVICE}),
    IntentClass.TRANSACTIONAL: frozenset({EntityKind.CTA, EntityKind.PRICE}),
    IntentClass.NAVIGATIONAL: frozenset({EntityKind.BRAND, EntityKind.ORGANIZATION}),
    IntentClass.LOCAL: frozenset({EntityKind.LOCATION}),
    IntentClass.COMPARISON: frozenset({EntityKind.COMPETITOR}),
    IntentClass.EVALUATION: frozenset({EntityKind.PROOF, EntityKind.METRIC, EntityKind.STANDARD}),
    IntentClass.RESEARCH: frozenset({EntityKind.METRIC, EntityKind.STANDARD}),
}

SELF_CONTAINMENT_ISSUES: frozenset[str] = frozenset(
    {"not_self_contained", "context_dependent", "pronoun_reference", "dangling_reference", "missing_subject", "needs_context"}
)

ADJACENCY_ISSUES: frozenset[str] = frozenset(
    {"evidence_adjacency", "claim_without_evidence", "evidence_gap", "unsupported_claim", "missing_citation"}
)

_INFORMATION_GAIN_CATEGORIES: frozenset[str] = frozenset(
    {"information_gain", "original_data", "original_research", "first_party"}
)

_RESTATEMENT_CATEGORIES: frozenset[str] = frozenset({"restatement", "thin_content", "duplicate_content"})

_FLESCH_LANGUAGES: frozenset[str] = frozenset({"en", "en-us", "en-gb", "es", "fr", "de", "pt", "it", "nl", "id"})

_LANGUAGE_WARNING_RE = re.compile(r"readability|flesch|non-latin|script|language", re.IGNORECASE)

_CTA_VERB_RE = re.compile(
    r"\b(get started|start (?:a )?(?:free )?trial|sign up|book (?:a )?(?:call|demo|consultation|appointment)"
    r"|request (?:a )?(?:demo|quote|pricing)|schedule|contact us|buy now|add to cart|download"
    r"|talk to (?:us|sales)|chat with|request a callback|see pricing)\b",
    re.IGNORECASE,
)

_OFFER_RE = re.compile(
    r"(\d+\s*%\s*off|free trial|free plan|money[- ]back|from\s*\$|discount|no credit card|pricing(?: starts)?)",
    re.IGNORECASE,
)

_EXAMPLE_MARKER_RE = re.compile(r"\b(e\.g\.|for example|such as|example:)\b", re.IGNORECASE)

_NUMBERED_LIST_RE = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s+\S", re.MULTILINE)

_PROBLEM_PREDICATE_WORDS = ("solve", "fix", "address", "prevent", "help", "treat", "resolve")
_CAPABILITY_PREDICATE_WORDS = ("enable", "allow", "deliver", "provide", "power", "reduce", "increase", "improve")

_TRIPLE_CREDIT: dict[TripleStatus, float] = {
    TripleStatus.EXPLICIT: 1.0,
    TripleStatus.IMPLIED: 0.5,
    TripleStatus.MISSING: 0.0,
    TripleStatus.UNSUPPORTED: -0.5,
    TripleStatus.WRONG: -1.0,
}

_EAV_CREDIT: dict[EAVStatus, float] = {
    EAVStatus.EXPLICIT: 1.0,
    EAVStatus.VAGUE: 0.4,
    EAVStatus.UNVERIFIED: 0.4,
    EAVStatus.CONFLICTING: 0.4,
    EAVStatus.MISSING: 0.0,
}

_LABELS = {
    ScoreKey.EOS: "Entity Optimization Score",
    ScoreKey.ERS: "Entity Relationship Score",
    ScoreKey.KGR: "Knowledge-Graph Readiness",
    ScoreKey.FCS: "Fan-out Coverage Score",
    ScoreKey.PRS: "Passage Retrievability Score",
    ScoreKey.CWS: "Citation-Worthiness / Information Gain",
    ScoreKey.HRS: "Human Readability & Utility",
    ScoreKey.INTENT: "Intent Alignment",
    ScoreKey.LOCAL_FIT: "Local Fit",
    ScoreKey.PAID_FIT: "Paid Landing Page Fit",
    ScoreKey.CONVERSION: "Conversion Readiness",
    ScoreKey.TRUST: "Trust / E-E-A-T Coverage",
    ScoreKey.LINKS: "Internal-Link Readiness",
}


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def _label(key: ScoreKey) -> str:
    return _LABELS.get(key, key.value)


def label_for(key: ScoreKey) -> str:
    """Human-readable label for any component key (PRD §9.2 core, §9.3 optional)."""
    return _LABELS.get(key, key.value)


def _build(
    key: ScoreKey,
    sub_scores: dict[str, float],
    sub_weights: dict[str, float],
    lost_points: list[str],
    rationale: str,
    observations: int,
    *,
    notes: Optional[list[str]] = None,
    confidence: Optional[Any] = None,
    floor: float = 0.0,
) -> ScoreComponent:
    """Assemble a ScoreComponent, re-normalizing over included sub-scores."""
    value, re_normalized, used = combine_sub_scores(sub_scores, sub_weights, floor=floor)
    notes = list(notes or [])
    excluded = [name for name in sub_weights if name not in sub_scores]
    if value is None:
        return ScoreComponent.unassessed(
            key,
            _label(key),
            "No sub-score of " + key.value + " had supporting evidence in the run state — not assessed (PRD §9.1).",
        )
    full_rationale = rationale
    if excluded:
        note = (
            f"Sub-scores excluded for lack of evidence (weights re-normalized): {', '.join(sorted(excluded))}."
        )
        notes.append(note)
    if re_normalized and not excluded:
        notes.append("Sub-score weights re-normalized over assessed dimensions (PRD §9.4).")
    if notes:
        full_rationale = full_rationale + " " + " ".join(notes)
    return ScoreComponent(
        score_key=key,
        label=_label(key),
        value=value,
        sub_scores=sub_scores,
        sub_weights=used,
        renormalized=re_normalized or bool(excluded),
        lost_points=lost_points,
        rationale=full_rationale,
        confidence=confidence or confidence_for(observations),
        observations=observations,
        notes=notes,
    )


def _triple_credit_score(triples: Sequence[SemanticTriple]) -> float:
    """10 × mean per-triple credit; unsupported/wrong relationships subtract (PRD §9.2.B)."""
    if not triples:
        return 1.0
    total = sum(_TRIPLE_CREDIT.get(t.status, 0.0) for t in triples)
    return clamp(10.0 * total / len(triples))


def _predicate_has(predicate: str, words: tuple[str, ...]) -> bool:
    normalized = normalize_name(predicate)
    return any(word in normalized for word in words)


def _kind_of(index: dict[str, Entity], name: Any) -> Optional[EntityKind]:
    entity = resolve_entity(index, name)
    return entity.kind if entity is not None else None


def _central_triples(
    triples: Sequence[SemanticTriple], index: dict[str, Entity], central: Optional[Entity], central_name: str
) -> list[SemanticTriple]:
    target_norm = normalize_name(central.canonical_name if central is not None else central_name)
    if not target_norm:
        return []
    result = []
    for triple in triples:
        resolved = resolve_entity(index, triple.subject)
        if (central is not None and resolved is central) or normalize_name(triple.subject) == target_norm:
            result.append(triple)
    return result


def _default_audience(state: Any) -> Optional[str]:
    from ega_scoring.state import get_audience

    audience = get_audience(state)
    if not audience or str(audience).strip().lower() in {"general audience", "general", "everyone"}:
        return None
    return str(audience)


# --------------------------------------------------------------------------
# EOS — Entity Optimization Score (PRD §9.2.A)
# --------------------------------------------------------------------------


def compute_eos(state: Any) -> ScoreComponent:
    """Entity Optimization Score: right central entity, attributes, focus and fit."""
    page_type = get_page_type(state)
    profile = get_profile(page_type)
    entities = get_entities(state)
    eav_rows = get_eav_rows(state)
    triples = get_triples(state)
    fanout = get_fanout(state)
    coverage_rows = get_coverage_rows(state)
    document = get_document(state)

    if not entities and not eav_rows:
        return ScoreComponent.unassessed(
            ScoreKey.EOS,
            _label(ScoreKey.EOS),
            "No entity inventory and no attribute-value rows in the run state — "
            "EOS cannot be assessed without evidence of what the page is about (PRD §9.1).",
        )

    index = build_entity_index(entities)
    central = central_entity_node(state)
    central_name = central.canonical_name if central is not None else ""
    sub_scores: dict[str, float] = {}
    lost: list[str] = []
    notes: list[str] = []

    # 1) Central entity clarity and salience (20%)
    subject_triples = _central_triples(triples, index, central, central_name)
    if central is not None:
        salience = float(central.salience)
        score = 5.0 + 2.0 * min(1.0, salience * 1.5)
        if subject_triples:
            score += min(3.0, 0.75 * len(subject_triples))
        else:
            score -= 1.5
            lost.append(
                f"Central entity '{central_name}' appears as subject in 0 of {len(triples)} triples."
            )
        sub_scores["central_entity_clarity"] = clamp(score)
    elif central_name:
        sub_scores["central_entity_clarity"] = 3.5
        lost.append(
            f"Declared central entity '{central_name}' matched none of the {len(entities)} extracted entities."
        )
    else:
        sub_scores["central_entity_clarity"] = 2.0
        lost.append("No central entity is flagged or declared; the page has no semantic anchor.")

    # 2) Relevance of supporting entities (15%)
    supporting = [e for e in entities if e is not central]
    relevant_kinds = RELEVANT_KINDS.get(page_type, RELEVANT_KINDS[PageType.GENERAL])
    if not supporting:
        sub_scores["supporting_entity_relevance"] = 2.0
        lost.append("0 supporting entities beyond the central one — severe entity gap.")
    else:
        relevant = sum(1 for e in supporting if e.kind in relevant_kinds)
        share = relevant / len(supporting)
        sub_scores["supporting_entity_relevance"] = max(1.5, 10.0 * share)
        if relevant < len(supporting):
            lost.append(
                f"{len(supporting) - relevant} of {len(supporting)} supporting entities are "
                f"off-profile kinds for a {profile.label} page."
            )

    # 3) Attribute/value completeness (15%)
    applicable = [r for r in eav_rows if r.status != EAVStatus.NOT_APPLICABLE]
    if not eav_rows:
        sub_scores["attribute_value_completeness"] = 2.0
        lost.append("0 entity-attribute rows captured — attribute completeness cannot be established.")
    elif not applicable:
        notes.append("All attribute rows are not-applicable; attribute completeness excluded.")
    else:
        credit = sum(_EAV_CREDIT.get(r.status, 0.0) for r in applicable if r.value or r.status == EAVStatus.MISSING)
        explicit = sum(1 for r in applicable if r.status == EAVStatus.EXPLICIT and r.value)
        sub_scores["attribute_value_completeness"] = clamp(10.0 * credit / len(applicable))
        if explicit < len(applicable):
            lost.append(
                f"{explicit} of {len(applicable)} applicable attribute rows have explicit values "
                f"({len(applicable) - explicit} vague, conflicting, unverified or missing)."
            )

    # 4) Primary-intent and entity coverage (15%)
    in_scope = [q for q in fanout if q.scope != QueryScope.OUT_OF_SCOPE]
    if not in_scope:
        notes.append(
            "Primary-intent coverage excluded: no fan-out queries in the run state (weights re-normalized)."
        )
    else:
        row_by_id = {row.query_id: row for row in coverage_rows}
        intents = {q.intent for q in in_scope}
        covered: set[IntentClass] = set()
        for query in in_scope:
            row = row_by_id.get(query.query_id)
            if row is not None and row.status in (CoverageStatus.COVERED, CoverageStatus.PARTIAL):
                covered.add(query.intent)
        for intent in intents:
            kinds = INTENT_ENTITY_KINDS.get(intent, frozenset())
            if any(e.kind in kinds for e in entities):
                covered.add(intent)
        sub_scores["primary_intent_coverage"] = 10.0 * len(covered) / len(intents)
        if covered != intents:
            missing = ", ".join(sorted(i.value for i in intents - covered))
            lost.append(
                f"{len(intents) - len(covered)} of {len(intents)} fan-out intents ({missing}) "
                f"have neither a covering entity nor a covered section."
            )

    # 5) Naming consistency and disambiguation (10%)
    norm_to_canonical: dict[str, str] = {}
    collisions = 0
    ambiguous_pairs = 0
    for entity in entities:
        normalized = normalize_name(entity.canonical_name)
        if normalized in norm_to_canonical and norm_to_canonical[normalized] != entity.canonical_name:
            collisions += 1
        norm_to_canonical[normalized] = entity.canonical_name
    normalized_names = sorted(norm_to_canonical)
    for i, name_a in enumerate(normalized_names):
        for name_b in normalized_names[i + 1 :]:
            if name_a != name_b and (name_a in name_b or name_b in name_a):
                ent_a, ent_b = norm_to_canonical[name_a], norm_to_canonical[name_b]
                disambiguated = any(
                    e.aliases or e.wikidata_id for e in entities if e.canonical_name in (ent_a, ent_b)
                )
                if not disambiguated:
                    ambiguous_pairs += 1
    naming = 9.0 - 3.0 * collisions - 1.5 * min(2, ambiguous_pairs)
    if len(entities) >= 3 and not any(e.aliases for e in entities):
        naming -= 1.0
        lost.append(
            f"None of the {len(entities)} entities carries an alias/disambiguation surface form."
        )
    if collisions:
        lost.append(
            f"{collisions} entities share a normalized name with a different canonical spelling — "
            f"inconsistent naming."
        )
    if ambiguous_pairs and not collisions:
        lost.append(
            f"{ambiguous_pairs} similar entity labels lack disambiguation (aliases or external IDs)."
        )
    sub_scores["naming_consistency"] = clamp(naming)

    # 6) Relevant trust/authority entities (10%)
    trust_count = sum(1 for e in entities if e.kind in TRUST_KINDS)
    sub_scores["trust_authority_entities"] = min(10.0, 3.0 + 2.5 * trust_count)
    if trust_count == 0:
        lost.append(
            "0 trust/authority entities (PROOF/STANDARD/REGULATION/PERSON) in the inventory."
        )

    # 7) Page-type fit (10%)
    required = REQUIRED_ATTRIBUTES.get(page_type, [])
    expected_kinds = EXPECTED_CENTRAL_KINDS.get(page_type, frozenset())
    satisfied = satisfied_attribute_keys(eav_rows)
    matched_required = [spec for spec in required if spec.key in satisfied]
    kind_ok = central.kind in expected_kinds if central is not None and expected_kinds else None
    if not required and not expected_kinds:
        notes.append("Page-type fit excluded: no required attributes or expected central kind for this type.")
    else:
        parts: list[float] = []
        weights: list[float] = []
        if required:
            attr_cov = len(matched_required) / len(required)
            parts.append(10.0 * attr_cov)
            weights.append(0.7)
            if len(matched_required) < len(required):
                missing = [spec.key for spec in required if spec.key not in satisfied]
                lost.append(
                    f"{len(required) - len(matched_required)} of {len(required)} required attributes for "
                    f"{profile.label} lack explicit values ({', '.join(missing[:5])})."
                )
        if expected_kinds:
            parts.append(10.0 if kind_ok else 0.0)
            weights.append(0.3)
            if kind_ok is False:
                expected = "/".join(sorted(k.value for k in expected_kinds))
                actual = central.kind.value if central is not None else "none"
                lost.append(
                    f"Central entity kind '{actual}' is off-profile for {profile.label} (expected {expected})."
                )
        sub_scores["page_type_fit"] = sum(p * w for p, w in zip(parts, weights, strict=False)) / sum(weights)

    # 8) Semantic coherence / absence of entity stuffing (5%)
    n_entities = len(entities)
    low_salience = sum(1 for e in entities if float(e.salience) < 0.15)
    other_kind = sum(1 for e in entities if e.kind == EntityKind.OTHER)
    coherence = 10.0 * (1 - 0.6 * (low_salience / n_entities) - 0.4 * (other_kind / n_entities))
    repeated = detect_repeated_phrases(document_text(state), 3, 4) if document is not None else []
    if repeated:
        coherence -= min(3.0, float(len(repeated)))
        lost.append(
            f"{len(repeated)} repeated 3-gram patterns (≥4 occurrences each) signal entity stuffing."
        )
    if low_salience:
        lost.append(
            f"{low_salience} of {n_entities} entities carry salience <0.15 — likely decorative mentions."
        )
    sub_scores["semantic_coherence"] = clamp(coherence)

    # 9) Local relevance — only for local profiles (PRD §9.2.A)
    if profile.local_relevant:
        locations = [e for e in entities if e.kind == EntityKind.LOCATION]
        local_target = get_location_target(state)
        if not locations:
            sub_scores["local_relevance"] = 1.0
            lost.append("0 geographic entities on a local service page — local relevance absent.")
        else:
            local_score = 4.0
            total_salience = sum(float(e.salience) for e in locations) or 1.0
            dominant = max(float(e.salience) for e in locations) / total_salience
            if dominant >= 0.6:
                local_score += 3.0
            else:
                local_score += 1.0
                lost.append(
                    f"No dominant geographic entity — top location holds only {dominant:.0%} of local salience."
                )
            text_norm = normalize_name(document_text(state))
            if local_target:
                target_norm = normalize_name(local_target)
                if target_norm and (target_norm in text_norm or any(
                    normalize_name(e.canonical_name) == target_norm for e in locations
                )):
                    local_score += 1.5
                else:
                    lost.append(f"Location target '{local_target}' never appears in the page content.")
            geo_triples = [t for t in triples if t.triple_type == TripleType.GEOGRAPHY]
            area_rows = [
                r for r in eav_rows
                if normalize_name(r.attribute) in {"service area", "coverage area", "location"}
                and r.status == EAVStatus.EXPLICIT
            ]
            if geo_triples or area_rows:
                local_score += 1.5
            else:
                lost.append("No service-area/coverage signals (geography triples or area attributes).")
            sub_scores["local_relevance"] = clamp(local_score)
    else:
        notes.append(
            f"Local relevance not applicable for a {profile.label} page — LOCATION entities are "
            f"excluded so they cannot lower EOS (PRD §9.2.A)."
        )

    weights = EOS_LOCAL_WEIGHTS if profile.local_relevant else EOS_WEIGHTS
    observations = len(entities) + len(eav_rows)
    rationale = (
        f"EOS assessed across {len(entities)} entities, {len(eav_rows)} attribute rows and "
        f"{len(triples)} triples on a {profile.label} page."
    )
    return _build(
        ScoreKey.EOS,
        sub_scores,
        weights,
        lost,
        rationale,
        observations,
        notes=notes,
    )


# --------------------------------------------------------------------------
# ERS — Entity Relationship Score (PRD §9.2.B)
# --------------------------------------------------------------------------


def compute_ers(state: Any) -> ScoreComponent:
    """Entity Relationship Score: clear, accurate, useful entity relationships."""
    page_type = get_page_type(state)
    profile = get_profile(page_type)
    entities = get_entities(state)
    triples = get_triples(state)
    claims = get_claims(state)
    eav_rows = get_eav_rows(state)
    document = get_document(state)

    if not triples and not claims and not eav_rows:
        return ScoreComponent.unassessed(
            ScoreKey.ERS,
            _label(ScoreKey.ERS),
            "No triples, claims or attribute rows in the run state — ERS cannot be assessed (PRD §9.1).",
        )

    index = build_entity_index(entities)
    sub_scores: dict[str, float] = {}
    lost: list[str] = []
    notes: list[str] = []

    def penalize_bad(category: str, items: Sequence[SemanticTriple]) -> None:
        bad = sum(1 for t in items if t.status in (TripleStatus.UNSUPPORTED, TripleStatus.WRONG))
        if bad:
            lost.append(
                f"{bad} of {len(items)} {category} relationships are unsupported/wrong and were "
                f"penalized even where they sound plausible (PRD §9.2.B)."
            )

    # 1) Problem → solution (15%)
    problem_solution = [
        t for t in triples
        if _kind_of(index, t.subject) == EntityKind.PROBLEM or _predicate_has(t.predicate, _PROBLEM_PREDICATE_WORDS)
    ]
    if problem_solution:
        sub_scores["problem_solution"] = _triple_credit_score(problem_solution)
        penalize_bad("problem→solution", problem_solution)
    else:
        sub_scores["problem_solution"] = 1.0
        lost.append(
            f"0 problem→solution relationships among {len(triples)} triples — narrow relationship variety."
        )

    # 2) Capability → outcome (15%)
    capability_outcome = [
        t for t in triples
        if t.triple_type == TripleType.OUTCOME
        or (
            _kind_of(index, t.subject) in {EntityKind.PRODUCT_SERVICE, EntityKind.TOOL, EntityKind.PLATFORM}
            and _kind_of(index, t.object_) in {EntityKind.OUTCOME, EntityKind.METRIC}
        )
        or (
            _predicate_has(t.predicate, _CAPABILITY_PREDICATE_WORDS)
            and _kind_of(index, t.object_) in {EntityKind.OUTCOME, EntityKind.METRIC}
        )
    ]
    if capability_outcome:
        sub_scores["capability_outcome"] = _triple_credit_score(capability_outcome)
        penalize_bad("capability→outcome", capability_outcome)
    else:
        sub_scores["capability_outcome"] = 1.0
        lost.append("0 capability→outcome relationships — benefits are asserted, not related to entities.")

    # 3) Process → mechanism → result (15%)
    process_result = [
        t for t in triples
        if t.triple_type == TripleType.PROCESS or _kind_of(index, t.subject) == EntityKind.PROCESS
    ]
    if process_result:
        sub_scores["process_mechanism_result"] = _triple_credit_score(process_result)
        penalize_bad("process→mechanism→result", process_result)
    else:
        sub_scores["process_mechanism_result"] = 1.0
        lost.append("0 process→mechanism→result relationships — the 'how' is not structured.")

    # 4) Entity → attribute/value clarity (15%)
    applicable = [r for r in eav_rows if r.status != EAVStatus.NOT_APPLICABLE]
    if not eav_rows:
        notes.append("Entity→attribute clarity excluded: no attribute rows captured (weights re-normalized).")
    elif not applicable:
        notes.append("Entity→attribute clarity excluded: all attribute rows are not-applicable.")
    else:
        explicit = sum(1 for r in applicable if r.status == EAVStatus.EXPLICIT and r.value)
        sub_scores["entity_attribute_clarity"] = 10.0 * explicit / len(applicable)
        if explicit < len(applicable):
            lost.append(
                f"{len(applicable) - explicit} of {len(applicable)} attribute relationships lack explicit values."
            )

    # 5) Cause/effect accuracy and qualification (15%)
    cause_effect = [t for t in triples if t.triple_type == TripleType.CAUSE_EFFECT]
    if cause_effect:
        sub_scores["cause_effect_accuracy"] = _triple_credit_score(cause_effect)
        penalize_bad("cause/effect", cause_effect)
    else:
        sub_scores["cause_effect_accuracy"] = 1.0
        lost.append(
            f"0 cause/effect relationships among {len(triples)} triples — causal claims are unqualified or absent."
        )

    # 6) Claim → evidence connection (15%)
    if not claims:
        notes.append("Claim→evidence connection excluded: the claim ledger is empty (weights re-normalized).")
    else:
        linked = [
            c for c in claims
            if c.evidence_source_ids or c.verification_state == VerificationState.VERIFIED
        ]
        sub_scores["claim_evidence_connection"] = 10.0 * len(linked) / len(claims)
        if len(linked) < len(claims):
            lost.append(
                f"{len(claims) - len(linked)} of {len(claims)} claims have no linked evidence source."
            )

    # 7) Local/audience/context relationships (5%)
    audience = _default_audience(state)
    if profile.local_relevant or audience:
        contextual = [
            t for t in triples
            if t.triple_type in (TripleType.GEOGRAPHY, TripleType.AUDIENCE)
            or _kind_of(index, t.subject) in {EntityKind.LOCATION, EntityKind.AUDIENCE}
            or _kind_of(index, t.object_) in {EntityKind.LOCATION, EntityKind.AUDIENCE}
        ]
        if contextual:
            sub_scores["local_context_relationships"] = _triple_credit_score(contextual)
            penalize_bad("local/audience", contextual)
        else:
            sub_scores["local_context_relationships"] = 1.0
            lost.append(
                "0 local/audience/context relationships despite a local or audience-targeted page."
            )
    else:
        notes.append(
            "Local/audience/context relationships not applicable for this page type — sub-score excluded."
        )

    # 8) Continuity across sections (5%)
    if document is None or not any(e.occurrences for e in entities):
        notes.append(
            "Section continuity excluded: no parsed document or no entity occurrences to trace (weights re-normalized)."
        )
    else:
        section_map = passage_section_map(document)
        with_occurrences = [e for e in entities if e.occurrences]
        multi = sum(
            1
            for e in with_occurrences
            if len({section_map.get(o.passage_id, o.passage_id) for o in e.occurrences}) >= 2
        )
        sub_scores["section_continuity"] = 10.0 * multi / len(with_occurrences)
        if multi < len(with_occurrences):
            lost.append(
                f"{len(with_occurrences) - multi} of {len(with_occurrences)} entities appear in only "
                f"one section — weak cross-section continuity."
            )

    observations = len(triples) + len(claims)
    rationale = (
        f"ERS assessed from {len(triples)} triples and {len(claims)} claims on a {profile.label} page."
    )
    return _build(ScoreKey.ERS, sub_scores, ERS_WEIGHTS, lost, rationale, observations)


# --------------------------------------------------------------------------
# KGR — Knowledge-Graph Readiness (PRD §9.2.C)
# --------------------------------------------------------------------------


def compute_kgr(state: Any) -> ScoreComponent:
    """Knowledge-Graph Readiness: explicit central triples, values, naming, proof."""
    page_type = get_page_type(state)
    entities = get_entities(state)
    triples = get_triples(state)
    eav_rows = get_eav_rows(state)
    claims = get_claims(state)

    if not entities and not triples and not eav_rows:
        return ScoreComponent.unassessed(
            ScoreKey.KGR,
            _label(ScoreKey.KGR),
            "No entities, triples or attribute rows in the run state — KGR cannot be assessed (PRD §9.1).",
        )

    index = build_entity_index(entities)
    central = central_entity_node(state)
    sub_scores: dict[str, float] = {}
    lost: list[str] = []
    notes: list[str] = []

    # 1) Essential central-entity triples explicit and accurate (30%)
    central_triples = _central_triples(triples, index, central, "")
    if central is None:
        sub_scores["central_entity_triples"] = 1.0
        lost.append("No central entity to anchor knowledge-graph nodes — 0 anchored triples.")
    elif not central_triples:
        sub_scores["central_entity_triples"] = 1.0
        lost.append(
            f"0 of {len(triples)} triples anchor the central entity '{central.canonical_name}'."
        )
    else:
        sub_scores["central_entity_triples"] = _triple_credit_score(central_triples)
        explicit_core = sum(
            1 for t in central_triples
            if t.status == TripleStatus.EXPLICIT and t.triple_type in (TripleType.CATEGORY, TripleType.CAPABILITY)
        )
        if explicit_core < len(central_triples):
            lost.append(
                f"{explicit_core} of {len(central_triples)} central triples are explicit category/capability statements."
            )

    # 2) Required EAV attributes have values (20%)
    required = REQUIRED_ATTRIBUTES.get(page_type, [])
    satisfied = satisfied_attribute_keys(eav_rows)
    applicable = [r for r in eav_rows if r.status != EAVStatus.NOT_APPLICABLE]
    if required:
        matched = [s for s in required if s.key in satisfied]
        sub_scores["required_attribute_values"] = 10.0 * len(matched) / len(required)
        if len(matched) < len(required):
            missing = [spec.key for spec in required if spec.key not in satisfied]
            lost.append(
                f"{len(required) - len(matched)} of {len(required)} required attributes have no explicit "
                f"value ({', '.join(missing[:5])})."
            )
    elif applicable:
        explicit = sum(1 for r in applicable if r.status == EAVStatus.EXPLICIT and r.value)
        sub_scores["required_attribute_values"] = 10.0 * explicit / len(applicable)
        notes.append(f"No required attribute list for this page type — used all {len(applicable)} rows.")
    elif eav_rows:
        notes.append("All attribute rows are not-applicable; attribute readiness excluded.")
    else:
        sub_scores["required_attribute_values"] = 1.0
        lost.append("0 attribute rows with values — knowledge-graph nodes would have no properties.")

    # 3) Canonical naming / alias handling / disambiguation (15%)
    if len(entities) == 1:
        sub_scores["canonical_naming"] = 8.0
    else:
        with_disambiguation = [e for e in entities if e.aliases or e.wikidata_id]
        share = len(with_disambiguation) / len(entities)
        sub_scores["canonical_naming"] = clamp(2.0 + 8.0 * share)
        if not with_disambiguation:
            lost.append(
                f"0 of {len(entities)} entities carry aliases or external IDs — weak disambiguation for a graph."
            )
        elif len(with_disambiguation) < len(entities):
            lost.append(
                f"{len(entities) - len(with_disambiguation)} of {len(entities)} entities lack aliases or external IDs."
            )

    # 4) Brand/project/site consistency (15%)
    canonical_facts = get_canonical_facts(state)
    norm_to_canonical: dict[str, set[str]] = {}
    for entity in entities:
        norm_to_canonical.setdefault(normalize_name(entity.canonical_name), set()).add(entity.canonical_name)
    variance = sum(1 for spellings in norm_to_canonical.values() if len(spellings) > 1)
    conflicts = detect_canonical_fact_conflicts(
        canonical_facts, eav_rows=eav_rows, claims=claims, triples=triples
    )
    brand_score = 8.5 - 3.0 * variance - 3.0 * min(3, len(conflicts))
    sub_scores["brand_consistency"] = clamp(brand_score)
    if variance:
        lost.append(
            f"{variance} canonical names are spelled inconsistently across the entity inventory."
        )
    if conflicts:
        lost.append(
            f"{len(conflicts)} content statements contradict canonical brand-pack facts."
        )
    if not canonical_facts:
        notes.append("No canonical brand pack supplied — consistency checked on surface-form variance only.")

    # 5) Entity types and relationships are coherent (10%)
    if entities:
        other_share = sum(1 for e in entities if e.kind == EntityKind.OTHER) / len(entities)
        sub_scores["entity_type_coherence"] = clamp(10.0 - 8.0 * other_share)
        if other_share > 0:
            lost.append(
                f"{sum(1 for e in entities if e.kind == EntityKind.OTHER)} of {len(entities)} entities are "
                f"untyped ('other') — incoherent typing for a graph."
            )
    else:
        notes.append("Entity type coherence excluded: no entity inventory (weights re-normalized).")

    # 6) Proof/source links support important triples (10%)
    explicit_triples = [t for t in triples if t.status == TripleStatus.EXPLICIT]
    if not explicit_triples:
        notes.append("Proof/source-link support excluded: no explicit triples to support (weights re-normalized).")
    else:
        supported = [t for t in explicit_triples if t.evidence_excerpt or t.passage_id]
        sub_scores["proof_source_links"] = 10.0 * len(supported) / len(explicit_triples)
        if len(supported) < len(explicit_triples):
            lost.append(
                f"{len(explicit_triples) - len(supported)} of {len(explicit_triples)} explicit triples carry "
                f"no evidence excerpt or passage anchor."
            )

    observations = len(triples) + len(eav_rows) + len(entities)
    rationale = (
        f"KGR assessed from {len(triples)} triples, {len(eav_rows)} attribute rows and "
        f"{len(entities)} entities ({'central: ' + central.canonical_name if central is not None else 'no central entity'})."
    )
    return _build(ScoreKey.KGR, sub_scores, KGR_WEIGHTS, lost, rationale, observations)


# --------------------------------------------------------------------------
# FCS — Fan-out Coverage Score (PRD §9.2.D / §9.4)
# --------------------------------------------------------------------------

_COVERAGE_CREDIT: dict[CoverageStatus, float] = {
    CoverageStatus.COVERED: 1.0,
    CoverageStatus.PARTIAL: 0.5,
    CoverageStatus.MISSING: 0.0,
}


def compute_fcs(state: Any) -> ScoreComponent:
    """Fan-out Coverage Score: importance-weighted coverage over in-scope rows."""
    rows = get_coverage_rows(state)
    fanout = get_fanout(state)

    if not rows:
        return ScoreComponent.unassessed(
            ScoreKey.FCS,
            _label(ScoreKey.FCS),
            "No fan-out coverage rows in the run state — zero rows is 'not assessed', not zero points (PRD §9.4).",
        )

    query_map = {q.query_id: q for q in fanout}
    observed = simulated = unmatched = excluded = 0
    numerator = 0.0
    denominator = 0.0
    lost: list[str] = []

    for row in rows:
        query = query_map.get(row.query_id)
        if row.status == CoverageStatus.EXCLUDED:
            excluded += 1
            continue
        if query is not None and query.scope == QueryScope.OUT_OF_SCOPE:
            excluded += 1
            continue
        if query is None:
            unmatched += 1
        elif query.origin == QueryOrigin.OBSERVED:
            observed += 1
        else:
            simulated += 1
        importance = float(query.importance if query is not None else 2)
        credit = _COVERAGE_CREDIT.get(row.status, 0.0)
        denominator += importance
        numerator += importance * credit
        if row.status == CoverageStatus.PARTIAL:
            lost.append(f"Query partially answered: '{row.query_text}' (importance {int(importance)}).")
        elif row.status == CoverageStatus.MISSING:
            lost.append(f"Query missing coverage: '{row.query_text}' (importance {int(importance)}).")

    if denominator <= 0:
        return ScoreComponent.unassessed(
            ScoreKey.FCS,
            _label(ScoreKey.FCS),
            f"All {len(rows)} coverage rows are excluded/out-of-scope — no in-scope denominator; "
            f"FCS not assessed (PRD §9.4).",
            observed_queries=observed,
            simulated_queries=simulated,
        )

    value = clamp(10.0 * numerator / denominator)
    in_scope = observed + simulated + unmatched
    lost.append(
        f"Provenance: {observed} observed vs {simulated} simulated in-scope queries "
        f"(+{unmatched} rows unmatched to a fan-out query) — never blended without this label (PRD §9.4)."
    )
    rationale = (
        f"FCS computed as 10 × {numerator:.1f} / {denominator:.1f} over {in_scope} in-scope rows "
        f"({excluded} excluded/out-of-scope)."
    )
    if observed == 0:
        rationale += " 0 observed queries — coverage computed from simulated queries only (hypotheses)."
    confidence = confidence_for(in_scope)
    if observed == 0 and confidence.value == "high":

        confidence = Confidence.MEDIUM

    return ScoreComponent(
        score_key=ScoreKey.FCS,
        label=_label(ScoreKey.FCS),
        value=value,
        sub_scores={"weighted_coverage": value},
        sub_weights={"weighted_coverage": 1.0},
        lost_points=lost,
        rationale=rationale,
        confidence=confidence,
        observations=in_scope,
        observed_queries=observed,
        simulated_queries=simulated,
    )


# --------------------------------------------------------------------------
# PRS — Passage Retrievability Score (PRD §9.2.E)
# --------------------------------------------------------------------------


def compute_prs(state: Any) -> ScoreComponent:
    """Passage Retrievability Score: clarity and extractability of passages."""
    document = get_document(state)
    profile = get_profile(get_page_type(state))

    if document is None or not document.passages:
        return ScoreComponent.unassessed(
            ScoreKey.PRS,
            _label(ScoreKey.PRS),
            "No parsed document or no passages in the run state — PRS cannot be assessed (PRD §9.2.E).",
        )

    passages = document.passages
    total = len(passages)
    audit_ran = any(p.issues or p.answer_first or p.named_subject or p.answer_shape for p in passages)
    claims = get_claims(state)
    coverage_rows = get_coverage_rows(state)
    fanout = get_fanout(state)
    anchored_claims = [c for c in claims if c.passage_id]
    if not audit_ran and not anchored_claims and not coverage_rows:
        return ScoreComponent.unassessed(
            ScoreKey.PRS,
            _label(ScoreKey.PRS),
            "Passage audit flags, claim anchors and coverage rows are all absent — the passage layer "
            "was not evaluated, so PRS is not assessed (PRD §9.2.E).",
            observations=total,
        )

    pindex = passage_index(document)
    section_map = passage_section_map(document)
    grouped = passages_by_section(document)
    sub_scores: dict[str, float] = {}
    lost: list[str] = []
    notes: list[str] = []

    if audit_ran:
        # 1) Answer-first openings (20%)
        answer_first = sum(1 for p in passages if p.answer_first)
        sub_scores["answer_first_opening"] = 10.0 * answer_first / total
        if answer_first < total:
            lost.append(
                f"{total - answer_first} of {total} passages are preamble-heavy (no answer-first opening)."
            )

        # 2) Named subjects / stable anchors (15%)
        named = sum(1 for p in passages if p.named_subject)
        sub_scores["named_subject_anchors"] = 10.0 * named / total
        if named < total:
            lost.append(
                f"{total - named} of {total} passages open with ambiguous pronouns or deictic references."
            )

        # 3) Standalone comprehension (20%)
        self_failures = sum(1 for p in passages if SELF_CONTAINMENT_ISSUES.intersection(p.issues))
        sub_scores["standalone_passage_comprehension"] = min(9.5, 10.0 * (1 - self_failures / total))
        if self_failures:
            lost.append(
                f"{self_failures} of {total} passages are flagged as not self-contained "
                f"(pronoun/context dependence)."
            )

        # 5) Appropriate answer shape (10%)
        shaped = sum(1 for p in passages if p.answer_shape is not None)
        shape_score = 10.0 * shaped / total
        expected_shapes = set(profile.expected_answer_shapes)
        expected_present = any(p.answer_shape in expected_shapes for p in passages) if expected_shapes else True
        if not expected_present:
            shape_score = min(shape_score, 4.0)
            lost.append(
                f"0 of {total} passages uses an expected answer shape for {profile.label} "
                f"({', '.join(sorted(s.value for s in expected_shapes))})."
            )
        elif shaped < total:
            lost.append(f"{total - shaped} of {total} passages present no recognizable answer shape.")
        sub_scores["answer_shape_fit"] = shape_score
    else:
        notes.append(
            "Passage audit flags absent — extractability sub-scores (answer-first, named subject, "
            "self-containedness, answer shape) excluded and weights re-normalized."
        )

    # 4) Claim/evidence adjacency (15%)
    adjacency_issues = sum(1 for p in passages if ADJACENCY_ISSUES.intersection(p.issues))
    claim_passages = {c.passage_id for c in anchored_claims if c.passage_id in pindex}
    if claim_passages:
        sub_scores["evidence_adjacency"] = 10.0 * len(claim_passages) / total
        if len(claim_passages) < total:
            lost.append(
                f"{total - len(claim_passages)} of {total} passages contain no anchored claim/evidence."
            )
    elif any(p.issues for p in passages):
        sub_scores["evidence_adjacency"] = min(9.5, 10.0 * (1 - adjacency_issues / total))
        if adjacency_issues:
            lost.append(
                f"{adjacency_issues} of {total} passages carry evidence-adjacency issues "
                f"(claims stated away from their support)."
            )
    else:
        notes.append(
            "No claims in the ledger and no recorded passage issues — evidence adjacency inferred "
            "from issue absence only (low confidence)."
        )
        sub_scores["evidence_adjacency"] = 8.0

    # 6) High-priority information appears early (10%)
    core_covered = [
        row for row in coverage_rows
        if (q := next((x for x in fanout if x.query_id == row.query_id), None)) is not None
        and q.importance == 3
        and row.status == CoverageStatus.COVERED
        and row.matched_passage_ids
    ]
    if core_covered:
        early = 0
        for row in core_covered:
            best = row.matched_passage_ids[0]
            section_id = section_map.get(best, pindex.get(best).section_id if best in pindex else "")
            first_two = (grouped.get(section_id) or [])[:2]
            if best in first_two:
                early += 1
        sub_scores["priority_information_early"] = 10.0 * early / len(core_covered)
        if early < len(core_covered):
            lost.append(
                f"{len(core_covered) - early} of {len(core_covered)} core answers are buried deeper than "
                f"the first two passages of their section."
            )
    else:
        notes.append(
            "Priority-information-early excluded: no covered core (importance=3) queries with matched passages."
        )

    # 7) Passage hierarchy and redundancy control (10%)
    text = document_text(state)
    repeated = detect_repeated_phrases(text, 3, 4)
    zero_passage_sections = sum(1 for s in document.sections if not s.passages)
    sections = document.sections or []
    long_sections = [
        s for s in sections
        if s.word_count > 800 or (s.word_count == 0 and len((s.raw_text or "").split()) > 800)
    ]
    long_ratio = len(long_sections) / len(sections) if sections else 0.0
    distinct_levels = len({h.level for h in document.headings})
    hierarchy = 10.0
    hierarchy -= 1.5 * min(4, len(repeated))
    hierarchy -= 2.0 if zero_passage_sections else 0.0
    hierarchy -= 4.0 * long_ratio
    hierarchy -= 2.0 if distinct_levels >= 5 else 0.0
    sub_scores["hierarchy_redundancy_control"] = clamp(hierarchy)
    if repeated:
        lost.append(f"{len(repeated)} repeated 3-gram patterns (≥4 occurrences) indicate redundancy.")
    if zero_passage_sections:
        lost.append(f"{zero_passage_sections} sections contain 0 passages — hierarchy anomalies.")
    if long_sections:
        lost.append(
            f"{len(long_sections)} of {len(sections)} sections exceed 800 words — hard to scan or retrieve."
        )

    observations = total
    rationale = (
        f"PRS assessed over {total} passages ({sum(1 for p in passages if p.answer_shape)} shaped, "
        f"{len(anchored_claims)} anchored claims). PRS measures clarity and extractability — not any "
        f"platform's hidden chunk or reranker score (PRD §9.2.E)."
    )
    return _build(ScoreKey.PRS, sub_scores, PRS_WEIGHTS, lost, rationale, observations, notes=notes)


# --------------------------------------------------------------------------
# CWS — Citation-Worthiness / Information Gain (PRD §9.2.F)
# --------------------------------------------------------------------------


def compute_cws(state: Any) -> ScoreComponent:
    """Citation-Worthiness / Information Gain score."""
    claims = get_claims(state)
    evidence_sources = get_evidence_sources(state)
    findings = get_findings(state)
    entities = get_entities(state)
    document = get_document(state)

    if not claims and not evidence_sources and not findings and document is None:
        return ScoreComponent.unassessed(
            ScoreKey.CWS,
            _label(ScoreKey.CWS),
            "No claims, evidence sources, findings or parsed document in the run state — "
            "CWS cannot be assessed (PRD §9.1).",
        )

    source_map = {s.source_id: s for s in evidence_sources}
    sub_scores: dict[str, float] = {}
    lost: list[str] = []
    notes: list[str] = []

    # 1) Original / first-party information (25%)
    gain_findings = [f for f in findings if f.category.lower() in _INFORMATION_GAIN_CATEGORIES]
    first_party_claims = [
        c for c in claims
        if any(
            source_map.get(sid) is not None
            and source_map[sid].label.value == "first_party"
            for sid in c.evidence_source_ids
        )
    ]
    candidates = len(findings) + len(claims)
    if candidates == 0:
        notes.append("Original/first-party information excluded: no findings or claims to judge (weights re-normalized).")
    else:
        hits = len(gain_findings) + len(first_party_claims)
        sub_scores["original_first_party"] = 10.0 * hits / candidates
        if hits == 0:
            lost.append(
                f"0 of {candidates} findings/claims carry first-party or original-data substance."
            )

    # 2) Verifiable evidence and sourcing (20%)
    if not claims and not evidence_sources:
        notes.append("Verifiable-evidence excluded: no claim ledger and no evidence sources (weights re-normalized).")
    elif not claims:
        with_url = sum(1 for s in evidence_sources if s.url)
        sub_scores["verifiable_evidence_sourcing"] = 10.0 * with_url / len(evidence_sources)
        notes.append(f"No claims captured — sourcing assessed from {len(evidence_sources)} evidence sources only.")
    else:
        supported = [c for c in claims if c.evidence_source_ids or c.verification_state == VerificationState.VERIFIED]
        numeric_unverified = [c for c in claims if is_numeric_claim(c) and claim_is_unverified(c)]
        credit = len(supported) - len(numeric_unverified)
        sub_scores["verifiable_evidence_sourcing"] = clamp(10.0 * credit / len(claims))
        if numeric_unverified:
            lost.append(
                f"{len(numeric_unverified)} of {len(claims)} numeric claims are unverified — "
                f"unsupported numbers are penalized explicitly (PRD §9.2.F)."
            )
        if len(supported) < len(claims):
            lost.append(
                f"{len(claims) - len(supported)} of {len(claims)} claims have no verified source link."
            )

    # 3) Information beyond common restatement (20%)
    if document is None:
        notes.append("Beyond-restatement excluded: no parsed document to measure repetition (weights re-normalized).")
    else:
        repeated = detect_repeated_phrases(document.raw_text or document.normalized_text, 3, 4)
        restatement = [f for f in findings if f.category.lower() in _RESTATEMENT_CATEGORIES]
        beyond = 10.0 - 1.5 * min(4, len(repeated)) - 2.5 * len(restatement)
        sub_scores["information_beyond_restatement"] = clamp(beyond)
        if repeated:
            lost.append(
                f"{len(repeated)} repeated 3-gram patterns (≥4 occurrences) suggest restatement of common copy."
            )
        if restatement:
            lost.append(f"{len(restatement)} findings mark thin/duplicate restatement content.")

    # 4) First-hand expertise / process detail (15%)
    people = [e for e in entities if e.kind == EntityKind.PERSON]
    processes = [e for e in entities if e.kind == EntityKind.PROCESS]
    if entities:
        expertise = min(10.0, 2.5 * len(people) + 1.0 * len(processes))
        sub_scores["first_hand_expertise"] = expertise if (people or processes) else 2.0
        if not people:
            lost.append(
                "0 PERSON entities with role/credentials — first-hand expertise cannot be established."
            )
        elif not processes:
            lost.append("0 PROCESS entities — no first-hand method detail in the entity inventory.")
    elif document is not None:
        sub_scores["first_hand_expertise"] = 3.0
        lost.append("0 entities extracted — no expertise or process signals could be attributed.")
    else:  # pragma: no cover - guarded by the not-assessed check above
        notes.append("First-hand expertise excluded: no entities and no document (weights re-normalized).")

    # 5) Claim precision and dated context (10%)
    if not claims:
        notes.append("Claim precision/dating excluded: the claim ledger is empty (weights re-normalized).")
    else:
        dated = sum(1 for c in claims if claim_has_dated_context(c, evidence_sources))
        sub_scores["claim_precision_dating"] = 10.0 * dated / len(claims)
        if dated < len(claims):
            lost.append(
                f"{len(claims) - dated} of {len(claims)} claims carry no dated context "
                f"(no source publication date or in-statement date)."
            )

    # 6) Attribution / source quality (10%)
    if not evidence_sources:
        notes.append("Attribution quality excluded: no evidence sources captured (weights re-normalized).")
    else:
        attributed = [s for s in evidence_sources if s.url and (s.publication_date or s.publisher)]
        sub_scores["attribution_quality"] = 10.0 * len(attributed) / len(evidence_sources)
        if len(attributed) < len(evidence_sources):
            lost.append(
                f"{len(evidence_sources) - len(attributed)} of {len(evidence_sources)} sources lack a URL "
                f"plus date/publisher for attribution."
            )

    observations = len(claims) + len(evidence_sources) + len(findings)
    rationale = (
        f"CWS assessed from {len(claims)} claims, {len(evidence_sources)} evidence sources and "
        f"{len(findings)} findings."
    )
    component = _build(ScoreKey.CWS, sub_scores, CWS_WEIGHTS, lost, rationale, observations, notes=notes)

    # CRITICAL: fabrication risk caps the whole component (PRD §9.2.F).
    fabrication_risk = [c for c in claims if claim_is_fabrication_risk(c)]
    if fabrication_risk and component.assessed:
        capped = min(component.value, 4.0)  # type: ignore[type-var]
        component.value = clamp(capped)
        component.lost_points.append(
            f"FABRICATION RISK: {len(fabrication_risk)} of {len(claims)} claims look fabricated or "
            f"conflicting — prose quality cannot rescue this (PRD §9.2.F/§9.5)."
        )
    return component


# --------------------------------------------------------------------------
# HRS — Human Readability & Utility (PRD §9.2.G)
# --------------------------------------------------------------------------


def compute_hrs(state: Any) -> ScoreComponent:
    """Human Readability & Utility Score, language-aware (PRD §9.2.G)."""
    document = get_document(state)
    if document is None:
        return ScoreComponent.unassessed(
            ScoreKey.HRS,
            _label(ScoreKey.HRS),
            "No parsed document in the run state — readability and utility cannot be assessed (PRD §9.1).",
        )

    page_type = get_page_type(state)
    profile = get_profile(page_type)
    language = get_language(state).lower()
    text = document.raw_text or document.normalized_text or ""
    sentences = extract_sentences(text)
    total_sentences = max(1, len(sentences))
    sub_scores: dict[str, float] = {}
    lost: list[str] = []
    notes: list[str] = []

    long_sentences = sum(1 for s in sentences if len(s.split()) > 25)
    long_ratio = long_sentences / total_sentences

    # 1) Clarity and plain-language fit (20%) — language aware.
    warnings = [w for w in get_warnings(state) if _LANGUAGE_WARNING_RE.search(w)]
    language_supported = language.split("-")[0] in {lang.split("-")[0] for lang in _FLESCH_LANGUAGES}
    readability: Optional[float] = None
    if language_supported and not warnings:
        from ega_parsers.metrics import compute_flesch_reading_ease

        readability = compute_flesch_reading_ease(text)
    if readability is not None:
        if readability >= 60.0:
            clarity = 9.0
        elif readability >= 45.0:
            clarity = 7.5
        else:
            clarity = 4.0
            lost.append(f"Text is dense (Flesch Reading Ease {readability}/100).")
        if long_ratio > 0.30:
            clarity -= 1.5
        elif long_ratio > 0.18:
            clarity -= 0.7
        if long_ratio > 0.18:
            lost.append(
                f"{long_sentences} of {total_sentences} sentences exceed 25 words (ratio {long_ratio:.2f})."
            )
        sub_scores["clarity_plain_language"] = clamp(clarity)
    else:
        if warnings:
            notes.append(
                f"Readability warning passed through ({warnings[0]}) — qualitative clarity path used."
            )
        else:
            notes.append(
                f"Language '{language}' is outside the Flesch-calibrated set — qualitative clarity path used."
            )
        if long_ratio <= 0.10:
            qualitative = 8.0
        elif long_ratio <= 0.25:
            qualitative = 6.5
        elif long_ratio <= 0.40:
            qualitative = 5.0
        else:
            qualitative = 3.0
        if long_sentences:
            lost.append(
                f"{long_sentences} of {total_sentences} sentences exceed 25 words (ratio {long_ratio:.2f})."
            )
        sub_scores["clarity_plain_language"] = qualitative

    # 2) Structure and scannability (15%)
    headings = document.headings
    sections = document.sections
    has_lists = bool(_NUMBERED_LIST_RE.search(text))
    structure = 3.0
    if len(headings) >= 4:
        structure += 3.0
    elif len(headings) >= 1:
        structure += 1.5
    else:
        lost.append("No headings — the page is a wall of text for human scanners.")
    if has_lists:
        structure += 2.0
    else:
        lost.append("No lists detected — steps/options are not scannable.")
    if len(sections) >= 2:
        structure += 1.5
    long_sections = [s for s in sections if (s.word_count or len((s.raw_text or '').split())) > 800]
    if long_sections:
        structure -= 2.0
        lost.append(f"{len(long_sections)} sections exceed 800 words — poor scannability.")
    sub_scores["structure_scannability"] = clamp(structure)

    # 3) Practical completeness for the audience (20%)
    eav_rows = get_eav_rows(state)
    required = REQUIRED_ATTRIBUTES.get(page_type, [])
    satisfied = satisfied_attribute_keys(eav_rows)
    if required:
        matched = [spec for spec in required if spec.key in satisfied]
        sub_scores["practical_completeness"] = 10.0 * len(matched) / len(required)
        if len(matched) < len(required):
            lost.append(
                f"{len(required) - len(matched)} of {len(required)} required attributes for "
                f"{profile.label} are missing — incomplete for the audience."
            )
    elif eav_rows:
        applicable = [r for r in eav_rows if r.status != EAVStatus.NOT_APPLICABLE]
        if applicable:
            explicit = sum(1 for r in applicable if r.status == EAVStatus.EXPLICIT and r.value)
            sub_scores["practical_completeness"] = 10.0 * explicit / len(applicable)
            notes.append(f"No required attribute list for this type — used all {len(applicable)} rows.")
        else:
            notes.append("Practical completeness excluded: all attribute rows are not-applicable.")
    else:
        sub_scores["practical_completeness"] = 2.0
        lost.append("0 attribute rows — practical completeness cannot be established.")

    # 4) Relevance / no filler / redundancy (15%)
    passages = document.passages
    seen: dict[str, str] = {}
    duplicates = 0
    for passage in passages:
        normalized = normalize_name(passage.text)
        if not normalized:
            continue
        if normalized in seen:
            duplicates += 1
        else:
            seen[normalized] = passage.passage_id
    repeated = detect_repeated_phrases(text, 3, 4)
    relevance = 10.0
    if passages:
        relevance -= 6.0 * (duplicates / len(passages))
    relevance -= 1.5 * min(4, len(repeated))
    sub_scores["relevance_no_filler"] = clamp(relevance)
    if duplicates:
        lost.append(f"{duplicates} of {len(passages)} passages duplicate another passage verbatim.")
    if repeated:
        lost.append(f"{len(repeated)} repeated 3-gram patterns (≥4 occurrences) read as filler.")

    # 5) Tone and terminology (10%) — banned terms as tone problems.
    banned_terms = get_banned_terms(state)
    if not banned_terms:
        notes.append(
            "Tone/terminology excluded: no banned-term list configured in the brand pack (weights re-normalized)."
        )
    else:
        violations = detect_banned_terms(text, banned_terms)
        sub_scores["tone_terminology"] = clamp(10.0 - 2.5 * min(4, len(violations)))
        if violations:
            terms = ", ".join(sorted({v.evidence for v in violations if v.evidence}))
            lost.append(f"{len(violations)} banned-term violations (tone/terminology problems): {terms}.")

    # 6) Helpful examples / steps / decision support (10%)
    example_markers = len(_EXAMPLE_MARKER_RE.findall(text))
    numbered_lists = len(_NUMBERED_LIST_RE.findall(text))
    process_entities = sum(1 for e in get_entities(state) if e.kind == EntityKind.PROCESS)
    examples = min(10.0, 2.0 * example_markers + 1.5 * min(2, numbered_lists) + 2.5 * process_entities)
    sub_scores["examples_decision_support"] = examples
    if examples <= 2.0:
        lost.append("0 examples, steps or decision-support markers found on the page.")

    # 7) Conversion / next-step clarity (10%) — informational pages shift the weight.
    informational_preset = profile.score_preset == "informational"
    if informational_preset:
        notes.append(
            "Conversion/next-step clarity not applicable to a purely informational page — "
            "its weight is redistributed (PRD §9.2.G)."
        )
    else:
        cta_entities = sum(1 for e in get_entities(state) if e.kind == EntityKind.CTA)
        cta_verbs = _CTA_VERB_RE.findall(text)
        if cta_entities or cta_verbs:
            sub_scores["conversion_next_step"] = min(10.0, 6.0 + 2.0 * min(2, cta_entities) + 1.0 * min(2, len(cta_verbs)))
        else:
            sub_scores["conversion_next_step"] = 2.0
            lost.append("0 calls to action or next-step verbs on a page expected to convert.")

    observations = len(document.passages) + len(document.sections) + len(document.headings)
    rationale = (
        f"HRS assessed over {len(document.passages)} passages, {len(document.sections)} sections and "
        f"{len(document.headings)} headings (language '{language}')."
    )
    return _build(ScoreKey.HRS, sub_scores, HRS_WEIGHTS, lost, rationale, observations, notes=notes)


__all__ = [
    "CWS_WEIGHTS",
    "EOS_LOCAL_WEIGHTS",
    "EOS_WEIGHTS",
    "ERS_WEIGHTS",
    "HRS_WEIGHTS",
    "KGR_WEIGHTS",
    "PRS_WEIGHTS",
    "compute_cws",
    "compute_eos",
    "compute_ers",
    "compute_fcs",
    "compute_hrs",
    "compute_kgr",
    "compute_prs",
    "label_for",
]
