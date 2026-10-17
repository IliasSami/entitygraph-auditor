"""Required-attribute registry per page type (PRD §5, FR-05).

Each page type declares the attribute/value slots an auditor must find in the
EAV inventory for the page to be considered practically complete. Attribute
``key`` strings are the canonical names used in ``EAVRow.attribute`` so that
deterministic scoring can match rows against the required set.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from ega_schemas.entities import EAVRow
from ega_schemas.enums import EAVStatus, IntentClass, PageType


@dataclass(frozen=True)
class AttributeSpec:
    """Static description of one required attribute slot (PRD §5)."""

    key: str
    label: str
    required_for: PageType
    description: str


def _spec(key: str, label: str, page_type: PageType, description: str) -> AttributeSpec:
    return AttributeSpec(key=key, label=label, required_for=page_type, description=description)


def _build_required_attributes() -> dict[PageType, list[AttributeSpec]]:
    """Build the canonical REQUIRED_ATTRIBUTES table (PRD §5 examples)."""
    table: dict[PageType, list[AttributeSpec]] = {}

    table[PageType.HOMEPAGE] = [
        _spec("primary_category", "Primary category", PageType.HOMEPAGE, "The one category/industry the brand belongs to."),
        _spec("value_proposition", "Value proposition", PageType.HOMEPAGE, "What the organization delivers and for whom."),
        _spec("key_services", "Key services", PageType.HOMEPAGE, "Coherent architecture of the main offerings, each linking to a detail page."),
        _spec("contact_path", "Contact path", PageType.HOMEPAGE, "A clear way to reach or engage the organization."),
    ]

    table[PageType.ABOUT] = [
        _spec("mission", "Mission / story", PageType.ABOUT, "Why the organization exists, in plain terms."),
        _spec("founding", "Founding facts", PageType.ABOUT, "Founding year, founders, or origin story."),
        _spec("leadership", "Leadership / team", PageType.ABOUT, "Named people with roles and credentials."),
        _spec("differentiators", "Differentiators", PageType.ABOUT, "Verifiable points of difference."),
    ]

    table[PageType.SERVICE] = [
        _spec("price", "Price / pricing basis", PageType.SERVICE, "Explicit price, pricing model, or range."),
        _spec("timeframe", "Timeframe", PageType.SERVICE, "How long delivery takes."),
        _spec("process", "Process", PageType.SERVICE, "The steps by which the service is delivered."),
        _spec("guarantee", "Guarantee / policy", PageType.SERVICE, "Guarantee, refund, or service-level policy."),
        _spec("coverage_area", "Coverage area", PageType.SERVICE, "Geographic or segment coverage of the service."),
        _spec("availability", "Availability", PageType.SERVICE, "When/how the service can be booked or accessed."),
    ]

    table[PageType.LOCAL_SERVICE] = table[PageType.SERVICE] + [
        _spec("location", "Location", PageType.LOCAL_SERVICE, "The physical address or city the page is about."),
        _spec("service_area", "Service area", PageType.LOCAL_SERVICE, "Neighbourhoods, cities, or radius served."),
        _spec("local_landmark_context", "Local landmark context", PageType.LOCAL_SERVICE, "Local landmarks or districts anchoring relevance."),
        _spec("hours", "Business hours", PageType.LOCAL_SERVICE, "Opening/operating hours for the location."),
        _spec("local_proof", "Local proof", PageType.LOCAL_SERVICE, "Local reviews, clients, projects, or registrations."),
    ]

    table[PageType.ARTICLE] = [
        _spec("author", "Author", PageType.ARTICLE, "Named author with role or credentials."),
        _spec("key_points", "Key points", PageType.ARTICLE, "The main answers or takeaways, stated early."),
        _spec("evidence", "Evidence", PageType.ARTICLE, "Sources, data, or first-hand detail supporting the piece."),
    ]

    table[PageType.GLOSSARY] = [
        _spec("definition", "Definition", PageType.GLOSSARY, "An early 40-60 word definition with category and distinguishing function."),
        _spec("category", "Category", PageType.GLOSSARY, "The broader category the term belongs to."),
        _spec("distinguishing_function", "Distinguishing function", PageType.GLOSSARY, "What makes the term distinct from neighbours."),
        _spec("examples", "Examples", PageType.GLOSSARY, "Concrete examples of the term in use."),
        _spec("variants", "Variants", PageType.GLOSSARY, "Alternate spellings, names, or regional variants."),
    ]

    table[PageType.LISTICLE] = [
        _spec("criteria", "Selection criteria", PageType.LISTICLE, "Why these items were selected."),
        _spec("item_count", "Item count", PageType.LISTICLE, "How many items are listed and why."),
        _spec("shortlist_items", "Shortlist items", PageType.LISTICLE, "The listed options with distinct attributes each."),
        _spec("selection_notes", "Fit notes", PageType.LISTICLE, "Which reader/use-case each item fits."),
    ]

    table[PageType.COMPARISON] = [
        _spec("criteria_set", "Comparison criteria", PageType.COMPARISON, "Identical criteria applied to every option."),
        _spec("verdict", "Use-case verdict", PageType.COMPARISON, "Which option wins for which use case."),
        _spec("limitations", "Limitations", PageType.COMPARISON, "Disclosed limitations of each option."),
    ]

    table[PageType.CASE_STUDY] = [
        _spec("baseline", "Baseline", PageType.CASE_STUDY, "The measured starting state."),
        _spec("intervention", "Intervention", PageType.CASE_STUDY, "What was actually done."),
        _spec("timeframe", "Timeframe", PageType.CASE_STUDY, "How long the change took to show results."),
        _spec("measured_result", "Measured result", PageType.CASE_STUDY, "Quantified outcome with numbers and units."),
        _spec("method", "Method", PageType.CASE_STUDY, "How the result was measured."),
        _spec("attribution", "Attribution", PageType.CASE_STUDY, "Who is accountable and who verified."),
    ]

    table[PageType.SAAS_B2B] = [
        _spec("value_proposition", "Value proposition", PageType.SAAS_B2B, "The product's core outcome for a named ICP."),
        _spec("target_icp", "Target ICP", PageType.SAAS_B2B, "The audience segment served."),
        _spec("pricing_model", "Pricing model", PageType.SAAS_B2B, "How the product is priced."),
        _spec("security", "Security posture", PageType.SAAS_B2B, "Security/compliance posture buyers must verify."),
        _spec("proof", "Proof", PageType.SAAS_B2B, "Customers, metrics, or case evidence."),
    ]

    table[PageType.INTEGRATION] = [
        _spec("platform", "Platform", PageType.INTEGRATION, "The platform being integrated with."),
        _spec("setup_steps", "Setup steps", PageType.INTEGRATION, "Ordered, reproducible setup procedure."),
        _spec("requirements", "Requirements", PageType.INTEGRATION, "Prerequisites and permissions needed."),
        _spec("sync_scope", "Sync scope", PageType.INTEGRATION, "What data moves in which direction."),
        _spec("limitations", "Limitations", PageType.INTEGRATION, "Known limits and edge cases."),
    ]

    table[PageType.PAID_LANDING] = [
        _spec("offer", "Offer", PageType.PAID_LANDING, "The concrete offer matching the ad group."),
        _spec("cta", "Call to action", PageType.PAID_LANDING, "A single primary conversion action."),
        _spec("trust_proof", "Trust proof", PageType.PAID_LANDING, "Trust signals near the point of action."),
        _spec("keyword_message_match", "Keyword/message match", PageType.PAID_LANDING, "Search term continuity from ad to headline to body."),
    ]

    table[PageType.PRODUCT_CATEGORY] = [
        _spec("price_range", "Price range", PageType.PRODUCT_CATEGORY, "Price band or from-price for the category."),
        _spec("availability", "Availability", PageType.PRODUCT_CATEGORY, "Stock or purchase availability."),
        _spec("specifications", "Specifications", PageType.PRODUCT_CATEGORY, "Comparable specs shared across the category."),
        _spec("selection_criteria", "Selection criteria", PageType.PRODUCT_CATEGORY, "How to choose within the category."),
        _spec("purchase_options", "Purchase options", PageType.PRODUCT_CATEGORY, "Ways to buy, quote, or request the product."),
    ]

    table[PageType.TRUST_POLICY] = [
        _spec("policy_scope", "Policy scope", PageType.TRUST_POLICY, "What the policy or certification covers."),
        _spec("compliance_standards", "Compliance standards", PageType.TRUST_POLICY, "Named standards, auditors, or regulations."),
        _spec("data_handling", "Data handling", PageType.TRUST_POLICY, "How data is stored, processed, and retained."),
        _spec("contact", "Contact route", PageType.TRUST_POLICY, "How to raise questions or complaints."),
        _spec("last_updated", "Last updated", PageType.TRUST_POLICY, "The date the policy was last reviewed."),
    ]

    table[PageType.DOCS] = [
        _spec("prerequisites", "Prerequisites", PageType.DOCS, "What the reader needs before starting."),
        _spec("procedure", "Procedure", PageType.DOCS, "Ordered, reproducible steps."),
        _spec("parameters", "Parameters / inputs", PageType.DOCS, "Inputs, flags, or options with types."),
        _spec("examples", "Examples", PageType.DOCS, "Copy-pasteable examples."),
        _spec("troubleshooting", "Troubleshooting", PageType.DOCS, "Common failure modes and fixes."),
    ]

    table[PageType.GENERAL] = []
    return table


#: Required attributes per page type (PRD §5).
REQUIRED_ATTRIBUTES: dict[PageType, list[AttributeSpec]] = _build_required_attributes()

#: Intent-derived attribute additions (PRD §5 "likely intent classes").
INTENT_ATTRIBUTES: dict[IntentClass, list[AttributeSpec]] = {
    IntentClass.COMMERCIAL: [
        _spec("price", "Price / pricing basis", PageType.GENERAL, "Commercial intent expects explicit pricing information."),
    ],
    IntentClass.TRANSACTIONAL: [
        _spec("cta", "Call to action", PageType.GENERAL, "Transactional intent expects a concrete action path."),
        _spec("price", "Price / pricing basis", PageType.GENERAL, "Transactional intent expects pricing or quote clarity."),
    ],
    IntentClass.LOCAL: [
        _spec("service_area", "Service area", PageType.GENERAL, "Local intent expects an explicit service area."),
        _spec("location", "Location", PageType.GENERAL, "Local intent expects an explicit location."),
    ],
    IntentClass.COMPARISON: [
        _spec("criteria_set", "Comparison criteria", PageType.GENERAL, "Comparison intent expects shared criteria."),
        _spec("verdict", "Use-case verdict", PageType.GENERAL, "Comparison intent expects a per-use-case verdict."),
    ],
    IntentClass.EVALUATION: [
        _spec("criteria_set", "Comparison criteria", PageType.GENERAL, "Evaluation intent expects explicit criteria."),
    ],
    IntentClass.INFORMATIONAL: [
        _spec("examples", "Examples", PageType.GENERAL, "Informational intent is better served with examples."),
    ],
    IntentClass.RESEARCH: [
        _spec("method", "Method", PageType.GENERAL, "Research intent expects a stated method."),
    ],
    IntentClass.NAVIGATIONAL: [],
}

#: Location attributes added only when a location target is configured (PRD §5/FR-12).
LOCATION_ATTRIBUTES: list[AttributeSpec] = [
    _spec("location", "Location", PageType.GENERAL, "Explicit location for a location-targeted audit."),
    _spec("service_area", "Service area", PageType.GENERAL, "Service area for a location-targeted audit."),
]


def attributes_for(
    page_type: PageType,
    intents: Optional[Iterable[IntentClass]] = None,
    location_target: Optional[str] = None,
) -> list[AttributeSpec]:
    """Merge page-type required attributes with intent-derived and location attributes.

    De-duplicates by attribute ``key``, preserving page-type entries first so
    that their stricter descriptions win. Location attributes are appended only
    when ``location_target`` is set (PRD §5, FR-12).
    """
    merged: dict[str, AttributeSpec] = {}
    for spec in REQUIRED_ATTRIBUTES.get(page_type, []):
        merged.setdefault(spec.key, spec)
    for intent in intents or []:
        for spec in INTENT_ATTRIBUTES.get(intent, []):
            merged.setdefault(spec.key, spec)
    if location_target:
        for spec in LOCATION_ATTRIBUTES:
            merged.setdefault(spec.key, spec)
    return list(merged.values())


def satisfied_attribute_keys(eav_rows: Iterable[EAVRow]) -> set[str]:
    """Attribute keys with an explicit, non-empty value in the EAV inventory."""
    keys: set[str] = set()
    for row in eav_rows:
        if row.status == EAVStatus.EXPLICIT and row.value:
            keys.add(row.attribute.strip().lower())
    return keys
