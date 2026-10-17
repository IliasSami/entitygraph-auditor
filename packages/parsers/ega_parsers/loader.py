"""Byte-level document loading with strict size guards.

Handles ``.md``, ``.txt``, ``.html``, ``.htm``, ``.docx`` (pure standard
library: ``zipfile`` + ``xml.etree``) and ``.pdf`` (only when the optional
``pypdf`` dependency is installed — this project does not ship it).

Safety rules for DOCX containers:

* total uncompressed size ≤ 50 MB, no single member > 50 MB;
* compression ratio guard (``file_size > compress_size × 100`` → reject) to
  catch zip bombs before extraction;
* ≤ 5000 paragraphs.

All violations raise :class:`ValueError` with a clear message. Nothing in the
container is ever executed or interpreted beyond XML text extraction.
"""

from __future__ import annotations

import io
import os
import re
import xml.etree.ElementTree as ET
import zipfile

from ega_parsers.normalize import block_normalized
from ega_parsers.result import ParseResult
from ega_parsers.segment import Block

MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_PARAGRAPHS = 5000
MAX_COMPRESSION_RATIO = 100

_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_HEADING_STYLE_RE = re.compile(r"^Heading([1-6])$", re.IGNORECASE)

SUPPORTED_EXTENSIONS = (".md", ".txt", ".html", ".htm", ".docx", ".pdf")

_TEXTUAL_EXTENSIONS = (".md", ".txt", ".html", ".htm")

_DOCX_BODY_NOTES = [
    "DOCX extraction covers body paragraphs only: headers, footers, footnotes, "
    "comments, text boxes and tracked-change deletions are not extracted.",
    "Heading levels in DOCX are inferred from paragraph styles (best effort).",
]


def decode_bytes(data: bytes) -> tuple[str, str | None]:
    """Decode bytes as UTF-8 (BOM-tolerant).

    Returns ``(text, note)`` where *note* explains lossy decoding, if any.
    """
    try:
        return data.decode("utf-8-sig"), None
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace"), (
            "Source bytes were not valid UTF-8; undecodable bytes were "
            "replaced with U+FFFD."
        )


def _block_assembler(raw_text: str) -> ParseResult:
    """Create an empty result whose normalized text grows block-by-block."""
    return ParseResult(raw_text=raw_text, normalized_text="")


def _append_block(result: ParseResult, kind: str, text: str, *, level: int = 0) -> None:
    normalized = block_normalized(text)
    if not normalized:
        return
    if result.normalized_text:
        result.normalized_text += "\n\n"
    start = len(result.normalized_text)
    result.normalized_text += normalized
    block = Block(kind=kind, start=start, end=start + len(normalized))
    if kind == "heading":
        block.level = level
        block.heading_text = normalized
    result.blocks.append(block)


def _zip_guard(zf: zipfile.ZipFile) -> None:
    """Apply the zip-bomb and size guards before reading any member."""
    total = 0
    for info in zf.infolist():
        total += info.file_size
        if info.file_size > MAX_UNCOMPRESSED_BYTES:
            raise ValueError(
                f"DOCX member '{info.filename}' expands to {info.file_size} bytes, "
                f"exceeding the 50 MB limit (possible zip bomb)."
            )
        if info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > MAX_COMPRESSION_RATIO and info.file_size > 64 * 1024:
                raise ValueError(
                    f"DOCX member '{info.filename}' has a compression ratio of "
                    f"{ratio:.0f}:1 (limit {MAX_COMPRESSION_RATIO}:1); refusing to "
                    "extract (possible zip bomb)."
                )
    if total > MAX_UNCOMPRESSED_BYTES:
        raise ValueError(
            f"DOCX container expands to {total} bytes, exceeding the 50 MB "
            "limit (possible zip bomb)."
        )


