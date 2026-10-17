"""Unit tests for byte-level document loading, DOCX safety guards and PDF
optional-dependency behaviour.

DOCX containers are built in-memory with :mod:`zipfile` so the zip-bomb and
size guards can be exercised without shipping fixture binaries.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from ega_parsers import load_document_bytes
from ega_parsers.loader import (
    MAX_PARAGRAPHS,
    decode_bytes,
)
from ega_schemas.content import ContentSourceMeta

_W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _docx_xml(paragraphs: list[str], styles: list[str] | None = None) -> str:
    styles = styles or ["" for _ in paragraphs]
    body = []
    for text, style in zip(paragraphs, styles, strict=False):
        if style:
            style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
        else:
            style_xml = ""
        body.append(f'<w:p>{style_xml}<w:r><w:t>{text}</w:t></w:r></w:p>')
    return f'<?xml version="1.0"?><w:document {_W_NS}><w:body>{"".join(body)}</w:body></w:document>'


def make_docx(paragraphs: list[str], styles: list[str] | None = None) -> bytes:
    """Build a minimal but structurally valid DOCX container in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        zf.writestr("word/document.xml", _docx_xml(paragraphs, styles))
    return buf.getvalue()


# --------------------------------------------------------------------------------------
# plain text formats
# --------------------------------------------------------------------------------------

def test_load_markdown_bytes():
    source = ContentSourceMeta()
    doc = load_document_bytes(b"# Title\n\nBody paragraph.", "page.md", source)
    assert source.original_format == "markdown"
    assert doc.title == "Title"
    assert doc.word_count >= 3


def test_load_html_bytes():
    source = ContentSourceMeta()
    doc = load_document_bytes(
        b"<html><head><title>T</title></head><body><h1>H</h1><p>Body text.</p></body></html>",
        "page.html",
        source,
    )
    assert source.original_format == "html"
    assert doc.title == "T"
    assert doc.metadata["form_count"] == 0


def test_load_txt_bytes_is_plain_text():
    source = ContentSourceMeta()
    doc = load_document_bytes(b"CAPS HEADING\n\nSome body text here.", "page.txt", source)
    assert source.original_format == "text"
    assert [h.text for h in doc.headings] == ["CAPS HEADING"]


def test_load_bom_prefixed_bytes():
    source = ContentSourceMeta()
    doc = load_document_bytes(b"\xef\xbb\xbf# Title\n\nBody.", "page.md", source)
    assert doc.title == "Title"
    assert not any("U+FFFD" in n for n in source.extraction_notes)


def test_invalid_utf8_bytes_are_replaced_and_noted():
    source = ContentSourceMeta()
    load_document_bytes(b"\xff\xfe invalid \x9c bytes", "page.txt", source)
    assert any("U+FFFD" in n for n in source.extraction_notes)


# --------------------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------------------

def test_load_docx_extracts_paragraphs_and_notes():
    source = ContentSourceMeta()
    doc = load_document_bytes(
        make_docx(["First paragraph.", "Second paragraph."]), "doc.docx", source
    )
    assert source.original_format == "docx"
    texts = [p.text for p in doc.passages]
    assert texts == ["First paragraph.", "Second paragraph."]
    assert any("body paragraphs only" in note for note in source.extraction_notes)


def test_docx_heading_styles_become_headings():
    source = ContentSourceMeta()
    doc = load_document_bytes(
        make_docx(["Chapter One", "Some body text."], styles=["Heading1", ""]),
        "doc.docx",
        source,
    )
    assert [h.text for h in doc.headings] == ["Chapter One"]
    assert doc.headings[0].level == 1


def test_docx_too_many_paragraphs_rejected():
    data = make_docx([f"Paragraph {i}" for i in range(MAX_PARAGRAPHS + 1)])
    with pytest.raises(ValueError, match="paragraph limit"):
        load_document_bytes(data, "doc.docx", ContentSourceMeta())


def test_docx_zip_bomb_ratio_rejected():
    """A highly compressible member above the size threshold trips the ratio guard."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        zf.writestr("word/document.xml", _docx_xml(["Hello world"]))
        # 1 MB of zeros compresses to ~1 KB -> ratio ~1000:1 > 100:1 limit.
        zf.writestr("word/embeddings/blob.bin", b"\0" * (1024 * 1024))
    with pytest.raises(ValueError, match="compression ratio"):
        load_document_bytes(buf.getvalue(), "doc.docx", ContentSourceMeta())


def test_docx_missing_document_xml_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
    with pytest.raises(ValueError, match="word/document.xml"):
        load_document_bytes(buf.getvalue(), "doc.docx", ContentSourceMeta())


def test_docx_malformed_xml_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        zf.writestr("word/document.xml", "<w:document><w:body><unclosed>")
    with pytest.raises(ValueError, match="not well-formed"):
        load_document_bytes(buf.getvalue(), "doc.docx", ContentSourceMeta())


def test_not_a_zip_rejected():
    with pytest.raises(ValueError, match="valid DOCX"):
        load_document_bytes(b"this is not a zip archive", "doc.docx", ContentSourceMeta())


# --------------------------------------------------------------------------------------
# guards / dispatch
# --------------------------------------------------------------------------------------

def test_unknown_extension_rejected():
    with pytest.raises(ValueError, match="Unsupported file extension"):
        load_document_bytes(b"anything", "page.xyz", ContentSourceMeta())


def test_pdf_without_pypdf_raises_clear_error():
    import importlib.util

    if importlib.util.find_spec("pypdf") is not None:
        pytest.skip("pypdf installed; optional-dependency error not applicable")
    with pytest.raises(ValueError, match="pypdf"):
        load_document_bytes(b"%PDF-1.4 ...", "page.pdf", ContentSourceMeta())


def test_decode_bytes_reports_lossless_utf8():
    text, note = decode_bytes("héllo — wörld".encode("utf-8"))
    assert text == "héllo — wörld"
    assert note is None


def test_decode_bytes_reports_replacement_for_invalid_utf8():
    text, note = decode_bytes(b"abc\x9cdef")
    assert note is not None
    assert "U+FFFD" in text or "�" in text
