"""Optional component scores (PRD §9.3).

PRD §9.3 lists optional profiles that sit *beside* the composite rather than
inside it: Intent Alignment, Local Fit, Paid Landing Page Fit, Conversion
Readiness, Trust / E-E-A-T Coverage and Internal-Link Readiness. Each one here
follows the same epistemology as the core components:

* pure and deterministic — a function of structured state only;
* an optional component that does not apply to the page is returned as
  ``not_applicable`` (never ``0``), and it never carries a composite weight;
* an optional component whose inputs are simply absent is ``not_assessed``.

The composite AVR (``ega_scoring.composite``) always uses only the seven core
components of PRD §9.2, so nothing in this module can move the composite.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence

from ega_schemas.enums import (
    CoverageStatus,
    EAVStatus,
    EntityKind,
    EvidenceLabel,
    IntentClass,
    PageType,
    QueryScope,
    ScoreKey,
    TripleType,
)

from auditor.rules.attributes import REQUIRED_ATTRIBUTES, satisfied_attribute_keys
from auditor.rules.page_profiles import get_profile
from ega_scoring.components import INTENT_ENTITY_KINDS, label_for
from ega_scoring.models import ScoreComponent, combine_sub_scores
from ega_scoring.rubric import clamp, confidence_for
from ega_scoring.state import (
    claim_has_dated_context,
    document_text,
    get_claims,
    get_coverage_rows,
    get_document,
    get_eav_rows,
    get_entities,
    get_evidence_sources,
    get_fanout,
    get_internal_link_targets,
    get_location_target,
    get_page_type,
    get_primary_intent,
    get_target_action,
    get_triples,
    normalize_name,
)

# --------------------------------------------------------------------------
# Optional sub-score weight tables (PRD §9.3 — internal editorial heuristics)
# --------------------------------------------------------------------------

INTENT_WEIGHTS: dict[str, float] = {
    "declared_intent_fit": 0.40,
    "intent_entity_evidence": 0.35,
    "fanout_intent_coverage": 0.25,
}

LOCAL_FIT_WEIGHTS: dict[str, float] = {
    "location_dominance": 0.30,
    "location_target_presence": 0.25,
    "local_attributes": 0.25,
    "local_proof": 0.20,
}

PAID_FIT_WEIGHTS: dict[str, float] = {
    "offer_clarity": 0.25,
    "single_primary_cta": 0.25,
    "trust_proof_at_action": 0.25,
    "keyword_message_match": 0.25,
}

CONVERSION_WEIGHTS: dict[str, float] = {
    "action_path_present": 0.35,
    "action_clarity": 0.25,
    "offer_specificity": 0.20,
    "friction_control": 0.20,
}

TRUST_WEIGHTS: dict[str, float] = {
    "trust_entities": 0.30,
    "authoritative_sources": 0.30,
    "attribution_authorship": 0.20,
    "dated_evidence": 0.20,
}

LINKS_WEIGHTS: dict[str, float] = {
    "internal_links_present": 0.35,
    "hub_targets_covered": 0.30,
    "descriptive_anchors": 0.20,
    "hierarchy_coverage": 0.15,
}

#: PRD §9.3 requires disclosure that optional scores are not part of the composite.
OPTIONAL_DISCLAIMER = (
    "Optional profile score — reported beside the composite AVR and never folded "
    "into it (PRD §9.3). Internal editorial heuristic, not a platform metric."
)

_TRUST_KINDS: frozenset[EntityKind] = frozenset(
    {EntityKind.PROOF, EntityKind.STANDARD, EntityKind.REGULATION, EntityKind.PERSON}
)

_AUTHORITATIVE_LABELS: frozenset[EvidenceLabel] = frozenset(
    {EvidenceLabel.OFFICIAL, EvidenceLabel.MEASURED_STUDY, EvidenceLabel.FIRST_PARTY, EvidenceLabel.PRACTITIONER}
)

_LOCAL_ATTRIBUTE_KEYS: frozenset[str] = frozenset(
    {"location", "service_area", "hours", "local_landmark_context", "local_proof", "coverage_area"}
)

_CTA_VERB_RE = re.compile(
    r"\b(get started|start (?:a )?(?:free )?trial|sign up|book (?:a )?(?:call|demo|consultation|appointment)"
    r"|request (?:a )?(?:demo|quote|pricing)|schedule|contact us|buy now|add to cart|download"
    r"|talk to (?:us|sales)|chat with|see pricing|subscribe)\b",
    re.IGNORECASE,
)

_OFFER_RE = re.compile(
    r"(\d+\s*%\s*off|free trial|free plan|free demo|money[- ]back|from\s*[€$£]\s*\d+|discount"
    r"|no credit card|limited time|pricing(?: starts)?|starting at)",
    re.IGNORECASE,
)

_WEAK_ANCHORS: frozenset[str] = frozenset(
    {"click here", "here", "read more", "learn more", "this", "link", "more", "details"}
)

_NEXT_STEP_RE = re.compile(
    r"\b(next step|step \d|follow these steps|how to|get started|try it|download now|book now)\b",
    re.IGNORECASE,
)

_FORM_RE = re.compile(r"<\s*form\b|\b(submit|required field|enter your email)\b", re.IGNORECASE)


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def _build(
    key: ScoreKey,
    sub_scores: dict[str, float],
    sub_weights: dict[str, float],
    lost: Sequence[str],
    rationale: str,
    observations: int,
    *,
    notes: Optional[Sequence[str]] = None,
) -> ScoreComponent:
    """Assemble an optional component, re-normalizing over included sub-scores."""
    value, re_normalized, used = combine_sub_scores(sub_scores, sub_weights)
    notes = list(notes or [])
    excluded = [name for name in sub_weights if name not in sub_scores]
    if value is None:  # pragma: no cover - callers guard against this
        return ScoreComponent.unassessed(
            key,
            label_for(key),
            f"No sub-score of {key.value} had supporting evidence — not assessed (PRD §9.3).",
        )
    if excluded:
        notes.append(
            "Sub-scores excluded for lack of evidence (weights re-normalized): "
            f"{', '.join(sorted(excluded))}."
        )
    notes.append(OPTIONAL_DISCLAIMER)
    return ScoreComponent(
        score_key=key,
        label=label_for(key),
        value=clamp(value),
        sub_scores=dict(sub_scores),
        sub_weights=used,
        renormalized=re_normalized or bool(excluded),
        lost_points=list(lost),
        rationale=rationale + " " + " ".join(notes),
        confidence=confidence_for(observations),
        observations=observations,
        notes=notes,
    )


def _not_applicable(key: ScoreKey, reason: str) -> ScoreComponent:
    return ScoreComponent.unassessed(
        key, label_for(key), reason, not_applicable=True
    )


# --------------------------------------------------------------------------
# INTENT — Intent Alignment (PRD §9.3)
# --------------------------------------------------------------------------


def compute_intent(state: Any) -> ScoreComponent:
    """Intent Alignment: declared/derived intent versus the page-type profile."""
    intent = get_primary_intent(state)
    profile = get_profile(get_page_type(state))
    entities = get_entities(state)
    fanout = get_fanout(state)
    coverage_rows = get_coverage_rows(state)

    if intent is None and not fanout:
        return ScoreComponent.unassessed(
            ScoreKey.INTENT,
            label_for(ScoreKey.INTENT),
            "No declared primary intent and no fan-out queries — intent alignment cannot be "
            "assessed (PRD §9.3).",
        )

    sub_scores: dict[str, float] = {}
    lost: list[str] = []
    notes: list[str] = []

    # 1) Does the declared intent match what this page type is designed for?
    if intent is None:
        sub_scores["declared_intent_fit"] = 6.0
        notes.append(
            "No declared primary intent — neutral score used; page-type intent profile is "
            "the only signal."
        )
    elif intent in profile.likely_intents:
        sub_scores["declared_intent_fit"] = 10.0
    else:
        sub_scores["declared_intent_fit"] = 3.0
        lost.append(
            f"Declared intent '{intent.value}' is not among the likely intents for a "
            f"{profile.label} page ({', '.join(i.value for i in profile.likely_intents)})."
        )

    # 2) Is there entity evidence for the intent?
    effective_intent = intent or (profile.likely_intents[0] if profile.likely_intents else None)
    if effective_intent is None:  # pragma: no cover - every profile declares intents
        notes.append("No intent to check entity evidence against — sub-score excluded.")
    elif not entities:
        notes.append(
            "Intent entity evidence excluded: the entity inventory is empty (weights re-normalized)."
        )
    else:
        kinds = INTENT_ENTITY_KINDS.get(effective_intent, frozenset())
        hits = [e for e in entities if e.kind in kinds]
        if hits:
            sub_scores["intent_entity_evidence"] = min(10.0, 5.0 + 1.5 * len(hits))
        else:
            sub_scores["intent_entity_evidence"] = 2.0
            expected = ", ".join(sorted(k.value for k in kinds)) or "none"
            lost.append(
                f"No entity of kind {expected} supports the '{effective_intent.value}' intent."
            )

    # 3) Fan-out intents actually covered by the page.
    in_scope = [q for q in fanout if q.scope != QueryScope.OUT_OF_SCOPE]
    row_by_id = {row.query_id: row for row in coverage_rows}
    if not in_scope:
        notes.append(
            "Fan-out intent coverage excluded: no in-scope fan-out queries "
            "(weights re-normalized)."
        )
    else:
        covered = 0
        for query in in_scope:
            row = row_by_id.get(query.query_id)
            kinds = INTENT_ENTITY_KINDS.get(query.intent, frozenset())
            has_entity = any(e.kind in kinds for e in entities)
            if row is not None and row.status in (CoverageStatus.COVERED, CoverageStatus.PARTIAL):
                covered += 1
            elif row is None and has_entity:
                covered += 1
        sub_scores["fanout_intent_coverage"] = 10.0 * covered / len(in_scope)
        if covered < len(in_scope):
            lost.append(
                f"{len(in_scope) - covered} of {len(in_scope)} in-scope fan-out queries have "
                f"neither coverage nor supporting entities."
            )

    observations = len(entities) + len(in_scope)
    return _build(
        ScoreKey.INTENT,
        sub_scores,
        INTENT_WEIGHTS,
        lost,
        f"Intent Alignment assessed against {len(entities)} entities and {len(in_scope)} "
        f"in-scope fan-out queries.",
        observations,
        notes=notes,
    )


# --------------------------------------------------------------------------
# LOCAL_FIT — Local Fit (PRD §9.3, FR-12)
# --------------------------------------------------------------------------


def compute_local_fit(state: Any) -> ScoreComponent:
    """Local Fit: geographic relevance for local pages or location-targeted audits."""
    profile = get_profile(get_page_type(state))
    location_target = get_location_target(state)
    entities = get_entities(state)
    eav_rows = get_eav_rows(state)
    triples = list(get_triples(state) or [])
    intent = get_primary_intent(state)
    locations = [e for e in entities if e.kind == EntityKind.LOCATION]

    applicable = (
        profile.local_relevant
        or bool(location_target)
        or bool(locations)
        or intent == IntentClass.LOCAL
    )
    if not applicable:
        return _not_applicable(
            ScoreKey.LOCAL_FIT,
            "Local Fit does not apply: the page is not location-relevant, no location target "
            "is configured, and no LOCATION entities or local intent are present "
            "(PRD §9.3 — optional scores are N/A, never zero).",
        )

    sub_scores: dict[str, float] = {}
    lost: list[str] = []
    notes: list[str] = []

    # 1) One dominant geographic entity.
    if not locations:
        sub_scores["location_dominance"] = 1.0
        lost.append("0 LOCATION entities — the local relevance has no geographic anchor.")
    else:
        total_salience = sum(float(e.salience) for e in locations) or 1.0
        dominant = max(float(e.salience) for e in locations) / total_salience
        sub_scores["location_dominance"] = clamp(4.0 + 6.0 * min(1.0, dominant))
        if dominant < 0.6:
            lost.append(
                f"No dominant location — the top LOCATION entity holds only {dominant:.0%} of "
                f"local salience."
            )

    # 2) The configured target location appears in the content.
    text_norm = normalize_name(document_text(state))
    if not location_target:
        notes.append("No location target configured — target-presence sub-score excluded.")
    elif not text_norm:
        notes.append("No text available — target-presence sub-score excluded.")
    else:
        target_norm = normalize_name(location_target)
        present = bool(target_norm) and (
            target_norm in text_norm
            or any(normalize_name(e.canonical_name) == target_norm for e in locations)
        )
        sub_scores["location_target_presence"] = 10.0 if present else 1.0
        if not present:
            lost.append(f"Location target '{location_target}' never appears in the page content.")

    # 3) Local attributes carry explicit values.
    applicable_rows = [
        row for row in eav_rows
        if normalize_name(row.attribute).replace(" ", "_") in _LOCAL_ATTRIBUTE_KEYS
    ]
    if not eav_rows:
        notes.append("No attribute rows — local-attribute sub-score excluded (weights re-normalized).")
    elif not applicable_rows:
        sub_scores["local_attributes"] = 2.0
        lost.append(
            "0 explicit local attributes (location, service area, hours) in the EAV inventory."
        )
    else:
        explicit = sum(
            1 for row in applicable_rows if row.status == EAVStatus.EXPLICIT and row.value
        )
        sub_scores["local_attributes"] = 10.0 * explicit / len(applicable_rows)
        if explicit < len(applicable_rows):
            lost.append(
                f"{len(applicable_rows) - explicit} of {len(applicable_rows)} local attribute rows "
                f"lack explicit values."
            )

    # 4) Local proof: geography triples or local-proof signal in the text.
    geo_triples = [t for t in triples if t.triple_type == TripleType.GEOGRAPHY]
    local_proof_terms = re.search(
        r"\b(local reviews?|testimonials?|projects? in|serving|registered in|licensed in)\b",
        text_norm,
    )
    if geo_triples or local_proof_terms:
        sub_scores["local_proof"] = 9.0 if geo_triples else 6.5
        if not geo_triples:
            lost.append("Local proof is mentioned in prose but not structured as geography triples.")
    else:
        sub_scores["local_proof"] = 1.0
        lost.append("No local proof (geography triples, local reviews, service-area signals).")

    observations = len(locations) + len(applicable_rows)
    return _build(
        ScoreKey.LOCAL_FIT,
        sub_scores,
        LOCAL_FIT_WEIGHTS,
        lost,
        f"Local Fit assessed over {len(locations)} LOCATION entities and "
        f"{len(applicable_rows)} local attribute rows.",
        observations,
        notes=notes,
    )


# --------------------------------------------------------------------------
# PAID_FIT — Paid Landing Page Fit (PRD §9.3, FR-13)
# --------------------------------------------------------------------------


def compute_paid_fit(state: Any) -> ScoreComponent:
    """Paid Landing Page Fit for ``paid_landing`` pages (PRD §9.3, FR-13)."""
    page_type = get_page_type(state)
    if page_type != PageType.PAID_LANDING:
        return _not_applicable(
            ScoreKey.PAID_FIT,
            f"Paid Landing Page Fit does not apply to a '{page_type.value}' page — it is only "
            f"assessed for 'paid_landing' pages (PRD §9.3).",
        )

    text = document_text(state)
    if not text:
        return ScoreComponent.unassessed(
            ScoreKey.PAID_FIT,
            label_for(ScoreKey.PAID_FIT),
            "No content text in the run state — paid landing page fit cannot be assessed (PRD §9.3).",
        )

    eav_rows = get_eav_rows(state)
    satisfied = satisfied_attribute_keys(eav_rows)
    required = {spec.key for spec in REQUIRED_ATTRIBUTES.get(PageType.PAID_LANDING, [])}
    entities = get_entities(state)
    sub_scores: dict[str, float] = {}
    lost: list[str] = []

    # 1) Offer clarity.
    offers = _OFFER_RE.findall(text)
    if required & {"offer"} and "offer" in satisfied:
        sub_scores["offer_clarity"] = 9.0
    elif offers:
        sub_scores["offer_clarity"] = 6.0
        lost.append("An offer is present in prose but not captured as an explicit 'offer' attribute.")
    else:
        sub_scores["offer_clarity"] = 1.5
        lost.append("No concrete offer (free trial, discount, price, guarantee) found on the page.")

    # 2) A single primary call to action.
    cta_entities = [e for e in entities if e.kind == EntityKind.CTA]
    cta_matches = _CTA_VERB_RE.findall(text)
    distinct_ctas = len({m.lower() for m in cta_matches})
    if distinct_ctas <= 1 and (cta_entities or cta_matches):
        sub_scores["single_primary_cta"] = 9.5
    elif distinct_ctas == 2:
        sub_scores["single_primary_cta"] = 6.0
        lost.append("2 competing call-to-action phrasings split the single advertised action.")
    elif distinct_ctas > 2:
        sub_scores["single_primary_cta"] = 3.0
        lost.append(f"{distinct_ctas} competing call-to-action phrasings — the ad promises one action.")
    else:
        sub_scores["single_primary_cta"] = 1.5
        lost.append("0 call-to-action phrasings found on a paid landing page.")

    # 3) Trust proof at the point of action.
    if "trust_proof" in satisfied:
        sub_scores["trust_proof_at_action"] = 9.5
    elif _TRUST_KINDS & {e.kind for e in entities}:
        sub_scores["trust_proof_at_action"] = 6.0
        lost.append(
            "Trust entities exist but are not captured as an explicit 'trust_proof' attribute."
        )
    else:
        sub_scores["trust_proof_at_action"] = 1.5
        lost.append("No trust proof (guarantee, reviews, credentials) near the conversion action.")

    # 4) Keyword/message match between ad and page.
    if "keyword_message_match" in satisfied:
        sub_scores["keyword_message_match"] = 9.0
    elif offers or cta_matches:
        sub_scores["keyword_message_match"] = 6.0
        lost.append(
            "Message continuity from the ad group is not declared as a 'keyword_message_match' attribute."
        )
    else:
        sub_scores["keyword_message_match"] = 2.0
        lost.append("No message continuity signal linking the ad group to the page copy.")

    observations = len(eav_rows) + len(entities)
    return _build(
        ScoreKey.PAID_FIT,
        sub_scores,
        PAID_FIT_WEIGHTS,
        lost,
        f"Paid Landing Page Fit assessed from {len(eav_rows)} attribute rows and "
        f"{len(entities)} entities (FR-13).",
        observations,
    )


# --------------------------------------------------------------------------
# CONVERSION — Conversion Readiness (PRD §9.3, FR-14)
# --------------------------------------------------------------------------


def compute_conversion(state: Any) -> ScoreComponent:
    """Conversion Readiness for pages that carry a conversion expectation (PRD §9.3)."""
    profile = get_profile(get_page_type(state))
    if profile.score_preset == "informational":
        return _not_applicable(
            ScoreKey.CONVERSION,
            f"Conversion Readiness does not apply to a {profile.label} page — informational "
            f"profiles carry no conversion expectation (PRD §9.3).",
        )

    text = document_text(state)
    entities = get_entities(state)
    if not text and not entities:
        return ScoreComponent.unassessed(
            ScoreKey.CONVERSION,
            label_for(ScoreKey.CONVERSION),
            "No content text and no entities in the run state — conversion readiness cannot be "
            "assessed (PRD §9.3).",
        )

    sub_scores: dict[str, float] = {}
    lost: list[str] = []
    notes: list[str] = []

    # 1) A concrete action path exists.
    cta_entities = [e for e in entities if e.kind == EntityKind.CTA]
    cta_matches = _CTA_VERB_RE.findall(text)
    if cta_entities or cta_matches:
        sub_scores["action_path_present"] = min(10.0, 6.0 + 2.0 * min(2, len(cta_entities)) + 1.5 * min(2, len(cta_matches)))
    else:
        sub_scores["action_path_present"] = 1.0
        lost.append("0 call-to-action entities or verbs — there is no action path.")

    # 2) The declared target action is reflected in the copy.
    target_action = get_target_action(state)
    if not target_action:
        notes.append("No target action declared — action-clarity sub-score excluded.")
    else:
        words = [w for w in normalize_name(target_action).split() if len(w) > 3]
        text_norm = normalize_name(text)
        matched = sum(1 for w in words if w in text_norm)
        if words:
            sub_scores["action_clarity"] = clamp(10.0 * matched / len(words))
            if matched < len(words):
                lost.append(
                    f"Declared target action '{target_action}' is only partly reflected in the copy "
                    f"({matched}/{len(words)} keywords)."
                )

    # 3) The offer is specific.
    if _OFFER_RE.search(text):
        sub_scores["offer_specificity"] = 8.5
    elif cta_matches:
        sub_scores["offer_specificity"] = 5.0
        lost.append("A call to action exists but no specific offer (price, trial, guarantee).")
    else:
        sub_scores["offer_specificity"] = 1.5
        lost.append("No specific offer or call to action to convert on.")

    # 4) Friction control: next-step guidance without excessive form friction.
    next_steps = bool(_NEXT_STEP_RE.search(text))
    heavy_form = bool(_FORM_RE.search(text))
    friction = 5.0
    if next_steps:
        friction += 3.0
    else:
        lost.append("No step-by-step next-step guidance near the action.")
    if heavy_form and not next_steps:
        friction -= 2.0
        lost.append("Form friction detected without guidance explaining what happens next.")
    sub_scores["friction_control"] = clamp(friction)

    observations = len(entities) + len(cta_matches)
    return _build(
        ScoreKey.CONVERSION,
        sub_scores,
        CONVERSION_WEIGHTS,
        lost,
        f"Conversion Readiness assessed from {len(entities)} entities and {len(cta_matches)} "
        f"call-to-action phrasings.",
        observations,
        notes=notes,
    )


# --------------------------------------------------------------------------
# TRUST — Trust / E-E-A-T Coverage (PRD §9.3)
# --------------------------------------------------------------------------


def compute_trust(state: Any) -> ScoreComponent:
    """Trust / E-E-A-T Coverage: named proof, authoritative sources, dating."""
    entities = get_entities(state)
    evidence_sources = get_evidence_sources(state)
    claims = get_claims(state)
    eav_rows = get_eav_rows(state)
    document = get_document(state)

    if not entities and not evidence_sources and not claims and document is None:
        return ScoreComponent.unassessed(
            ScoreKey.TRUST,
            label_for(ScoreKey.TRUST),
            "No entities, sources, claims or parsed document — trust coverage cannot be "
            "assessed (PRD §9.3).",
        )

    sub_scores: dict[str, float] = {}
    lost: list[str] = []
    notes: list[str] = []

    # 1) Trust/authority entities.
    if not entities:
        notes.append("Trust entities excluded: no entity inventory (weights re-normalized).")
    else:
        trust_entities = [e for e in entities if e.kind in _TRUST_KINDS]
        sub_scores["trust_entities"] = min(10.0, 3.0 + 2.5 * len(trust_entities))
        if not trust_entities:
            lost.append(
                "0 PROOF/STANDARD/REGULATION/PERSON entities — no named authority is established."
            )

    # 2) Authoritative sources with a URL.
    if not evidence_sources:
        notes.append("Authoritative sources excluded: no evidence sources captured (weights re-normalized).")
    else:
        authoritative = [
            s for s in evidence_sources if s.label in _AUTHORITATIVE_LABELS and s.url
        ]
        sub_scores["authoritative_sources"] = 10.0 * len(authoritative) / len(evidence_sources)
        if len(authoritative) < len(evidence_sources):
            lost.append(
                f"{len(evidence_sources) - len(authoritative)} of {len(evidence_sources)} sources "
                f"are unlabeled or have no URL."
            )

    # 3) Attribution / authorship.
    attribution_keys = {"author", "leadership", "team", "credentials", "reviewed_by"}
    satisfied = satisfied_attribute_keys(eav_rows)
    attributed = [e for e in entities if e.kind == EntityKind.PERSON and e.occurrences]
    if satisfied & attribution_keys or attributed:
        sub_scores["attribution_authorship"] = 9.0 if (satisfied & attribution_keys) else 6.5
    else:
        sub_scores["attribution_authorship"] = 2.0
        lost.append("No named author/credentials attribute and no attributable PERSON entity.")

    # 4) Dated evidence.
    if not claims and not evidence_sources:
        notes.append("Dated evidence excluded: no claims and no sources (weights re-normalized).")
    else:
        dated_claims = sum(1 for c in claims if claim_has_dated_context(c, evidence_sources))
        dated_sources = sum(1 for s in evidence_sources if s.publication_date)
        denominator = len(claims) + len(evidence_sources)
        numerator = dated_claims + dated_sources
        sub_scores["dated_evidence"] = 10.0 * numerator / denominator
        if numerator < denominator:
            lost.append(
                f"{denominator - numerator} of {denominator} claims/sources carry no publication "
                f"date or in-statement date."
            )

    observations = len(entities) + len(evidence_sources) + len(claims)
    return _build(
        ScoreKey.TRUST,
        sub_scores,
        TRUST_WEIGHTS,
        lost,
        f"Trust / E-E-A-T assessed from {len(entities)} entities, {len(evidence_sources)} sources "
        f"and {len(claims)} claims.",
        observations,
        notes=notes,
    )


# --------------------------------------------------------------------------
# LINKS — Internal-Link Readiness (PRD §9.3, FR-15)
# --------------------------------------------------------------------------


def compute_internal_links(state: Any) -> ScoreComponent:
    """Internal-Link Readiness: hub targets, anchors and hierarchy coverage (FR-15)."""
    document = get_document(state)
    targets = get_internal_link_targets(state)
    links: list[Any] = list(getattr(document, "links", []) or []) if document is not None else []
    internal = [link for link in links if getattr(link, "is_internal", False)]

    if document is None and not targets:
        return ScoreComponent.unassessed(
            ScoreKey.LINKS,
            label_for(ScoreKey.LINKS),
            "No parsed document and no configured internal-link targets — internal-link readiness "
            "cannot be assessed (PRD §9.3).",
        )

    sub_scores: dict[str, float] = {}
    lost: list[str] = []

    # 1) Internal links exist at all.
    if links:
        sub_scores["internal_links_present"] = min(
            10.0, 3.0 + 7.0 * (len(internal) / len(links))
        )
        if not internal:
            lost.append("0 internal links among the links detected on the page.")
    else:
        sub_scores["internal_links_present"] = 1.0
        lost.append("No links detected on the page — no internal navigation surface.")

    # 2) Configured hub targets are actually linked.
    if not targets:
        sub_scores["hub_targets_covered"] = 3.0
        lost.append(
            "No internal-link target list configured — hub coverage assumed weak "
            "(add a context pack to score this precisely)."
        )
    else:
        normalized_links = " ".join(
            normalize_name(f"{getattr(link, 'url', '')} {getattr(link, 'anchor_text', '')}") for link in links
        )
        hits = 0
        for target in targets:
            label = normalize_name(_target_value(target))
            if label and label in normalized_links:
                hits += 1
        sub_scores["hub_targets_covered"] = 10.0 * hits / len(targets)
        if hits < len(targets):
            lost.append(
                f"{len(targets) - hits} of {len(targets)} configured hub/context-pack link targets "
                f"are not linked from the page."
            )

    # 3) Descriptive anchor text.
    if not internal:
        sub_scores["descriptive_anchors"] = 1.0
        lost.append("No internal links to evaluate anchor text on.")
    else:
        descriptive = sum(
            1 for link in internal
            if _is_descriptive_anchor(getattr(link, "anchor_text", ""))
        )
        sub_scores["descriptive_anchors"] = 10.0 * descriptive / len(internal)
        if descriptive < len(internal):
            lost.append(
                f"{len(internal) - descriptive} of {len(internal)} internal links use weak or "
                f"generic anchor text."
            )

    # 4) Hierarchy coverage: internal links point to more than one section/depth.
    distinct_urls = {getattr(link, "url", "") for link in internal if getattr(link, "url", "")}
    if not internal:
        sub_scores["hierarchy_coverage"] = 1.0
    elif len(distinct_urls) >= 3:
        sub_scores["hierarchy_coverage"] = 10.0
    elif len(distinct_urls) == 2:
        sub_scores["hierarchy_coverage"] = 6.5
        lost.append("Only 2 distinct internal targets — thin hub-and-spoke architecture.")
    else:
        sub_scores["hierarchy_coverage"] = 3.5
        lost.append("A single distinct internal target — the page is a dead end for crawlers.")

    observations = len(links) + len(targets)
    return _build(
        ScoreKey.LINKS,
        sub_scores,
        LINKS_WEIGHTS,
        lost,
        f"Internal-link readiness assessed from {len(links)} links and {len(targets)} configured "
        f"targets (FR-15).",
        observations,
    )


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def _target_value(target: Any) -> str:
    """Best-effort string for a configured internal-link target."""
    if isinstance(target, str):
        return target
    if isinstance(target, Mapping):
        for key in ("url", "target_url", "anchor", "anchor_phrase", "label", "entity"):
            value = target.get(key)
            if value:
                return str(value)
        return ""
    for attr in ("url", "target_url", "anchor", "anchor_phrase", "label", "entity"):
        value = getattr(target, attr, None)
        if value:
            return str(value)
    return ""


def _is_descriptive_anchor(anchor: str) -> bool:
    """True when anchor text is descriptive rather than generic/empty."""
    normalized = normalize_name(anchor)
    if not normalized or normalized in _WEAK_ANCHORS:
        return False
    return len(normalized.split()) >= 2


__all__ = [
    "CONVERSION_WEIGHTS",
    "INTENT_WEIGHTS",
    "LINKS_WEIGHTS",
    "LOCAL_FIT_WEIGHTS",
    "OPTIONAL_DISCLAIMER",
    "PAID_FIT_WEIGHTS",
    "TRUST_WEIGHTS",
    "compute_conversion",
    "compute_intent",
    "compute_internal_links",
    "compute_local_fit",
    "compute_paid_fit",
    "compute_trust",
]
