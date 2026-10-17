"""ega_parsers — deterministic content parsers for EntityGraph Auditor.

Zero-network, zero-LLM extraction: Markdown, HTML, plain text and uploaded
documents (``.md``/``.txt``/``.html``/``.htm``/``.docx``, plus ``.pdf`` when
the optional ``pypdf`` dependency is present) are turned into the shared
:class:`ega_schemas.content.ParsedDocument` with exact character offsets,
stable IDs, honest extraction notes/limitations and a suggested page type.

Example::

    from ega_parsers import parse_content
    from ega_schemas.content import ContentSourceMeta

    source = ContentSourceMeta()
    doc = parse_content("# Hello", content_format="markdown", source=source)
"""

from ega_parsers.api import (
    load_document_bytes,
    parse_content,
    parse_html,
    parse_markdown,
    parse_text,
)
from ega_parsers.classify import classify_page_type

# NOTE: ``DocumentParser`` is the legacy high-level facade kept for the
# pre-existing consumers (imported from ``ega_parsers`` at package import time).
from ega_parsers.document_parser import DocumentParser
from ega_parsers.linguistics import detect_language
from ega_parsers.metrics import (
    compute_flesch_reading_ease,
    compute_lexical_diversity,
    detect_repeated_phrases,
    extract_sentences,
)
from ega_parsers.normalize import content_hash, normalize_text

# NOTE: the SSRF guards and the (network-only, opt-in) URL fetcher are
# re-exported because other packages import them from ``ega_parsers``.
from ega_parsers.url_fetcher import (
    FetchException,
    SSRFException,
    fetch_url,
    validate_url_safety,
)

__all__ = [
    "DocumentParser",
    "FetchException",
    "SSRFException",
    "classify_page_type",
    "compute_flesch_reading_ease",
    "compute_lexical_diversity",
    "content_hash",
    "detect_language",
    "detect_repeated_phrases",
    "extract_sentences",
    "fetch_url",
    "load_document_bytes",
    "normalize_text",
    "parse_content",
    "parse_html",
    "parse_markdown",
    "parse_text",
    "validate_url_safety",
]
