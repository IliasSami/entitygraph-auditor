"""Unit tests for the ``ega_parsers`` public API and assembly invariants.

These test the deterministic contract of ``parse_markdown`` / ``parse_html`` /
``parse_text`` / ``parse_content``: exact character-offset slices, stable IDs,
text statistics, honest extraction flags and the security-relevant link model.
The legacy :class:`ega_parsers.DocumentParser` facade is covered separately in
``test_parsers.py``.
"""

from __future__ import annotations

import pytest
from ega_parsers import parse_content, parse_html, parse_text
from ega_schemas.content import ContentSourceMeta


def _doc(text: str, fmt: str = "markdown", **kwargs):
    source = ContentSourceMeta()
    doc = parse_content(text, content_format=fmt, source=source, **kwargs)
    return doc, source


MD_SAMPLE = """# Acme Platform

Acme Platform is a workflow tool for small teams.

## Features

- Fast onboarding
- Secure by default
- Works offline

## Pricing

| Plan | Monthly | Seats |
| --- | --- | --- |
| Free | $0 | 3 |
| Pro | $12 | 25 |

See [our pricing](/pricing) or [contact sales](https://acme.example/contact).
"""


# --------------------------------------------------------------------------------------
# offset + structure invariants
# --------------------------------------------------------------------------------------

def test_passage_offsets_are_exact_slices():
    doc, _ = _doc(MD_SAMPLE)
    assert doc.passages, "expected passages"
    for passage in doc.passages:
        assert doc.normalized_text[passage.start_offset : passage.end_offset] == passage.text
        assert passage.end_offset > passage.start_offset


def test_heading_offsets_point_at_heading_text():
    doc, _ = _doc(MD_SAMPLE)
    assert [h.text for h in doc.headings] == ["Acme Platform", "Features", "Pricing"]
    assert [h.level for h in doc.headings] == [1, 2, 2]
    for heading in doc.headings:
        # The offset points at the start of the heading *block* in the
        # normalized text (which keeps the Markdown ``#`` marker), so the
        # heading text begins within the marker characters after the offset.
        window = doc.normalized_text[heading.offset : heading.offset + heading.level + 1 + len(heading.text)]
        assert window.endswith(heading.text)


def test_stable_sequential_ids():
    doc, _ = _doc(MD_SAMPLE)
    assert [h.id for h in doc.headings] == ["h-001", "h-002", "h-003"]
    assert [p.passage_id for p in doc.passages] == [
        f"p-{i:04d}" for i in range(1, len(doc.passages) + 1)
    ]
    assert [s.section_id for s in doc.sections] == ["sec-001", "sec-002", "sec-003"]


def test_preamble_section_only_when_content_precedes_first_heading():
    doc, _ = _doc("Intro paragraph before any heading.\n\n# Title\n\nBody.")
    assert doc.sections[0].section_id == "sec-000"
    assert doc.sections[0].heading is None

    doc2, _ = _doc("# Title\n\nBody only.")
    assert doc2.sections[0].section_id == "sec-001"


def test_every_passage_belongs_to_a_section():
    doc, _ = _doc(MD_SAMPLE)
    section_ids = {s.section_id for s in doc.sections}
    assert all(p.section_id in section_ids for p in doc.passages)
    # passages are also embedded in their sections, in document order
    flat = [p.passage_id for s in doc.sections for p in s.passages]
    assert flat == sorted(flat)


def test_tables_and_lists_extracted_with_spans():
    doc, _ = _doc(MD_SAMPLE)
    assert len(doc.tables) == 1
    table = doc.tables[0]
    assert table["rows"][0] == ["Plan", "Monthly", "Seats"]
    assert ["Pro", "$12", "25"] in table["rows"]
    # the separator row must not appear as a passage
    assert not any(set(p.text) <= {"-", "|", " ", ":"} for p in doc.passages)

    assert len(doc.lists) == 1
    assert doc.lists[0]["ordered"] is False
    assert doc.lists[0]["items"] == ["- Fast onboarding", "- Secure by default", "- Works offline"]


