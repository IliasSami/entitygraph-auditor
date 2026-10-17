"""Page-type profiles and composite weight presets (PRD §5, PRD §9.4).

Every one of the 16 ``PageType`` values gets a profile describing what a good
page of that type looks like: expected central entity, likely intents, answer
shapes, proof types, required attributes, conversion goal, relevancy penalties,
failure patterns, and the AVR weight preset used for the composite score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ega_schemas.enums import AnswerShape, IntentClass, PageType

from auditor.rules.attributes import REQUIRED_ATTRIBUTES

#: Allowed composite weight presets (PRD §9.4 table columns).
WEIGHT_PRESETS: tuple[str, ...] = ("informational", "listicle", "commercial", "case_study")

PROFILE_VERSION = "1.0"


@dataclass(frozen=True)
class PageProfile:
    """Deterministic description of what a page type must contain (PRD §5)."""

    page_type: PageType
    label: str
    expected_central_entity_desc: str
    likely_intents: tuple[IntentClass, ...]
    expected_answer_shapes: tuple[AnswerShape, ...]
    expected_proof_types: tuple[str, ...]
    required_attributes: tuple[str, ...]
    conversion_goal_desc: str
    relevancy_penalties: tuple[str, ...]
    score_preset: str
    local_relevant: bool
    common_failure_patterns: tuple[str, ...]
    glossary_early_definition: bool = False


def _attrs(page_type: PageType) -> tuple[str, ...]:
    return tuple(spec.key for spec in REQUIRED_ATTRIBUTES.get(page_type, []))


def _profile(
    page_type: PageType,
    label: str,
    central: str,
    intents: tuple[IntentClass, ...],
    shapes: tuple[AnswerShape, ...],
    proofs: tuple[str, ...],
    conversion: str,
    penalties: tuple[str, ...],
    preset: str,
    local: bool,
    failures: tuple[str, ...],
    glossary_early_definition: bool = False,
) -> PageProfile:
    return PageProfile(
        page_type=page_type,
        label=label,
        expected_central_entity_desc=central,
        likely_intents=intents,
        expected_answer_shapes=shapes,
        expected_proof_types=proofs,
        required_attributes=_attrs(page_type),
        conversion_goal_desc=conversion,
        relevancy_penalties=penalties,
        score_preset=preset,
        local_relevant=local,
        common_failure_patterns=failures,
        glossary_early_definition=glossary_early_definition,
    )


def _build_profiles() -> dict[PageType, PageProfile]:
    profiles: dict[PageType, PageProfile] = {}

    profiles[PageType.GLOSSARY] = _profile(
        PageType.GLOSSARY,
        "Glossary / definition",
        "One concept/term (EntityKind.CONCEPT) defined on the page.",
        (IntentClass.INFORMATIONAL, IntentClass.NAVIGATIONAL),
        (AnswerShape.DEFINITION,),
        ("primary sources", "standards references", "internal topic links"),
        "Navigate to related topic or deeper resource.",
        (
            "definition buried after several paragraphs",
            "definition missing category or distinguishing function",
            "term mixed with unrelated product pitch",
        ),
        "informational",
        False,
        (
            "definition under 40 or over 60 words",
            "no examples or variants after the definition",
            "several terms defined without one clear primary term",
        ),
        glossary_early_definition=True,
    )

    profiles[PageType.ARTICLE] = _profile(
        PageType.ARTICLE,
        "Informational article / tutorial",
        "The topic/concept the article explains (EntityKind.CONCEPT or PROCESS).",
        (IntentClass.INFORMATIONAL, IntentClass.RESEARCH),
        (AnswerShape.PROCEDURE, AnswerShape.DEFINITION, AnswerShape.CHECKLIST),
        ("cited sources", "author credentials", "first-hand detail"),
        "Read, then continue to a related resource or tool.",
        (
            "topic drift away from the stated query",
            "claims with no linked evidence",
            "fluff intros delaying the answer",
        ),
        "informational",
        False,
        (
            "no named author or expertise signal",
            "generic restatement of other articles",
            "answer appears only in the final section",
        ),
    )

    profiles[PageType.DOCS] = _profile(
        PageType.DOCS,
        "Technical documentation",
        "The product/API/feature being documented (EntityKind.PRODUCT_SERVICE or CONCEPT).",
        (IntentClass.INFORMATIONAL, IntentClass.NAVIGATIONAL),
        (AnswerShape.PROCEDURE, AnswerShape.CHECKLIST),
        ("code samples", "version stamps", "official references"),
        "Complete the documented task successfully.",
        (
            "steps not ordered or not reproducible",
            "prerequisites assumed but unstated",
            "version/parameter drift",
        ),
        "informational",
        False,
        (
            "missing troubleshooting for common failures",
            "parameters listed without types or defaults",
            "explanation without a runnable example",
        ),
    )

    profiles[PageType.LISTICLE] = _profile(
        PageType.LISTICLE,
        "Listicle / 'best X' page",
        "The category being enumerated (EntityKind.CONCEPT or USE_CASE).",
        (IntentClass.COMPARISON, IntentClass.COMMERCIAL, IntentClass.INFORMATIONAL),
        (AnswerShape.SHORTLIST, AnswerShape.CHECKLIST),
        ("comparison criteria", "verifiable attributes per item"),
        "Pick an item and visit its detail page.",
        (
            "items with no distinguishing attributes",
            "no stated selection criteria",
            "undisclosed affiliation or ads mixed into editorial",
        ),
        "listicle",
        False,
        (
            "every item described identically",
            "no fit notes for different reader types",
            "count mismatch between title and list",
        ),
    )

    profiles[PageType.COMPARISON] = _profile(
        PageType.COMPARISON,
        "Comparison / alternative / versus",
        "The option pair or set being compared (EntityKind.COMPETITOR or PRODUCT_SERVICE).",
        (IntentClass.COMPARISON, IntentClass.EVALUATION, IntentClass.COMMERCIAL),
        (AnswerShape.COMPARISON_VERDICT, AnswerShape.TABLE),
        ("identical criteria per option", "limitation disclosures", "verifiable specs"),
        "Choose an option and proceed to its page.",
        (
            "different criteria applied to different options",
            "no verdict for any use case",
            "limitations hidden or omitted",
        ),
        "listicle",
        False,
        (
            "one option consistently favoured without criteria",
            "comparison table with no narrative verdict",
            "stale pricing or version data",
        ),
    )

    profiles[PageType.CASE_STUDY] = _profile(
        PageType.CASE_STUDY,
        "Case study / customer story",
        "The customer/organization served (EntityKind.ORGANIZATION).",
        (IntentClass.EVALUATION, IntentClass.COMMERCIAL, IntentClass.RESEARCH),
        (AnswerShape.PROOF_BLOCK, AnswerShape.TABLE),
        ("measured results", "named customer", "method disclosure"),
        "Request a similar engagement or proof call.",
        (
            "results without baseline",
            "outcome claims without method",
            "attribution unclear (who did what)",
        ),
        "case_study",
        False,
        (
            "timeframe missing",
            "numbers without units or measurement window",
            "quote with no name or role",
        ),
    )

    profiles[PageType.HOMEPAGE] = _profile(
        PageType.HOMEPAGE,
        "Homepage / entity home",
        "The brand/organization itself (EntityKind.BRAND or ORGANIZATION).",
        (IntentClass.NAVIGATIONAL, IntentClass.COMMERCIAL),
        (AnswerShape.DEFINITION, AnswerShape.CTA),
        ("brand identity proof", "service architecture links"),
        "Route visitors to the right detail page or contact path.",
        (
            "exhaustive topic stuffing instead of a coherent architecture",
            "no link to detail pages",
            "ambiguous brand category",
        ),
        "commercial",
        False,
        (
            "every service crammed into the hero",
            "no named brand near the top",
            "dead-end page with no onward links",
        ),
    )

    profiles[PageType.ABOUT] = _profile(
        PageType.ABOUT,
        "About / team / company story",
        "The organization and its people (EntityKind.ORGANIZATION).",
        (IntentClass.NAVIGATIONAL, IntentClass.EVALUATION),
        (AnswerShape.PROOF_BLOCK, AnswerShape.DEFINITION),
        ("named people", "founding facts", "verifiable milestones"),
        "Trust the organization and continue to services.",
        (
            "unverifiable brand superlatives",
            "no named people or roles",
            "story with no verifiable facts",
        ),
        "commercial",
        False,
        (
            "mission-only page with zero facts",
            "team listed without credentials",
            "claims of being '#1' without evidence",
        ),
    )

    profiles[PageType.SERVICE] = _profile(
        PageType.SERVICE,
        "Commercial service page",
        "The service offered (EntityKind.PRODUCT_SERVICE) delivered by the brand.",
        (IntentClass.COMMERCIAL, IntentClass.TRANSACTIONAL, IntentClass.EVALUATION),
        (AnswerShape.PRICING_FACT, AnswerShape.PROCEDURE, AnswerShape.CTA),
        ("pricing", "process detail", "guarantee or policy", "customer proof"),
        "Request a quote, booking, or consultation.",
        (
            "promises without timeframe or price",
            "no process explanation",
            "vague response-time or outcome wording",
        ),
        "commercial",
        False,
        (
            "guarantee language without terms",
            "no availability information",
            "service described only in marketing adjectives",
        ),
    )

    profiles[PageType.LOCAL_SERVICE] = _profile(
        PageType.LOCAL_SERVICE,
        "Location-specific service page",
        "One dominant geographic/service entity for a single city or area (EntityKind.PRODUCT_SERVICE + LOCATION).",
        (IntentClass.LOCAL, IntentClass.COMMERCIAL, IntentClass.TRANSACTIONAL),
        (AnswerShape.PRICING_FACT, AnswerShape.PROOF_BLOCK, AnswerShape.CTA),
        ("local proof", "service-area signals", "hours and location data"),
        "Call, book, or visit the location.",
        (
            "unnecessary city mixing (multiple unrelated cities)",
            "no real local relevance beyond the city name",
            "inconsistent service-area signals",
        ),
        "commercial",
        True,
        (
            "city name stuffed without local context",
            "no hours or location data",
            "no local proof (reviews, projects, registration)",
        ),
    )

    profiles[PageType.SAAS_B2B] = _profile(
        PageType.SAAS_B2B,
        "B2B / SaaS commercial page",
        "The software product (EntityKind.PRODUCT_SERVICE).",
        (IntentClass.COMMERCIAL, IntentClass.EVALUATION, IntentClass.TRANSACTIONAL),
        (AnswerShape.PRICING_FACT, AnswerShape.PROOF_BLOCK, AnswerShape.CTA),
        ("customer proof", "security posture", "pricing model"),
        "Start a trial or request a demo.",
        (
            "feature list with no outcomes",
            "no pricing model or ICP clarity",
            "security questions unanswered",
        ),
        "commercial",
        False,
        (
            "vague 'AI-powered' claims with no mechanism",
            "no named customers or metrics",
            "CTA repeated without offer clarity",
        ),
    )

    profiles[PageType.INTEGRATION] = _profile(
        PageType.INTEGRATION,
        "Integration / platform page",
        "The platform pair being integrated (EntityKind.PLATFORM).",
        (IntentClass.INFORMATIONAL, IntentClass.COMMERCIAL, IntentClass.NAVIGATIONAL),
        (AnswerShape.PROCEDURE, AnswerShape.CHECKLIST),
        ("setup steps", "requirements list", "limitation disclosure"),
        "Connect the integration or read the setup steps.",
        (
            "setup steps missing or unordered",
            "sync scope unstated",
            "limitations hidden",
        ),
        "commercial",
        False,
        (
            "marketing page instead of a procedure",
            "no version or permission requirements",
            "bidirectional sync claimed without detail",
        ),
    )

    profiles[PageType.PAID_LANDING] = _profile(
        PageType.PAID_LANDING,
        "Paid-search landing page",
        "The offer/product advertised (EntityKind.PRODUCT_SERVICE or CTA).",
        (IntentClass.TRANSACTIONAL, IntentClass.COMMERCIAL),
        (AnswerShape.CTA, AnswerShape.PRICING_FACT, AnswerShape.PROOF_BLOCK),
        ("offer clarity", "trust proof near the CTA", "message continuity from ad"),
        "Convert on the single advertised action.",
        (
            "search-term/ad-group mismatch (message discontinuity)",
            "offer buried or ambiguous",
            "high form friction without justification",
        ),
        "commercial",
        False,
        (
            "multiple competing CTAs",
            "no trust signal at the point of action",
            "headline does not echo the ad group's search term",
        ),
    )

    profiles[PageType.PRODUCT_CATEGORY] = _profile(
        PageType.PRODUCT_CATEGORY,
        "Product / category page",
        "The product category or catalogue node (EntityKind.PRODUCT_SERVICE).",
        (IntentClass.COMMERCIAL, IntentClass.COMPARISON),
        (AnswerShape.TABLE, AnswerShape.SHORTLIST, AnswerShape.PRICING_FACT),
        ("specifications", "price bands", "availability"),
        "Compare and select a product to purchase or quote.",
        (
            "specs not comparable across items",
            "no price band or availability",
            "no selection guidance",
        ),
        "commercial",
        False,
        (
            "thin category text with only product cards",
            "no selection criteria",
            "availability unclear",
        ),
    )

    profiles[PageType.TRUST_POLICY] = _profile(
        PageType.TRUST_POLICY,
        "Trust, certification, policy, or compliance page",
        "The organization's compliance posture (EntityKind.ORGANIZATION or STANDARD).",
        (IntentClass.EVALUATION, IntentClass.INFORMATIONAL),
        (AnswerShape.PROOF_BLOCK, AnswerShape.DEFINITION),
        ("named standards", "auditor or certification references", "last-reviewed date"),
        "Increase confidence; answer diligence questions.",
        (
            "certification logos without names or dates",
            "policy text without scope",
            "no last-updated date",
        ),
        "informational",
        False,
        (
            "generic trust badges with no substantiation",
            "regulations name-dropped without mapping",
            "no contact route for questions",
        ),
    )

    profiles[PageType.GENERAL] = _profile(
        PageType.GENERAL,
        "General / custom page",
        "Whatever the page is primarily about (user-supplied central entity).",
        (IntentClass.INFORMATIONAL,),
        (AnswerShape.DEFINITION, AnswerShape.CHECKLIST),
        ("any verifiable evidence present"),
        "Stated by the user; defaults to informed reading.",
        (
            "no clear central entity",
            "no declared intent",
            "assumed proof requirements",
        ),
        "informational",
        False,
        (
            "page type unknown → rubric applied generically",
            "missing everything the auditor expected",
            "user override not provided",
        ),
    )
    return profiles


#: Full page-type profile registry (PRD §5): all 16 PageType values.
PAGE_PROFILES: dict[PageType, PageProfile] = _build_profiles()


def get_profile(page_type: PageType, override_preset: Optional[str] = None) -> PageProfile:
    """Return the profile for ``page_type``; optionally override the weight preset.

    Raises ``ValueError`` when the override preset is not one of the four PRD
    §9.4 columns.
    """
    profile = PAGE_PROFILES.get(page_type, PAGE_PROFILES[PageType.GENERAL])
    if override_preset is None or override_preset == profile.score_preset:
        return profile
    if override_preset not in WEIGHT_PRESETS:
        raise ValueError(
            f"Unknown score preset {override_preset!r}; expected one of {sorted(WEIGHT_PRESETS)}"
        )
    return PageProfile(
        page_type=profile.page_type,
        label=profile.label,
        expected_central_entity_desc=profile.expected_central_entity_desc,
        likely_intents=profile.likely_intents,
        expected_answer_shapes=profile.expected_answer_shapes,
        expected_proof_types=profile.expected_proof_types,
        required_attributes=profile.required_attributes,
        conversion_goal_desc=profile.conversion_goal_desc,
        relevancy_penalties=profile.relevancy_penalties,
        score_preset=override_preset,
        local_relevant=profile.local_relevant,
        common_failure_patterns=profile.common_failure_patterns,
        glossary_early_definition=profile.glossary_early_definition,
    )


#: Exact PRD §9.4 composite weights, as fractions summing to 1.0.
_AVR_WEIGHT_TABLE: dict[str, dict[str, float]] = {
    "informational": {"EOS": 0.15, "ERS": 0.15, "KGR": 0.10, "FCS": 0.15, "PRS": 0.15, "CWS": 0.20, "HRS": 0.10},
    "listicle": {"EOS": 0.15, "ERS": 0.10, "KGR": 0.15, "FCS": 0.15, "PRS": 0.15, "CWS": 0.20, "HRS": 0.10},
    "commercial": {"EOS": 0.15, "ERS": 0.15, "KGR": 0.15, "FCS": 0.10, "PRS": 0.15, "CWS": 0.15, "HRS": 0.15},
    "case_study": {"EOS": 0.10, "ERS": 0.15, "KGR": 0.10, "FCS": 0.05, "PRS": 0.10, "CWS": 0.35, "HRS": 0.15},
}


def weight_preset(preset: str) -> dict[str, float]:
    """Return the AVR weight table (fractions summing to 1.0) for a preset (PRD §9.4)."""
    try:
        return dict(_AVR_WEIGHT_TABLE[preset])
    except KeyError:
        raise ValueError(f"Unknown score preset {preset!r}; expected one of {sorted(WEIGHT_PRESETS)}") from None
