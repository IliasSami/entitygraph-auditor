"""Deterministic Entity SEO and AEO Brief Generator (PRD FR-18).

Constructs high-precision, machine-efficient content briefs containing:
1. Search-intent classification & question patterns derived from the target query.
2. Grounded facts & proof points from active context packs.
3. Structured H2/H3 outline cards with answer-first lead directives and word counts.
4. Named entity anchors and schema types.
5. Lexicon directives (terms to include, replace, avoid).

Zero paid API dependencies: 100% deterministic local generation.
"""

from __future__ import annotations

import re
import uuid
from typing import Any


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", cleaned)


def generate_content_brief(
    target_query: str,
    page_type: str = "service",
    brand_name: str | None = None,
    location: str | None = None,
    context_pack_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate an enterprise-grade Entity SEO and AEO brief from query parameters."""
    query = (target_query or "Agency Services").strip()
    # Neutral placeholders when the caller supplies no brand/location. We never
    # invent a specific company name or city — the outline says "Your brand" /
    # "your market" until real project data or a canonical fact is provided.
    brand = (brand_name or "").strip() or "Your brand"
    loc = (location or "").strip() or "your market"
    ptype = (page_type or "service").lower()

    # Determine intent
    intent = "Commercial / Advisory"
    if any(w in query.lower() for w in ("how", "what", "why", "guide", "learn", "definition")):
        intent = "Informational / Educational"
    elif any(w in query.lower() for w in ("cost", "pricing", "rate", "fee", "plans", "quote")):
        intent = "Commercial / Transactional"

    # Extract verified facts from context pack if available
    pack_facts: list[str] = []
    pack_rules: list[str] = []
    banned_words: list[str] = ["100% unhackable", "unhackable", "guaranteed", "miracle", "foolproof"]

    if context_pack_data:
        for f in context_pack_data.get("canonical_facts") or []:
            if isinstance(f, dict):
                k = f.get("key") or f.get("property") or ""
                v = f.get("value") or ""
                pack_facts.append(f"{k}: {v}" if k else v)
            elif isinstance(f, str):
                pack_facts.append(f)

        for r in context_pack_data.get("brand_rules") or []:
            if isinstance(r, dict):
                pack_rules.append(r.get("statement") or r.get("rule_id") or "")
            elif isinstance(r, str):
                pack_rules.append(r)

        for b in context_pack_data.get("banned_terms") or []:
            if isinstance(b, str) and b not in banned_words:
                banned_words.append(b)

    # No fabricated facts: when the active pack has no canonical facts we return an
    # explicit placeholder so the UI never presents an invented "verified" claim.
    grounded = bool(pack_facts)
    if not pack_facts:
        pack_facts = [
            "No verified fact in the active context pack — import a canonical fact to ground this source"
        ]

    def _fact(index: int, _label: str) -> str:
        return (
            pack_facts[index]
            if index < len(pack_facts)
            else "No verified fact for this section — add a canonical fact to the active context pack"
        )

    # Deterministic source pool. These are query-derived patterns and real pack
    # facts — NOT results from a People-Also-Ask / Perplexity / AI-engine lookup,
    # so the labels say exactly that.
    sources: list[dict[str, Any]] = [
        {
            "id": f"src-{uuid.uuid4().hex[:6]}",
            "type": "question",
            "title": f"How much should an organization pay for {query.lower()}?",
            "source": "Query pattern · Pricing",
            "tag": "High intent",
            "tagColor": "bg-primary-soft text-primary",
        },
        {
            "id": f"src-{uuid.uuid4().hex[:6]}",
            "type": "fact",
            "title": (
                pack_facts[0]
                if grounded
                else "No verified pricing fact in the active context pack"
            ),
            "source": "Context pack · canonical fact" if grounded else "Unverified placeholder",
            "tag": "Verified fact" if grounded else "Needs grounding",
            "tagColor": "bg-emerald-50 text-emerald-800 border border-emerald-200",
        },
        {
            "id": f"src-{uuid.uuid4().hex[:6]}",
            "type": "gap",
            "title": f"Unanswered buyer questions about {query.lower()}",
            "source": "Coverage gap · derived",
            "tag": "Coverage gap",
            "tagColor": "bg-surface-subtle text-muted-foreground",
        },
        {
            "id": f"src-{uuid.uuid4().hex[:6]}",
            "type": "question",
            "title": f"What is the difference between general providers and specialized {query.lower()}?",
            "source": "Query pattern · Differentiation",
            "tag": "Core intent",
            "tagColor": "bg-indigo-50 text-indigo-700",
        },
    ]

    # Generate outline sections matching Aentio Calm Technical Craft schema
    sections: list[dict[str, Any]] = [
        {
            "id": f"sec-{uuid.uuid4().hex[:6]}",
            "h2Number": 1,
            "title": f"Why Modern Organizations Require Dedicated {query.title()}",
            "badge": "Answer",
            "badgeColor": "bg-emerald-50 text-emerald-800",
            "entities": [
                {"name": brand, "type": "Organization"},
                {"name": query.title(), "type": "Service"},
                {"name": loc, "type": "Place"},
            ],
            "facts": [_fact(0, "definition")],
            "directive": (
                f"Open with an answer-first definition: clearly state that {brand} delivers "
                f"structured {query.lower()} tailored for operations in {loc}. "
                "Explicitly answer what the service is and who it is for in the first 2 sentences."
            ),
            "wordRange": "120–180 words",
        },
        {
            "id": f"sec-{uuid.uuid4().hex[:6]}",
            "h2Number": 2,
            "title": f"Transparent Pricing & Engagement Structure for {query.title()}",
            "badge": "Pricing",
            "badgeColor": "bg-amber-50 text-amber-800",
            "entities": [
                {"name": "Pricing Structure", "type": "Concept"},
                {"name": "Engagement Model", "type": "Concept"},
            ],
            "facts": [
                _fact(1, "pricing")
            ],
            "directive": (
                "Provide concrete, transparent pricing tiers with explicit numerical boundaries. "
                "Avoid ambiguous marketing buzzwords; provide clear deliverables per bracket."
            ),
            "wordRange": "150–220 words",
        },
        {
            "id": f"sec-{uuid.uuid4().hex[:6]}",
            "h2Number": 3,
            "title": "Core Operational Mechanics & Technology Stack",
            "badge": "Mechanism",
            "badgeColor": "bg-indigo-50 text-indigo-700",
            "entities": [
                {"name": "Platform Integration", "type": "Standard"},
                {"name": "Workflow Automation", "type": "System"},
            ],
            "facts": [
                _fact(2, "mechanism")
            ],
            "directive": (
                "Explain the exact step-by-step methodology and tooling integration. "
                "Structure passages with clear subject-predicate-object triples so search crawlers "
                "and LLM answer engines extract standalone factual summaries."
            ),
            "wordRange": "200–280 words",
        },
        {
            "id": f"sec-{uuid.uuid4().hex[:6]}",
            "h2Number": 4,
            "title": "Compliance, Verification & Quality Standards",
            "badge": "Authority",
            "badgeColor": "bg-surface-subtle text-foreground",
            "entities": [
                {"name": "Regulatory Compliance", "type": "Standard"},
                {"name": "Quality Assurance", "type": "Process"},
            ],
            "facts": pack_rules[:2] if pack_rules else ["No brand-rule fact in the active context pack"],
            "directive": (
                "Highlight formal certifications, compliance checkpoints, and verification protocols. "
                "Include a standalone FAQ or definition block suitable for direct AI extraction."
            ),
            "wordRange": "160–240 words",
        },
    ]

    # Lexicon suggestions. `include` only surfaces the real query term and any
    # pack-provided terms; `replace`/`avoid` are deterministic style guidance.
    lexicon_include = [query.lower()]
    for fact in pack_facts:
        head = fact.split(":", 1)[0].strip().lower()
        if head and head not in lexicon_include and len(head) <= 40:
            lexicon_include.append(head)
    lexicon = {
        "include": lexicon_include[:6],
        "replace": [
            {"from": "industry-leading", "to": "specialized and verified"},
            {"from": "unmatched synergy", "to": "direct system integration"},
            {"from": "best-in-class", "to": "standard-compliant"},
        ],
        "avoid": banned_words,
    }

    return {
        "target_query": query,
        "page_type": ptype,
        "brand_name": brand,
        "location": loc,
        "intent": intent,
        "recommended_word_count": "900–1,400 words",
        "reading_level": "Grade 10–12 (Technical/Professional)",
        "grounded": grounded,
        "disclaimer": (
            "Internal editorial heuristic. Sections and sources are deterministic "
            "templates derived from the target query and the active context pack; "
            "no external search or AI-engine lookup was performed. Facts marked "
            "\"Unverified placeholder\" are not verified — add a canonical fact to the "
            "active context pack before publishing."
        ),
        "sources": sources,
        "sections": sections,
        "lexicon": lexicon,
    }
