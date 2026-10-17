"""Structure builder: blocks → headings, sections, passages, tables, lists.

Format parsers (Markdown, plain text, HTML, DOCX) each produce a normalized
text plus an ordered list of :class:`Block` records whose ``start``/``end``
offsets already point into that normalized text. This module turns them into
the deterministic document skeleton:

* headings ``h-001..`` in document order;
* sections ``sec-000`` (preamble) then ``sec-001..`` — a section starts at a
  heading and ends just before the next heading of *any* level;
* passages ``p-0001..`` in document order with the hard invariant
  ``normalized_text[start:end] == text`` (the passage text **is** the slice);
* table and list groupings.

Every ID depends only on the normalized input, so identical inputs always
produce identical structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ega_parsers.stats import count_words

PassageKind = Literal["paragraph", "list_item", "table_row", "definition", "heading", "code"]


@dataclass
class Block:
    """A span of normalized text classified by the format parser."""

    kind: PassageKind
    start: int
    end: int
    level: int = 0
    heading_text: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class HeadingData:
    """Plain heading record prior to Pydantic assembly."""

    id: str
    level: int
    text: str
    offset: int
    parent_id: str = ""
    children: list[str] = field(default_factory=list)


@dataclass
class PassageData:
    """Plain passage record; ``text`` is exactly ``normalized[start:end]``."""

    passage_id: str
    section_id: str
    text: str
    word_count: int
    start_offset: int
    end_offset: int
    kind: PassageKind


@dataclass
class SectionData:
    """Plain section record."""

    section_id: str
    heading: HeadingData | None
    passages: list[PassageData]
    raw_text: str
    word_count: int
    level: int = 0
    parent_section_id: str = ""
    children_section_ids: list[str] = field(default_factory=list)


@dataclass
class TableData:
    """Plain table record (rows as cell strings)."""

    section_id: str
    rows: list[list[str]]
    start_offset: int
    end_offset: int


@dataclass
class ListData:
    """Plain list record; ``items`` are the exact item passage texts."""

    section_id: str
    ordered: bool
    items: list[str]
    start_offset: int
    end_offset: int


@dataclass
class Structure:
    """Everything the assembled document exposes about its shape."""

    headings: list[HeadingData]
    sections: list[SectionData]
    passages: list[PassageData]
    tables: list[TableData]
    lists: list[ListData]


def _heading_id(index: int) -> str:
    return f"h-{index:03d}"


def _section_id(index: int) -> str:
    return f"sec-{index:03d}"


def _passage_id(index: int) -> str:
    return f"p-{index:04d}"


def build_structure(normalized_text: str, blocks: list[Block]) -> Structure:
    """Group classified blocks into the deterministic document skeleton.

    Blocks must be sorted by ``start`` (the parsers emit them in document
    order). Heading blocks drive section boundaries; every other block becomes
    a passage whose text is the verbatim slice of *normalized_text*.
    """
    ordered_blocks = sorted(blocks, key=lambda b: (b.start, b.end))
    heading_blocks = [b for b in ordered_blocks if b.kind == "heading"]

    # --- headings: stable ids, parent = nearest preceding heading with smaller level
    headings: list[HeadingData] = []
    for i, hb in enumerate(heading_blocks, start=1):
        headings.append(
            HeadingData(
                id=_heading_id(i),
                level=hb.level,
                text=hb.heading_text,
                offset=hb.start,
            )
        )
    stack: list[int] = []  # indices into headings
    for idx, heading in enumerate(headings):
        while stack and headings[stack[-1]].level >= heading.level:
            stack.pop()
        if stack:
            parent = headings[stack[-1]]
            heading.parent_id = parent.id
            parent.children.append(heading.id)
        stack.append(idx)

    # --- sections: sec-000 preamble + one per heading (boundary = next heading)
    section_bounds: list[tuple[str, HeadingData | None, int, int]] = []
    first_heading_start = heading_blocks[0].start if heading_blocks else len(normalized_text)
    has_preamble_content = any(
        b.kind != "heading" and not b.meta.get("separator") and b.start < first_heading_start
        for b in ordered_blocks
    )
    if has_preamble_content:
        section_bounds.append((_section_id(0), None, 0, first_heading_start))
    for i, hb in enumerate(heading_blocks):
        end = heading_blocks[i + 1].start if i + 1 < len(heading_blocks) else len(normalized_text)
        section_bounds.append((_section_id(i + 1), headings[i], hb.start, end))

    # Section-level parent/children: nearest preceding section with smaller level.
    sections: list[SectionData] = []
    section_index_by_heading_id: dict[str, int] = {}
    for sec_idx, (sid, heading, start, end) in enumerate(section_bounds):
        raw = normalized_text[start:end]
        section = SectionData(
            section_id=sid,
            heading=heading,
            passages=[],
            raw_text=raw,
            word_count=count_words(raw),
            level=heading.level if heading else 0,
        )
        # Attach passages inside this span.
        for block in ordered_blocks:
            if block.kind == "heading" or block.start < start or block.start >= end:
                continue
            if block.meta.get("separator"):
                continue  # markdown table delimiter row: structure, not content
            text = normalized_text[block.start : block.end]
            if not text.strip():
                continue
            kind: PassageKind = "paragraph" if block.kind == "code" else block.kind  # type: ignore[assignment]
            passage = PassageData(
                passage_id="",  # assigned below, in document order
                section_id=sid,
                text=text,
                word_count=count_words(text),
                start_offset=block.start,
                end_offset=block.end,
                kind=kind,
            )
            section.passages.append(passage)
        if heading is not None:
            section_index_by_heading_id[heading.id] = sec_idx
        sections.append(section)

    # Resolve section-level parents/children (skip the preamble: level 0).
    sec_stack: list[int] = []
    for idx, section in enumerate(sections):
        if section.heading is None:
            continue
        while sec_stack and sections[sec_stack[-1]].level >= section.level:
            sec_stack.pop()
        if sec_stack:
            parent = sections[sec_stack[-1]]
            section.parent_section_id = parent.section_id
            parent.children_section_ids.append(section.section_id)
        sec_stack.append(idx)

    # --- passages: global document order → stable p-NNNN ids
    passages: list[PassageData] = []
    for section in sections:
        for passage in section.passages:
            passages.append(passage)
    passages.sort(key=lambda p: p.start_offset)
    for i, passage in enumerate(passages, start=1):
        passage.passage_id = _passage_id(i)

    # --- tables: contiguous runs of table_row blocks
    tables: list[TableData] = []
    section_of = _make_section_lookup(section_bounds)
    run: list[Block] = []

    def flush_table() -> None:
        if not run:
            return
        start, end = run[0].start, run[-1].end
        tables.append(
            TableData(
                section_id=section_of(start),
                rows=[list(b.meta.get("cells", [])) for b in run if not b.meta.get("separator")],
                start_offset=start,
                end_offset=end,
            )
        )
        run.clear()

    prev_start = -1
    for block in ordered_blocks:
        if block.kind == "table_row":
            run.append(block)
            prev_start = block.end
        else:
            if block.start >= prev_start:
                flush_table()
    flush_table()

    # --- lists: runs of list_item blocks (blank gaps do not break a list,
    #     any non list-item block does)
    lists: list[ListData] = []
    item_run: list[Block] = []

    def flush_list() -> None:
        if not item_run:
            return
        start, end = item_run[0].start, item_run[-1].end
        lists.append(
            ListData(
                section_id=section_of(start),
                ordered=bool(item_run[0].meta.get("ordered", False)),
                items=[normalized_text[b.start : b.end] for b in item_run],
                start_offset=start,
                end_offset=end,
            )
        )
        item_run.clear()

    last_consumed = -1
    for block in ordered_blocks:
        if block.meta.get("separator"):
            continue  # table delimiter rows never break or join lists
        if block.kind == "list_item":
            if item_run and (
                bool(block.meta.get("ordered")) != bool(item_run[0].meta.get("ordered"))
                or _gap_has_other_content(ordered_blocks, last_consumed, block.start)
            ):
                flush_list()
            item_run.append(block)
            last_consumed = block.end
        else:
            if item_run and block.start >= last_consumed:
                flush_list()
    flush_list()

    return Structure(
        headings=headings,
        sections=sections,
        passages=passages,
        tables=tables,
        lists=lists,
    )


def _make_section_lookup(
    section_bounds: list[tuple[str, HeadingData | None, int, int]]
) -> callable:
    """Return ``fn(offset) -> section_id`` for an arbitrary document offset."""

    def lookup(offset: int) -> str:
        for sid, _heading, start, end in section_bounds:
            if start <= offset < end:
                return sid
        # Past-the-end offsets fall into the last section.
        return section_bounds[-1][0] if section_bounds else _section_id(0)

    return lookup


def _gap_has_other_content(blocks: list[Block], a_end: int, b_start: int) -> bool:
    """True when any non list-item block sits between two list items.

    Headings and table delimiter rows count too: a heading between items
    starts a new section, so the items belong to different lists.
    """
    for block in blocks:
        if block.kind == "list_item":
            continue
        if block.start >= a_end and block.end <= b_start:
            return True
    return False
