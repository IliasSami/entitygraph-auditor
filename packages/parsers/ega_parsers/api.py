"""Public parser API: format entry points, dispatch, and document assembly.

``parse_markdown`` / ``parse_html`` / ``parse_text`` / ``parse_content`` /
``load_document_bytes`` all converge on :func:`_finish`, which:

* builds the deterministic structure (headings, sections, passages with the
  exact-slice invariant, tables, lists);
* computes text statistics (counts, densities, repetition, readability with
  language gating, boilerplate/duplicate ratios);
* records honest extraction flags on the caller's
  :class:`ega_schemas.content.ContentSourceMeta` (``original_format``,
  ``extraction_loss``, ``extraction_notes``, ``limitations``);
* classifies a suggested page type and wires
  ``suggested_page_type``/``confidence``/``rationale`` onto the document.

Every failure path falls back to plain-text extraction with a recorded
limitation; the only :class:`ValueError`s that escape are the documented
input-contract errors (unknown format/extension, unsafe DOCX container,
missing optional dependency).
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from ega_schemas.content import (
    ContentSourceMeta,
    ParsedDocument,
)

from ega_parsers.classify import classify_page_type
from ega_parsers.guards import guarded_scan
from ega_parsers.html_parser import scan_html
from ega_parsers.loader import extract_document
from ega_parsers.markdown_parser import scan_markdown
from ega_parsers.normalize import content_hash
from ega_parsers.result import ParseResult, RawLink
from ega_parsers.segment import build_structure
from ega_parsers.stats import compute_stats
from ega_parsers.text_parser import scan_text

BASE_LIMITATION = (
    "Text-only audit: does not validate crawlability, indexing, JavaScript "
    "rendering, schema validity, or bot access."
)
_EMPTY_PAGE_CHARS = 200
_BOILERPLATE_NOTE_THRESHOLD = 0.35
_DUPLICATE_NOTE_THRESHOLD = 0.25
_WORDS_PER_MINUTE = 200


# --------------------------------------------------------------------------------------
# contract verification — fails loudly (not silently) while schemas converge
# --------------------------------------------------------------------------------------

def _verify_contract(doc: ParsedDocument, source: ContentSourceMeta) -> None:
    """Raise a precise RuntimeError when the shared schema is missing fields."""
    missing_doc = [
        name
        for name in (
            "original_text", "tables", "lists", "metadata", "text_stats",
            "suggested_page_type", "confidence", "rationale",
        )
        if not hasattr(doc, name)
    ]
    missing_src = [
        name for name in ("original_format", "extraction_notes", "extraction_loss", "limitations")
        if not hasattr(source, name)
    ]
    if missing_doc or missing_src:
        raise RuntimeError(
            "ega_schemas content contract incomplete — ParsedDocument missing "
            f"{missing_doc or '[]'}, ContentSourceMeta missing {missing_src or '[]'}. "
            "See COORDINATION_TASKS.md (entry: Parsers worker) and merge the "
            "superset fields into packages/schemas/ega_schemas/content.py."
        )


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------

def _extend_unique(target: list[str], values: list[str]) -> None:
    for value in values:
        if value and value not in target:
            target.append(value)


def _same_site(url: str, base_url: str) -> bool:
    def netloc(u: str) -> str:
        return urlparse(u).netloc.lower().removeprefix("www.")

    left, right = netloc(url), netloc(base_url)
    return bool(left) and bool(right) and left == right


def _is_internal(url: str, is_anchor: bool, base_url: str | None) -> bool:
    """A link is internal when it stays on the audited origin.

    Scheme-less relative links (``/pricing``, ``pricing.html``) and pure
    fragments (``#faq``) are same-origin *by construction*, so they are
    internal even when no ``base_url`` was supplied. Absolute links are only
    internal when a ``base_url`` on the same host was supplied.
    """
    if is_anchor:
        return True
    parsed = urlparse(url)
    if not parsed.scheme and not parsed.netloc:
        return True
    return bool(base_url) and _same_site(url, base_url)


def _resolve_links(raw_links: list[RawLink], base_url: str | None) -> list[dict]:
    resolved: list[dict] = []
    for raw in raw_links:
        url = urljoin(base_url, raw.url) if base_url else raw.url
        resolved.append(
            {
                "url": url,
                "anchor_text": raw.anchor_text,
                "is_internal": _is_internal(url, raw.is_anchor, base_url),
                "is_anchor": raw.is_anchor,
            }
        )
    return resolved


def _link_rels(raw_links: list[RawLink], base_url: str | None) -> list[dict]:
    """``rel`` values are not part of the shared ``Link`` contract, so they are
    preserved in ``metadata`` for the security/SEO rules that need them."""
    return [
        {"url": urljoin(base_url, raw.url) if base_url else raw.url, "rel": raw.rel}
        for raw in raw_links
        if raw.rel
    ]


def _finish(
    result: ParseResult,
    source: ContentSourceMeta,
    *,
    original_format: str,
    base_url: str | None,
    language_hint: str | None,
) -> ParsedDocument:
    """Assemble a ParsedDocument, fill source flags, and classify."""
    normalized = result.normalized_text
    structure = build_structure(normalized, result.blocks)

    stats = compute_stats(
        normalized,
        [(p.passage_id, p.text) for p in structure.passages],
        language_hint=language_hint,
        boilerplate_extra_lines=result.boilerplate_lines,
    )

    headings_payload = [
        {
            "level": h.level,
            "text": h.text,
            "id": h.id,
            "offset": h.offset,
        }
        for h in structure.headings
    ]
    # ``Heading``/``Section`` carry no hierarchy fields in the shared contract,
    # so the parent/child trees are preserved in ``metadata`` instead of being
    # silently dropped by Pydantic's extra-field handling.
    heading_tree = [
        {"id": h.id, "parent_id": h.parent_id, "children": list(h.children)}
        for h in structure.headings
    ]
    passage_payloads = [
        {
            "passage_id": p.passage_id,
            "section_id": p.section_id,
            "text": p.text,
            "word_count": p.word_count,
            "start_offset": p.start_offset,
            "end_offset": p.end_offset,
        }
        for p in structure.passages
    ]
    passage_by_id = {p["passage_id"]: p for p in passage_payloads}
    sections_payload = [
        {
            "section_id": s.section_id,
            "heading": (
                {
                    "level": s.heading.level,
                    "text": s.heading.text,
                    "id": s.heading.id,
                    "offset": s.heading.offset,
                }
                if s.heading
                else None
            ),
            "passages": [passage_by_id[p.passage_id] for p in s.passages],
            "raw_text": s.raw_text,
            "word_count": s.word_count,
        }
        for s in structure.sections
    ]
    section_tree = [
        {
            "section_id": s.section_id,
            "level": s.level,
            "parent_section_id": s.parent_section_id,
            "children_section_ids": list(s.children_section_ids),
        }
        for s in structure.sections
    ]
    stats_payload = {
        "char_count": stats.char_count,
        "word_count": stats.word_count,
        "sentence_count": stats.sentence_count,
        "paragraph_count": stats.paragraph_count,
        "avg_sentence_words": stats.avg_sentence_words,
        "avg_paragraph_words": stats.avg_paragraph_words,
        "long_sentence_ratio": stats.long_sentence_ratio,
        "lexical_density": stats.lexical_density,
        "language": stats.language,
        "language_confidence": stats.language_confidence,
        "flesch_reading_ease": stats.flesch_reading_ease,
        "flesch_kincaid_grade": stats.flesch_kincaid_grade,
        "readability_warning": stats.readability_warning,
        "boilerplate_ratio": stats.boilerplate_ratio,
        "duplicate_paragraph_ratio": stats.duplicate_paragraph_ratio,
        "repeated_phrase_hits": [
            {"phrase": h.phrase, "count": h.count, "first_passage_id": h.first_passage_id}
            for h in stats.repeated_phrase_hits
        ],
    }

    word_count = stats.word_count
    payload: dict = {
        "raw_text": result.raw_text,
        "original_text": result.raw_text,
        "normalized_text": normalized,
        "title": result.title,
        "sections": sections_payload,
        "passages": passage_payloads,
        "headings": headings_payload,
        "links": _resolve_links(result.links, base_url),
        "word_count": word_count,
        "char_count": stats.char_count,
        "reading_time_minutes": round(word_count / _WORDS_PER_MINUTE, 1),
        "content_hash": content_hash(normalized),
        "tables": [
            {
                "section_id": t.section_id,
                "rows": t.rows,
                "start_offset": t.start_offset,
                "end_offset": t.end_offset,
            }
            for t in structure.tables
        ],
        "lists": [
            {
                "section_id": block.section_id,
                "ordered": block.ordered,
                "items": block.items,
                "start_offset": block.start_offset,
                "end_offset": block.end_offset,
            }
            for block in structure.lists
        ],
        "metadata": {
            **dict(result.metadata),
            "heading_tree": heading_tree,
            "section_tree": section_tree,
            "link_rels": _link_rels(result.links, base_url),
        },
        "text_stats": stats_payload,
    }
    doc = ParsedDocument.model_validate(payload)
    _verify_contract(doc, source)

    # ---- suggested page type (user selection overrides elsewhere) ----------
    page_type, confidence, rationale = classify_page_type(doc)
    doc.suggested_page_type = page_type.value
    doc.confidence = f"{confidence:.2f}"
    doc.rationale = rationale

    # ---- honest source flags ------------------------------------------------
    source.original_format = original_format
    _extend_unique(source.extraction_notes, result.notes)
    _extend_unique(source.limitations, [BASE_LIMITATION, *result.limitations])
    if not base_url and any(urlparse(raw.url).scheme for raw in result.links):
        _extend_unique(
            source.limitations,
            [
                "No base_url provided: internal-link detection for absolute "
                "links was not possible; they are recorded as extracted."
            ],
        )
    if len(normalized.strip()) < _EMPTY_PAGE_CHARS:
        source.extraction_loss = 1.0
        _extend_unique(
            source.extraction_notes,
            [
                f"Empty or near-empty page: normalized text is "
                f"{len(normalized.strip())} characters (< {_EMPTY_PAGE_CHARS})."
            ],
        )
    if stats.boilerplate_ratio > _BOILERPLATE_NOTE_THRESHOLD:
        _extend_unique(
            source.extraction_notes,
            [
                f"Boilerplate-heavy page: {stats.boilerplate_ratio:.0%} of "
                "extracted text is repeated short nav-like lines."
            ],
        )
    if stats.duplicate_paragraph_ratio > _DUPLICATE_NOTE_THRESHOLD:
        _extend_unique(
            source.extraction_notes,
            [
                f"Duplicate content: {stats.duplicate_paragraph_ratio:.0%} of "
                "paragraphs repeat verbatim."
            ],
        )
    if result.fallback_used:
        source.extraction_loss = 1.0

    return doc


# --------------------------------------------------------------------------------------
# public entry points
# --------------------------------------------------------------------------------------

def parse_markdown(
    text: str,
    source: ContentSourceMeta,
    base_url: str | None = None,
    language_hint: str | None = None,
) -> ParsedDocument:
    """Parse Markdown text into a :class:`ParsedDocument`."""
    result = guarded_scan(scan_markdown, text, "Markdown")
    return _finish(
        result, source, original_format="markdown", base_url=base_url, language_hint=language_hint
    )


def parse_html(
    html: str,
    source: ContentSourceMeta,
    base_url: str | None = None,
    language_hint: str | None = None,
) -> ParsedDocument:
    """Parse HTML into a :class:`ParsedDocument` (BeautifulSoup, no network)."""
    result = guarded_scan(scan_html, html, "HTML")
    return _finish(
        result, source, original_format="html", base_url=base_url, language_hint=language_hint
    )


def parse_text(
    text: str,
    source: ContentSourceMeta,
    base_url: str | None = None,
    language_hint: str | None = None,
) -> ParsedDocument:
    """Parse plain text into a :class:`ParsedDocument`."""
    result = guarded_scan(scan_text, text, "Plain-text")
    return _finish(
        result, source, original_format="text", base_url=base_url, language_hint=language_hint
    )


def parse_content(
    text: str,
    *,
    content_format: str,
    source: ContentSourceMeta,
    base_url: str | None = None,
    language_hint: str | None = None,
) -> ParsedDocument:
    """Dispatch on *content_format*: ``'markdown'``/``'md'``, ``'html'``, ``'text'``."""
    fmt = (content_format or "").strip().lower()
    if fmt in ("markdown", "md"):
        return parse_markdown(text, source, base_url=base_url, language_hint=language_hint)
    if fmt == "html":
        return parse_html(text, source, base_url=base_url, language_hint=language_hint)
    if fmt == "text":
        return parse_text(text, source, base_url=base_url, language_hint=language_hint)
    raise ValueError(
        f"Unknown content_format {content_format!r}; expected 'markdown', 'md', "
        "'html' or 'text'."
    )


def load_document_bytes(
    data: bytes,
    filename: str,
    source: ContentSourceMeta,
    *,
    base_url: str | None = None,
    language_hint: str | None = None,
) -> ParsedDocument:
    """Parse file bytes (``.md``/``.txt``/``.html``/``.htm``/``.docx``/``.pdf``).

    ``ValueError`` is raised for unknown extensions, malformed/oversized DOCX
    containers and a missing optional ``pypdf`` dependency — the caller can
    surface those directly. HTML byte content that fails to parse falls back
    to plain text with a recorded limitation.
    """
    original_format, result = extract_document(data, filename)
    return _finish(
        result,
        source,
        original_format=original_format,
        base_url=base_url,
        language_hint=language_hint,
    )