def test_ordered_list_marked_ordered():
    doc, _ = _doc("1. First\n2. Second\n3. Third")
    assert doc.lists and doc.lists[0]["ordered"] is True
    assert doc.lists[0]["items"] == ["1. First", "2. Second", "3. Third"]


# --------------------------------------------------------------------------------------
# extraction-quality flags
# --------------------------------------------------------------------------------------

def test_empty_page_flags_extraction_loss():
    doc, source = _doc("tiny")
    assert source.extraction_loss == 1.0
    assert any("near-empty" in n for n in source.extraction_notes)
    assert doc.word_count == 1


def test_duplicate_paragraphs_flagged():
    para = "This is a duplicated paragraph used to test the duplicate ratio signal."
    doc, source = _doc(f"{para}\n\n{para}\n\nSomething unique here.")
    assert doc.text_stats["duplicate_paragraph_ratio"] > 0.0
    assert any("Duplicate content" in n for n in source.extraction_notes)


def test_language_and_readability_are_recorded():
    doc, _ = _doc(
        "The quick brown fox jumps over the lazy dog. It runs fast through the field every day."
    )
    assert doc.text_stats["language"] == "en"
    assert doc.text_stats["flesch_reading_ease"] is not None
    assert doc.text_stats["flesch_kincaid_grade"] is not None


def test_non_english_readability_is_not_forced_to_english_formula():
    french = (
        "Le service est simple et rapide pour toutes les petites équipes. "
        "Nous vous aidons à démarrer en quelques minutes avec un guide clair."
    )
    doc, _ = _doc(french, language_hint="fr")
    stats = doc.text_stats
    assert stats["language"] == "fr"
    assert stats["flesch_kincaid_grade"] is None
    assert stats["readability_warning"]


def test_unknown_language_readability_is_withheld():
    # Bengali script: neither English nor French formula is valid.
    bengali = "এটি একটি পরীক্ষামূলক বাক্য যা ভাষা সনাক্তকরণ যাচাই করে। " * 4
    doc, _ = _doc(bengali)
    stats = doc.text_stats
    assert stats["language"] == "bn"
    assert stats["flesch_reading_ease"] is None
    assert stats["flesch_kincaid_grade"] is None
    assert stats["readability_warning"]


def test_normalized_text_is_idempotent_with_content_hash():
    doc, _ = _doc(MD_SAMPLE)
    assert doc.content_hash.startswith("sha256:")
    assert doc.original_text == doc.raw_text
    # char/word counts describe the normalized text
    assert doc.char_count == len(doc.normalized_text)
    assert doc.word_count > 0
    assert doc.reading_time_minutes >= 0.0


# --------------------------------------------------------------------------------------
# links
# --------------------------------------------------------------------------------------

def test_relative_links_are_internal_without_base_url():
    doc, source = _doc("[Pricing](/pricing) and [#faq](#faq) and [ext](https://other.test/x)")
    by_url = {link.url: link for link in doc.links}
    assert by_url["/pricing"].is_internal is True
    assert by_url["#faq"].is_internal is True
    assert by_url["#faq"].is_anchor is True
    assert by_url["https://other.test/x"].is_internal is False
    # the unresolved-absolute-links limitation is recorded
    assert any("No base_url" in note for note in source.limitations)


def test_absolute_links_resolved_against_base_url():
    doc, _ = _doc(
        "[a](pricing) [b](https://acme.example/about) [c](https://elsewhere.example)", 
        base_url="https://acme.example/blog/post",
    )
    by_url = {link.url: link for link in doc.links}
    assert by_url["https://acme.example/blog/pricing"].is_internal is True
    assert by_url["https://acme.example/about"].is_internal is True
    assert by_url["https://elsewhere.example"].is_internal is False


def test_link_rel_preserved_in_metadata():
    html = '<html><body><a href="/a" rel="nofollow sponsored">A</a></body></html>'
    doc = parse_html(html, ContentSourceMeta(), base_url="https://acme.example/")
    assert doc.metadata["link_rels"] == [{"url": "https://acme.example/a", "rel": "nofollow sponsored"}]


