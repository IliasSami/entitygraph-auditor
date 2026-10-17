"""Deterministic page-type classifier.

Keyword/heuristic rules in strict priority order. The classifier only
*suggests* a page type; a user selection always overrides it (handled by the
caller). Every result carries a bounded confidence in ``0.0–1.0`` and a short
rationale string that cites the concrete signals that fired — no opaque
scores.

Signals read: title, H1/H2… heading texts, the first 100 words, the full
normalized text, links (anchor texts), tables, ordered lists, and HTML
metadata (form/code counts). Field access goes through ``getattr`` defaults so
the classifier keeps working while the shared schema is still converging.
"""

from __future__ import annotations

import re
from typing import Any

from ega_schemas.content import ParsedDocument
from ega_schemas.enums import PageType

_WHAT_IS_RE = re.compile(r"\bwhat (is|are|does|do)\b|\bdefinition of\b|\bglossary\b")
_DEFINITION_IN_PROSE_RE = re.compile(
    r"\bwhat is\b|\bis defined as\b|\brefers to\b|\bdefinition\b|\bis a\b|\bis an\b"
)
_COMPARISON_RE = re.compile(
    r"\b(vs\.?|versus|alternatives?|compare|compared|comparison)\b"
)
_LISTICLE_RE = re.compile(r"\b(top|best)\s+\d+\b|\b\d+\s+(best|top)\b")
_CASE_STUDY_RE = re.compile(
    r"\bcase study\b|\bhow we helped\b|\bbefore and after\b"
)
_PLACE_AFTER_PREPOSITION_RE = re.compile(
    r"\b(?:in|near|around|serving|servicing)\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2}"
)
_SERVICE_AREA_RE = re.compile(
    r"\bservice areas?\b|\bcities we serve\b|\bneighborhoods?\b|\bserving [A-Z]"
)
_CTA_RE = re.compile(
    r"\b(sign up|sign-up|free trial|start (your )?free|try (it |us )?free|get started|"
    r"pricing|subscribe|request a demo|book a demo|claim (yours|now)|start now)\b",
    re.IGNORECASE,
)
_SERVICE_CTA_RE = re.compile(
    r"\b(book now|get a quote|request a quote|free estimate|contact us|call us|schedule)\b",
    re.IGNORECASE,
)
_SERVICE_NOUN_RE = re.compile(
    r"\b(services?|repair|cleaning|plumbing|electrical|roofing|landscaping|agency|"
    r"consulting|installation|maintenance|studio|dental|dentist|lawyer|law firm|"
    r"painting|moving|massage|therapy|clinic|salon|hvac)\b",
    re.IGNORECASE,
)
_SAAS_NOUN_RE = re.compile(
    r"\b(software|platform|dashboard|workspace|workflow|teams?|integrations?|api|"
    r"app|subscription|crm|automation|pipeline)\b",
    re.IGNORECASE,
)
_DOCS_PATTERNS = [
    "```",
    "npm install",
    "pip install",
    "yarn add",
    "curl -",
    "api reference",
    "endpoint",
    "parameters",
    "returns:",
    "authentication",
    "GET /",
    "POST /",
    "PUT /",
    "DELETE /",
]
_ABOUT_RE = re.compile(r"\babout us\b|\bour story\b|\bour team\b|\bwho we are\b|\babout our\b")
_TRUST_RE = re.compile(
    r"\b(privacy policy|terms of service|terms of use|cookie policy|gdpr|"
    r"iso ?27001|soc ?2|hipaa|certified|compliance|data processing)\b",
    re.IGNORECASE,
)
_INTEGRATION_RE = re.compile(
    r"\b(integrations?|works with|connect (to|with)|plug-?ins?|add-ons?)\b",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(r"([$€£¥]\s?\d|\bprice|\bpricing|\bmsrp|\bcost\b)", re.IGNORECASE)
_BUY_RE = re.compile(
    r"\b(add to cart|buy|shop|checkout|in stock|order now|free shipping)\b", re.IGNORECASE
)
_SPEC_RE = re.compile(
    r"\b(specs?|specifications?|dimensions|warranty|reviews?)\b", re.IGNORECASE
)
_PRODUCT_NOUN_RE = re.compile(
    r"\b(shoes?|mattress|laptops?|cameras?|phones?|tvs?|blenders?|drills?|jackets?|"
    r"coffee makers?|strollers?|monitors?|keyboards?|printers?|backpacks?|treadmills?|"
    r"vacuums?|products?|models?|collection|series|sizes)\b",
    re.IGNORECASE,
)
_BYLINE_RE = re.compile(r"\bby\s+[A-Z][a-z]+(\s+[A-Z][a-z]+){1,2}\b")
_HOWTO_RE = re.compile(r"\bhow to\b|\bstep\s?\d\b|\bwalkthrough\b|\btutorial\b")

_GENERAL_RATIONALE = "no strong signal"


def _first_h1(doc: ParsedDocument) -> str:
    for heading in doc.headings:
        if heading.level == 1:
            return heading.text
    return ""


def _heading_blob(doc: ParsedDocument) -> str:
    return " | ".join(h.text for h in doc.headings)


def _first_words(doc: ParsedDocument, count: int = 100) -> str:
    return " ".join(doc.normalized_text.split()[:count])


def _table_rows(table: Any) -> list[list[str]]:
    """Rows of a table payload (dict from the schema, or object)."""
    if isinstance(table, dict):
        rows = table.get("rows", [])
    else:
        rows = getattr(table, "rows", [])
    return [list(row) for row in rows]


def _list_fields(block: Any) -> tuple[bool, list[str]]:
    """``(ordered, items)`` of a list payload (dict from the schema, or object)."""
    if isinstance(block, dict):
        return bool(block.get("ordered", False)), list(block.get("items", []))
    return bool(getattr(block, "ordered", False)), list(getattr(block, "items", []))


def _has_ordered_list(doc: ParsedDocument, min_items: int = 3) -> bool:
    for block in getattr(doc, "lists", None) or []:
        ordered, items = _list_fields(block)
        if ordered and len(items) >= min_items:
            return True
    return False


def _has_comparison_table(doc: ParsedDocument) -> bool:
    for table in getattr(doc, "tables", None) or []:
        rows = _table_rows(table)
        if not rows:
            continue
        header = " ".join(rows[0]).lower()
        if re.search(r"\bvs\b|\bversus\b", header):
            return True
        if len(rows[0]) >= 3 and len(rows) >= 3 and "price" in header:
            return True
    return False


def _form_count(doc: ParsedDocument) -> int | None:
    meta = getattr(doc, "metadata", None) or {}
    value = meta.get("form_count")
    return int(value) if isinstance(value, int) else None


def _code_block_count(doc: ParsedDocument) -> int:
    meta = getattr(doc, "metadata", None) or {}
    value = meta.get("code_block_count", 0)
    return int(value) if isinstance(value, int) else 0


def classify_page_type(doc: ParsedDocument) -> tuple[PageType, float, str]:
    """Suggest ``(page_type, confidence, rationale)`` for a parsed document.

    Rules run in fixed priority order so identical inputs always classify
    identically. Confidence is a transparent heuristic, not a probability.
    """
    title = (doc.title or "").strip()
    h1 = _first_h1(doc)
    title_h1 = f"{title} {h1}".strip()
    title_h1_l = title_h1.lower()
    headings_l = _heading_blob(doc).lower()
    first100_l = _first_words(doc, 100).lower()
    text_l = doc.normalized_text.lower()

    # 1) GLOSSARY — definition in the first 100 words + a definition-style H1
    def_match = _DEFINITION_IN_PROSE_RE.search(first100_l)
    h1_match = _WHAT_IS_RE.search(title_h1_l)
    if def_match and h1_match:
        return (
            PageType.GLOSSARY,
            0.78,
            f"definition phrasing in first 100 words ('{def_match.group(0)}') "
            f"and title/H1 pattern ('{h1_match.group(0)}')",
        )

    # 2) COMPARISON — vs/alternatives wording or a comparison table
    comp = _COMPARISON_RE.search(title_h1_l) or _COMPARISON_RE.search(headings_l)
    if comp:
        return (
            PageType.COMPARISON,
            0.8,
            f"comparison keyword '{comp.group(0).strip()}' in title/heading",
        )
    if _has_comparison_table(doc):
        return (
            PageType.COMPARISON,
            0.72,
            "comparison table detected (feature/price columns or 'vs' header)",
        )

    # 3) LISTICLE — best/top-N in title + a numbered list
    listicle = _LISTICLE_RE.search(title_h1_l)
    if listicle and _has_ordered_list(doc):
        return (
            PageType.LISTICLE,
            0.75,
            f"'{listicle.group(0)}' in title/H1 plus a numbered list",
        )

    # 4) CASE_STUDY — case-study phrasing
    case = _CASE_STUDY_RE.search(title_h1_l) or _CASE_STUDY_RE.search(headings_l)
    if case:
        return (
            PageType.CASE_STUDY,
            0.7,
            f"case-study signal '{case.group(0).strip()}' in title/heading",
        )
    if re.search(r"\bbefore and after\b", text_l) and re.search(
        r"\b(results?|outcome|increase|reduced)\b", text_l
    ):
        return (
            PageType.CASE_STUDY,
            0.62,
            "before/after narrative with results language in body text",
        )

    # 5) LOCAL_SERVICE — place pattern in title/H1, repeated place mentions,
    #    or explicit service-area language
    place = _PLACE_AFTER_PREPOSITION_RE.search(title_h1)
    if place:
        return (
            PageType.LOCAL_SERVICE,
            0.74,
            f"place pattern '{place.group(0)}' in title/H1",
        )
    places = _PLACE_AFTER_PREPOSITION_RE.findall(doc.normalized_text)
    area = _SERVICE_AREA_RE.search(doc.normalized_text)
    if len(places) >= 3:
        return (
            PageType.LOCAL_SERVICE,
            0.66,
            f"{len(places)} 'in/near <Place>' occurrences in body text",
        )
    if area:
        return (
            PageType.LOCAL_SERVICE,
            0.6,
            f"service-area phrasing '{area.group(0)}' in body text",
        )

    # 6) PAID_LANDING / SAAS_B2B — CTA vocabulary + short page + form
    cta = _CTA_RE.search(title_h1) or _CTA_RE.search(first100_l)
    if cta and doc.word_count <= 400:
        forms = _form_count(doc)
        saas = _SAAS_NOUN_RE.search(title_h1_l) or _SAAS_NOUN_RE.search(headings_l)
        if saas:
            return (
                PageType.SAAS_B2B,
                0.68,
                f"CTA '{cta.group(0)}' on a short page ({doc.word_count} words) with "
                f"product language ('{saas.group(0)}')",
            )
        if forms:
            return (
                PageType.PAID_LANDING,
                0.66,
                f"CTA '{cta.group(0)}' on a short page ({doc.word_count} words) with a form",
            )
        note = "form presence unknown (non-HTML source)" if forms is None else "no form"
        return (
            PageType.PAID_LANDING,
            0.55,
            f"CTA '{cta.group(0)}' on a short page ({doc.word_count} words); {note}",
        )

    # 7) DOCS — code fences / install commands / API reference patterns
    hits = [p for p in _DOCS_PATTERNS if p.lower() in text_l]
    if "```" in doc.normalized_text or _code_block_count(doc) > 0:
        extra = f" plus docs vocabulary ({', '.join(hits[:3])})" if hits else ""
        return PageType.DOCS, 0.76, f"code blocks present{extra}"
    if len(hits) >= 2:
        return (
            PageType.DOCS,
            0.68,
            f"API/command patterns found: {', '.join(hits[:3])}",
        )

    # 8) ABOUT — about-us vocabulary in title/headings
    about = _ABOUT_RE.search(title_h1_l) or _ABOUT_RE.search(headings_l)
    if about:
        return (
            PageType.ABOUT,
            0.74,
            f"about-us phrasing '{about.group(0)}' in title/heading",
        )

    # 9) SERVICE — booking/quote CTA + service nouns in title/headings
    svc_cta = _SERVICE_CTA_RE.search(title_h1_l)
    svc_noun = _SERVICE_NOUN_RE.search(title_h1_l) or _SERVICE_NOUN_RE.search(headings_l)
    if svc_cta and svc_noun:
        return (
            PageType.SERVICE,
            0.68,
            f"CTA '{svc_cta.group(0)}' with service noun '{svc_noun.group(0)}' in title/heading",
        )

    # 10) HOMEPAGE — short, nav-heavy, brand-name-style H1, many links
    short_anchors = [
        link
        for link in doc.links
        if len(link.anchor_text.split()) <= 3 and link.anchor_text.strip()
    ]
    if (
        doc.links
        and len(doc.links) >= 5
        and len(short_anchors) >= max(4, int(0.6 * len(doc.links)))
        and doc.word_count <= 600
        and h1
        and len(h1.split()) <= 6
    ):
        return (
            PageType.HOMEPAGE,
            0.66,
            f"{len(doc.links)} links with mostly short anchors, short H1 "
            f"({len(h1.split())} words), {doc.word_count} words total",
        )

    # 11) TRUST_POLICY — privacy/terms/compliance vocabulary
    trust_title = _TRUST_RE.search(title_h1_l) or _TRUST_RE.search(headings_l)
    trust_hits = _TRUST_RE.findall(doc.normalized_text)
    if trust_title:
        return (
            PageType.TRUST_POLICY,
            0.8,
            f"policy/compliance keyword '{trust_title.group(0).strip()}' in title/heading",
        )
    if len(trust_hits) >= 2:
        return (
            PageType.TRUST_POLICY,
            0.6,
            f"{len(trust_hits)} policy/compliance keyword occurrences in body text",
        )

    # 12) INTEGRATION — integration/connect vocabulary
    integ = _INTEGRATION_RE.search(title_h1_l) or _INTEGRATION_RE.search(headings_l)
    if integ:
        return (
            PageType.INTEGRATION,
            0.68,
            f"integration phrasing '{integ.group(0)}' in title/heading",
        )

    # 13) PRODUCT_CATEGORY — product nouns + price/buy/spec signals
    product = _PRODUCT_NOUN_RE.search(title_h1_l) or _PRODUCT_NOUN_RE.search(headings_l)
    product_signals = [
        name
        for name, pattern in (("price", _PRICE_RE), ("buy/shop", _BUY_RE), ("specs", _SPEC_RE))
        if pattern.search(text_l)
    ]
    if product and len(product_signals) >= 2:
        return (
            PageType.PRODUCT_CATEGORY,
            0.64,
            f"product noun '{product.group(0)}' in title/heading with "
            f"{', '.join(product_signals)} signals",
        )

    # 14) ARTICLE — long prose with byline or how-to steps
    if doc.word_count >= 600:
        sample = doc.normalized_text[:600]
        byline = _BYLINE_RE.search(sample)
        steps = _HOWTO_RE.search(title_h1_l) or _has_ordered_list(doc, min_items=4)
        if byline:
            return (
                PageType.ARTICLE,
                0.66,
                f"long prose ({doc.word_count} words) with byline '{byline.group(0)}'",
            )
        if steps:
            return (
                PageType.ARTICLE,
                0.6,
                f"long prose ({doc.word_count} words) with how-to/step structure",
            )
        return (
            PageType.ARTICLE,
            0.52,
            f"long-form prose ({doc.word_count} words) without strong page-type markers",
        )

    # 15) fallback
    return PageType.GENERAL, 0.3, _GENERAL_RATIONALE
