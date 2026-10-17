"""Deterministic structural parser for HTML, Markdown, and plain text."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

from bs4 import BeautifulSoup
from ega_schemas.content import Heading, Link, ParsedDocument, Passage, Section
from ega_schemas.enums import AnswerShape

from ega_parsers.metrics import compute_reading_time_minutes

PRONOUN_STARTS = (
    "it ", "its ", "it's ", "they ", "their ", "them ", "they're ", "this ", "these ",
    "we ", "our ", "us ", "we're ", "he ", "his ", "she ", "her ", "there are ", "there is "
)


def detect_answer_shape(text: str) -> AnswerShape:
    """Classify the stylistic shape of an answer passage."""
    lower = text.lower().strip()
    if re.match(r'^(is|are|refers to|denotes|defined as)\b', lower) or " is defined as " in lower or " refers to " in lower:
        return AnswerShape.DEFINITION
    if re.match(r'^step\s+\d+|^\d+\.\s+', lower) or "first," in lower or "then," in lower:
        return AnswerShape.PROCEDURE
    if "\n- " in text or "\n* " in text or "checklist" in lower:
        return AnswerShape.CHECKLIST
    if " vs " in lower or "compared to" in lower or "whereas" in lower:
        return AnswerShape.COMPARISON_VERDICT
    if "$" in text or "€" in text or "£" in text or "pricing" in lower or "cost" in lower or "/month" in lower:
        return AnswerShape.PRICING_FACT
    if "risk" in lower or "danger" in lower or "warning" in lower or "caution" in lower:
        return AnswerShape.RISK_EXPLANATION
    if "case study" in lower or "results" in lower or "metric" in lower or "%" in text:
        return AnswerShape.PROOF_BLOCK
    if "contact us" in lower or "get started" in lower or "sign up" in lower or "book a call" in lower:
        return AnswerShape.CTA
    return AnswerShape.DEFINITION


def analyze_passage_retrievability(text: str) -> tuple[bool, bool, list[str]]:
    """Determine whether passage is named-subject anchor and answer-first."""
    issues: list[str] = []
    lower = text.strip().lower()
    
    # Check named subject
    has_pronoun_start = any(lower.startswith(p) for p in PRONOUN_STARTS)
    named_subject = not has_pronoun_start
    if has_pronoun_start:
        issues.append("Passage opens with ambiguous pronoun or deictic reference instead of named entity anchor.")

    # Check answer first (concise, direct predicate assertion in first sentence)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    first_sentence = sentences[0] if sentences else text
    
    answer_first = False
    if len(first_sentence.split()) <= 35 and any(verb in first_sentence.lower() for verb in [" is ", " are ", " provides ", " delivers ", " means ", " includes ", " costs ", " enables "]):
        answer_first = True
    elif len(first_sentence.split()) > 40:
        issues.append("First sentence is verbose or preamble-heavy before answering the intent.")

    return named_subject, answer_first, issues


class DocumentParser:
    """Parser that converts HTML, Markdown, or raw text into a ParsedDocument."""

    @classmethod
    def parse(
        cls,
        content: str,
        default_title: Optional[str] = None,
        content_format: Optional[str] = None,
        source: Optional[Any] = None,
        **kwargs: Any,
    ) -> ParsedDocument:
        """Parse raw content into normalized sections, headings, passages, and links."""
        content = content.strip() if content else ""
        if not content:
            return ParsedDocument(
                raw_text="",
                original_text="",
                normalized_text="",
                title=default_title,
                content_hash=hashlib.sha256(b"").hexdigest(),
            )

        # Detect HTML
        is_html = bool(re.search(r'<(!DOCTYPE|html|head|body|div|p|h[1-6]|ul|li|section|article)\b', content, re.IGNORECASE))

        if is_html:
            return cls._parse_html(content, default_title)
        return cls._parse_markdown_or_text(content, default_title)

    @classmethod
    def _parse_html(cls, html_content: str, default_title: Optional[str] = None) -> ParsedDocument:
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract title
        title = default_title
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.string.strip()

        # Remove script, style, meta, nav, footer chrome
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        # Extract links
        links: list[Link] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            anchor_text = a.get_text(strip=True)
            if href and anchor_text:
                is_internal = href.startswith("/") or not href.startswith("http")
                is_anchor = href.startswith("#")
                links.append(Link(url=href, anchor_text=anchor_text, is_internal=is_internal, is_anchor=is_anchor))

        # Structural parsing: headings and passages
        body = soup.find("body") or soup
        headings: list[Heading] = []
        sections: list[Section] = []
        all_passages: list[Passage] = []

        current_heading: Optional[Heading] = None
        current_passages: list[Passage] = []
        current_section_id = "sec-0"
        passage_counter = 1
        current_offset = 0
        normalized_parts: list[str] = []

        # Iterate over block elements
        block_tags = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"]
        for element in body.find_all(block_tags):
            tag_name = element.name.lower()
            text = element.get_text(separator=" ", strip=True)
            if not text:
                continue

            if tag_name.startswith("h") and len(tag_name) == 2 and tag_name[1].isdigit():
                # Flush previous section if it has content
                if current_passages or current_heading:
                    raw_sec = "\n\n".join(p.text for p in current_passages)
                    sections.append(Section(
                        section_id=current_section_id,
                        heading=current_heading,
                        passages=current_passages,
                        raw_text=raw_sec,
                        word_count=len(raw_sec.split()),
                    ))
                    current_passages = []

                level = int(tag_name[1])
                h_id = f"h-{len(headings) + 1}"
                current_heading = Heading(level=level, text=text, id=h_id, offset=current_offset)
                headings.append(current_heading)
                current_section_id = f"sec-{len(headings)}"
                normalized_parts.append(f"{'#' * level} {text}")
                current_offset += len(text) + 2
                if not title and level == 1:
                    title = text
            else:
                # Passage
                p_id = f"p-{passage_counter:04d}"
                passage_counter += 1
                words = len(text.split())
                start_off = current_offset
                end_off = current_offset + len(text)
                current_offset = end_off + 2
                normalized_parts.append(text)

                named_sub, ans_first, issues = analyze_passage_retrievability(text)
                shape = detect_answer_shape(text)

                passage = Passage(
                    passage_id=p_id,
                    section_id=current_section_id,
                    text=text,
                    word_count=words,
                    start_offset=start_off,
                    end_offset=end_off,
                    named_subject=named_sub,
                    answer_first=ans_first,
                    answer_shape=shape,
                    issues=issues,
                )
                current_passages.append(passage)
                all_passages.append(passage)

        # Flush final section
        if current_passages or current_heading:
            raw_sec = "\n\n".join(p.text for p in current_passages)
            sections.append(Section(
                section_id=current_section_id,
                heading=current_heading,
                passages=current_passages,
                raw_text=raw_sec,
                word_count=len(raw_sec.split()),
            ))

        normalized_text = "\n\n".join(normalized_parts)
        words_total = len(normalized_text.split())
        content_hash = hashlib.sha256(html_content.encode("utf-8")).hexdigest()

        return ParsedDocument(
            raw_text=html_content,
            original_text=html_content,
            normalized_text=normalized_text,
            title=title,
            sections=sections,
            passages=all_passages,
            headings=headings,
            links=links,
            word_count=words_total,
            char_count=len(normalized_text),
            reading_time_minutes=compute_reading_time_minutes(words_total),
            content_hash=content_hash,
        )

    @classmethod
    def _parse_markdown_or_text(cls, text: str, default_title: Optional[str] = None) -> ParsedDocument:
        lines = text.split("\n")
        headings: list[Heading] = []
        sections: list[Section] = []
        all_passages: list[Passage] = []
        links: list[Link] = []

        title = default_title
        current_heading: Optional[Heading] = None
        current_passages: list[Passage] = []
        current_section_id = "sec-0"
        passage_counter = 1
        current_offset = 0
        normalized_parts: list[str] = []

        # Extract markdown links [text](url)
        for match in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', text):
            anchor = match.group(1).strip()
            url = match.group(2).strip()
            is_internal = url.startswith("/") or not url.startswith("http")
            is_anchor = url.startswith("#")
            links.append(Link(url=url, anchor_text=anchor, is_internal=is_internal, is_anchor=is_anchor))

        # Chunk lines into paragraphs or headings
        paragraphs: list[tuple[str, bool, int]] = []  # (text, is_heading, level)
        buffer: list[str] = []

        for line in lines:
            stripped = line.strip()
            heading_match = re.match(r'^(#{1,6})\s+(.*)$', stripped)
            if heading_match:
                if buffer:
                    paragraphs.append(("\n".join(buffer), False, 0))
                    buffer = []
                level = len(heading_match.group(1))
                h_text = heading_match.group(2).strip()
                paragraphs.append((h_text, True, level))
            elif not stripped:
                if buffer:
                    paragraphs.append(("\n".join(buffer), False, 0))
                    buffer = []
            else:
                buffer.append(stripped)

        if buffer:
            paragraphs.append(("\n".join(buffer), False, 0))

        for p_text, is_h, h_lvl in paragraphs:
            if is_h:
                if current_passages or current_heading:
                    raw_sec = "\n\n".join(p.text for p in current_passages)
                    sections.append(Section(
                        section_id=current_section_id,
                        heading=current_heading,
                        passages=current_passages,
                        raw_text=raw_sec,
                        word_count=len(raw_sec.split()),
                    ))
                    current_passages = []

                h_id = f"h-{len(headings) + 1}"
                current_heading = Heading(level=h_lvl, text=p_text, id=h_id, offset=current_offset)
                headings.append(current_heading)
                current_section_id = f"sec-{len(headings)}"
                normalized_parts.append(f"{'#' * h_lvl} {p_text}")
                current_offset += len(p_text) + 2
                if (not title or title == default_title) and h_lvl == 1:
                    title = p_text
            else:
                p_id = f"p-{passage_counter:04d}"
                passage_counter += 1
                words = len(p_text.split())
                start_off = current_offset
                end_off = current_offset + len(p_text)
                current_offset = end_off + 2
                normalized_parts.append(p_text)

                named_sub, ans_first, issues = analyze_passage_retrievability(p_text)
                shape = detect_answer_shape(p_text)

                passage = Passage(
                    passage_id=p_id,
                    section_id=current_section_id,
                    text=p_text,
                    word_count=words,
                    start_offset=start_off,
                    end_offset=end_off,
                    named_subject=named_sub,
                    answer_first=ans_first,
                    answer_shape=shape,
                    issues=issues,
                )
                current_passages.append(passage)
                all_passages.append(passage)

        if current_passages or current_heading:
            raw_sec = "\n\n".join(p.text for p in current_passages)
            sections.append(Section(
                section_id=current_section_id,
                heading=current_heading,
                passages=current_passages,
                raw_text=raw_sec,
                word_count=len(raw_sec.split()),
            ))

        normalized_text = "\n\n".join(normalized_parts)
        words_total = len(normalized_text.split())
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        return ParsedDocument(
            raw_text=text,
            original_text=text,
            normalized_text=normalized_text,
            title=title,
            sections=sections,
            passages=all_passages,
            headings=headings,
            links=links,
            word_count=words_total,
            char_count=len(normalized_text),
            reading_time_minutes=compute_reading_time_minutes(words_total),
            content_hash=content_hash,
        )