# --------------------------------------------------------------------------------------
# html specifics
# --------------------------------------------------------------------------------------

def test_html_metadata_and_json_ld():
    html = """<!doctype html><html lang="en"><head>
    <title>Acme Pricing</title>
    <meta name="description" content="Simple pricing for teams">
    <meta name="robots" content="noindex, nofollow">
    <link rel="canonical" href="https://acme.example/pricing">
    <script type="application/ld+json">{"@type": "Product"}</script>
    </head><body><h1>Pricing</h1><p>Simple plans.</p></body></html>"""
    doc = parse_html(html, ContentSourceMeta())
    meta = doc.metadata
    assert doc.title == "Acme Pricing"
    assert meta["description"] == "Simple pricing for teams"
    assert meta["canonical"] == "https://acme.example/pricing"
    assert meta["lang"] == "en"
    assert meta["robots_noindex"] is True
    assert meta["json_ld"] == ['{"@type": "Product"}']


def test_html_script_style_nav_excluded_from_passages():
    html = """<html><body>
    <nav>Home About Contact</nav>
    <script>var x = 'leak';</script>
    <style>.leak { color: red; }</style>
    <p>Real visible content only.</p>
    </body></html>"""
    doc = parse_html(html, ContentSourceMeta())
    assert [p.text for p in doc.passages] == ["Real visible content only."]


def test_html_first_h1_becomes_title_when_no_title_tag():
    doc = parse_html("<body><h1>Fallback Heading</h1><p>x</p></body>", ContentSourceMeta())
    assert doc.title == "Fallback Heading"


def test_html_form_and_code_counts_recorded():
    html = "<html><body><form></form><pre>code()</pre><p>text</p></body></html>"
    doc = parse_html(html, ContentSourceMeta())
    assert doc.metadata["form_count"] == 1
    assert doc.metadata["code_block_count"] == 1


# --------------------------------------------------------------------------------------
# plain text
# --------------------------------------------------------------------------------------

def test_plain_text_detects_only_explicit_headings():
    text = "THIS IS A HEADING\n\nBody paragraph here.\n\n# Markdown Style\n\nMore body."
    doc = parse_text(text, ContentSourceMeta())
    assert [h.text for h in doc.headings] == ["THIS IS A HEADING", "Markdown Style"]


def test_plain_text_ordinary_sentence_not_a_heading():
    text = "This sentence is long enough to be a normal paragraph and not a caps heading."
    doc = parse_text(text, ContentSourceMeta())
    assert doc.headings == []
    assert len(doc.passages) == 1


# --------------------------------------------------------------------------------------
# dispatch + guards
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("fmt", ["markdown", "md", "html", "text"])
def test_parse_content_dispatch(fmt):
    doc, _ = _doc("# Hello\n\nWorld paragraph.", fmt=fmt)
    assert doc.word_count >= 2


def test_parse_content_unknown_format_raises():
    with pytest.raises(ValueError, match="Unknown content_format"):
        parse_content("x", content_format="rst", source=ContentSourceMeta())


def test_malformed_html_falls_back_to_text(monkeypatch):
    from ega_parsers import api

    def boom(_html):
        raise RuntimeError("simulated soup failure")

    monkeypatch.setattr(api, "scan_html", boom)
    source = ContentSourceMeta()
    doc = api.parse_html("<html><body><p>Still text.</p></body></html>", source)
    assert source.extraction_loss == 1.0
    assert any("fell back to plain-text" in note for note in source.extraction_notes)
    assert any("could not be extracted reliably" in lim for lim in source.limitations)
    assert "Still text." in doc.normalized_text


def test_parse_markdown_does_not_mutate_shared_defaults():
    # Two parses must not leak state through shared mutable defaults.
    doc1, src1 = _doc("# One\n\nBody one.")
    doc2, src2 = _doc("# Two\n\nBody two.")
    assert doc1.suggested_page_type is not None and doc2.suggested_page_type is not None
    assert "Body one" in doc1.normalized_text and "Body one" not in doc2.normalized_text
    assert src1 is not src2