def _extract_docx(data: bytes) -> ParseResult:
    """Extract paragraphs from ``word/document.xml`` into a ParseResult."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Not a valid DOCX (ZIP) file: {exc}") from exc
    with zf:
        _zip_guard(zf)
        try:
            xml_bytes = zf.read("word/document.xml")
        except KeyError as exc:
            raise ValueError(
                "Not a valid DOCX file: missing word/document.xml."
            ) from exc
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"DOCX word/document.xml is not well-formed XML: {exc}") from exc

    paragraphs = list(root.iter(f"{_WORD_NS}p"))
    if len(paragraphs) > MAX_PARAGRAPHS:
        raise ValueError(
            f"DOCX contains {len(paragraphs)} paragraphs, exceeding the "
            f"{MAX_PARAGRAPHS}-paragraph limit."
        )

    result = _block_assembler(raw_text="")
    for para in paragraphs:
        texts = [node.text or "" for node in para.iter(f"{_WORD_NS}t")]
        text = "".join(texts).strip()
        if not text:
            continue
        level = 0
        style = para.find(f"{_WORD_NS}pPr/{_WORD_NS}pStyle")
        if style is not None:
            value = style.get(f"{_WORD_NS}val") or ""
            heading = _HEADING_STYLE_RE.match(value)
            if heading:
                level = int(heading.group(1))
            elif value.lower() == "title":
                level = 1
        if level:
            _append_block(result, "heading", text, level=level)
        else:
            _append_block(result, "paragraph", text)
    return result


def _extract_pdf(data: bytes) -> ParseResult:
    """Best-effort PDF text extraction (optional dependency ``pypdf``)."""
    try:
        from pypdf import PdfReader  # noqa: PLC0415  (optional dependency)
    except ImportError as exc:
        raise ValueError(
            "PDF extraction requires optional dependency pypdf; not installed"
        ) from exc
    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        if extracted.strip():
            pages.append(extracted)
    text = "\n\n".join(pages)
    from ega_parsers.text_parser import scan_text

    result = scan_text(text)
    result.raw_text = text
    result.notes.append(
        "PDF text extraction is best-effort: layout, tables, images and "
        "reading order may be lost."
    )
    return result


def extract_document(data: bytes, filename: str) -> tuple[str, ParseResult]:
    """Extract ``(original_format, ParseResult)`` from raw file bytes.

    Raises ``ValueError`` for unknown extensions, malformed containers, and
    guard violations — never returns partial silently-truncated content.
    Malformed HTML falls back to plain-text extraction with a recorded note.
    """
    ext = os.path.splitext(filename or "")[1].lower()

    if ext in _TEXTUAL_EXTENSIONS:
        text, note = decode_bytes(data)
        if ext == ".html" or ext == ".htm":
            from ega_parsers.guards import guarded_scan
            from ega_parsers.html_parser import scan_html

            # Malformed HTML must not escape byte loading: the guarded scan
            # falls back to plain text with an explicit note.
            result = guarded_scan(scan_html, text, "HTML")
            original_format = "html"
        elif ext == ".md":
            from ega_parsers.guards import guarded_scan
            from ega_parsers.markdown_parser import scan_markdown

            result = guarded_scan(scan_markdown, text, "Markdown")
            original_format = "markdown"
        else:
            from ega_parsers.guards import guarded_scan
            from ega_parsers.text_parser import scan_text

            result = guarded_scan(scan_text, text, "Plain-text")
            original_format = "text"
        result.raw_text = text
        if note:
            result.notes.append(note)
        return original_format, result

    if ext == ".docx":
        result = _extract_docx(data)
        # The extracted text is the honest raw text for DOCX (the input is a
        # binary container with no user-facing source string).
        result.raw_text = result.normalized_text
        result.notes.extend(_DOCX_BODY_NOTES)
        return "docx", result

    if ext == ".pdf":
        result = _extract_pdf(data)
        return "pdf", result

    raise ValueError(
        f"Unsupported file extension {ext!r} for {filename!r}; supported: "
        + ", ".join(SUPPORTED_EXTENSIONS)
    )
