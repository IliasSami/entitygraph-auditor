"""Markdown parser (CommonMark-flavoured subset, fully deterministic).

Supported constructs: ATX headings (``#``–``######``), setext headings
(``===``/``---`` under a paragraph), fenced code blocks, bullet/ordered list
items with indented continuation lines, GFM pipe tables (with separator rows
excluded from content), pandoc-style definition lines (``: definition``),
YAML front matter (skipped; ``title:`` picked up as the document title),
inline/reference links and autolinks.

Anything not recognised stays verbatim paragraph text — passage text is always
the exact slice of the normalized document, so nothing is rewritten.
"""

from __future__ import annotations

import re

from ega_parsers.normalize import normalize_text
from ega_parsers.result import ParseResult, RawLink
from ega_parsers.segment import Block

_ATX_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*)$")
_SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_LIST_RE = re.compile(r"^( {0,3})([-*+]|\d{1,9}[.)])([ \t]+)(.*)$")
_DEF_RE = re.compile(r"^ {0,3}:[ \t]+(.*)$")
_REFDEF_RE = re.compile(r"^ {0,3}\[[^\]]+\]:[ \t]+\S+")
_FRONTMATTER_TITLE_RE = re.compile(r"^title:[ \t]*(.+)$", re.IGNORECASE)

_LINK_RE = re.compile(
    r"(?P<bang>!)?\[(?P<text>[^\[\]]*)\]\([ \t]*(?P<url><?[^)\s>]+>?)(?:[ \t]+\"[^\"]*\")?[ \t]*\)"
)
_AUTOLINK_RE = re.compile(r"<(?P<url>https?://[^>\s]+)>")
_REF_LINK_RE = re.compile(r"\[(?P<text>[^\[\]]+)\]\[[^\[\]]*\]")

_CODESPAN_RE = re.compile(r"`([^`]*)`")
_IMAGE_RE = re.compile(r"!\[([^\[\]]*)\]\([^)]*\)")
_INLINE_LINK_RE = re.compile(r"\[([^\[\]]*)\]\([^)]*\)")
_BOLD_RE = re.compile(r"(\*\*|__)(.+?)\1", re.DOTALL)
_ITALIC_RE = re.compile(r"(?<![*\w])\*([^*\s][^*]*)\*(?![*\w])")

_SEPARATOR_CELL_RE = re.compile(r":?-+:?")


def clean_inline_markdown(text: str) -> str:
    """Reduce inline Markdown markup to its visible text.

    Used for heading text, table cells and titles — never for passage text
    (passages keep the exact slice).
    """
    out = _IMAGE_RE.sub(r"\1", text)
    out = _INLINE_LINK_RE.sub(r"\1", out)
    out = _REF_LINK_RE.sub(r"\1", out)
    out = _CODESPAN_RE.sub(r"\1", out)
    out = _BOLD_RE.sub(r"\2", out)
    out = _ITALIC_RE.sub(r"\1", out)
    return out.strip()


def _split_cells(line: str) -> list[str]:
    """Split a pipe-table row into cell strings (edge empties dropped)."""
    cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)]
    while cells and cells[0] == "":
        cells.pop(0)
    while cells and cells[-1] == "":
        cells.pop()
    return [clean_inline_markdown(c) for c in cells]


def _is_separator_row(line: str) -> bool:
    """True for a GFM table delimiter row such as ``|---|:--|``."""
    if "|" not in line:
        return False
    cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)]
    while cells and cells[0] == "":
        cells.pop(0)
    while cells and cells[-1] == "":
        cells.pop()
    if not cells:
        return False
    return all(_SEPARATOR_CELL_RE.fullmatch(c) for c in cells)


def _extract_links(text: str) -> list[RawLink]:
    """Inline links, reference links with a target, and http(s) autolinks."""
    found: list[RawLink] = []
    for match in _LINK_RE.finditer(text):
        if match.group("bang"):
            continue  # images are not links
        url = match.group("url").strip("<>")
        found.append(
            RawLink(
                url=url,
                anchor_text=clean_inline_markdown(match.group("text")),
                is_anchor=url.startswith("#"),
            )
        )
    for match in _AUTOLINK_RE.finditer(text):
        url = match.group("url")
        found.append(RawLink(url=url, anchor_text=url, is_anchor=False))
    return found


def scan_markdown(text: str) -> ParseResult:
    """Parse *text* as Markdown into a pre-assembly :class:`ParseResult`."""
    normalized = normalize_text(text)
    result = ParseResult(raw_text=text, normalized_text=normalized)

    lines = normalized.split("\n")
    starts: list[int] = []
    pos = 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1

    def line_end(i: int) -> int:
        return starts[i] + len(lines[i])

    # --- YAML front matter: skip it, harvest an explicit title -------------
    skip_until = -1
    if lines and lines[0] == "---":
        for j in range(1, len(lines)):
            if lines[j] == "---":
                skip_until = j
                for inner in lines[1:j]:
                    m = _FRONTMATTER_TITLE_RE.match(inner.strip())
                    if m:
                        result.title = m.group(1).strip().strip("\"'")
                break
        if skip_until == -1:
            skip_until = -1  # no closing delimiter -> not front matter

    i = 0
    para_start = -1  # offset of the running TEXT paragraph
    para_end = -1  # exclusive end of the running paragraph
    para_lines: list[str] = []
    fence: tuple[str, int, int] | None = None  # (char, length, start offset)

    def flush_para() -> None:
        nonlocal para_start, para_end
        if para_start >= 0:
            result.blocks.append(
                Block(kind="paragraph", start=para_start, end=para_end)
            )
            para_start = -1
            para_end = -1
            para_lines.clear()

    while i < len(lines):
        line = lines[i]

        if i <= skip_until and skip_until >= 0 and i <= skip_until:
            if i < skip_until:
                flush_para()
                i += 1
                continue

        # --- fenced code ----------------------------------------------------
        fence_match = _FENCE_RE.match(line)
        if fence is not None:
            if fence_match:
                marker = fence_match.group(1)
                if marker[0] == fence[0] and len(marker) >= fence[1] and not fence_match.group(2).strip():
                    result.blocks.append(
                        Block(kind="code", start=fence[2], end=line_end(i))
                    )
                    fence = None
            i += 1
            continue
        if fence_match and not (
            fence_match.group(1)[0] == "`" and "`" in fence_match.group(2)
        ):
            flush_para()
            fence = (fence_match.group(1)[0], len(fence_match.group(1)), starts[i])
            i += 1
            continue

        if not line.strip():
            flush_para()
            i += 1
            continue

        # --- reference-style link definitions: source-only, not content -----
        if _REFDEF_RE.match(line):
            flush_para()
            i += 1
            continue

        # --- ATX headings ----------------------------------------------------
        atx = _ATX_RE.match(line)
        if atx:
            flush_para()
            level = len(atx.group(1))
            heading_text = atx.group(2).rstrip()
            heading_text = re.sub(r"[ \t]+#+[ \t]*$", "", heading_text)
            start = starts[i]
            result.blocks.append(
                Block(
                    kind="heading",
                    start=start,
                    end=line_end(i),
                    level=level,
                    heading_text=clean_inline_markdown(heading_text),
                )
            )
            result.links.extend(_extract_links(line))
            i += 1
            continue

        # --- GFM pipe table (lookahead on the separator row) -----------------
        if "|" in line and i + 1 < len(lines) and _is_separator_row(lines[i + 1]):
            flush_para()
            header_cells = _split_cells(line)
            result.blocks.append(
                Block(
                    kind="table_row",
                    start=starts[i],
                    end=line_end(i),
                    meta={"cells": header_cells},
                )
            )
            result.links.extend(_extract_links(line))
            j = i + 1
            first_row_end = line_end(i)
            while j < len(lines) and "|" in lines[j]:
                separator = _is_separator_row(lines[j])
                cells = [] if separator else _split_cells(lines[j])
                block = Block(
                    kind="table_row",
                    start=starts[j],
                    end=line_end(j),
                    meta={"cells": cells, "separator": separator},
                )
                result.blocks.append(block)
                if not separator:
                    first_row_end = line_end(j)
                    result.links.extend(_extract_links(lines[j]))
                j += 1
            # Trim trailing non-row content is impossible here; all rows carry
            # exact spans, the table span is derived from them downstream.
            del first_row_end
            i = j
            continue

        # --- setext heading: paragraph line(s) followed by ===/--- -----------
        setext = _SETEXT_RE.match(line)
        if setext and para_start >= 0:
            level = 1 if setext.group(1)[0] == "=" else 2
            heading_text = clean_inline_markdown(" ".join(para_lines))
            start, end = para_start, para_end
            para_start = -1
            para_end = -1
            para_lines.clear()
            result.blocks.append(
                Block(
                    kind="heading",
                    start=start,
                    end=end,
                    level=level,
                    heading_text=heading_text,
                )
            )
            i += 1
            continue
        if setext:
            # thematic break or underline without a paragraph -> not content
            flush_para()
            i += 1
            continue

        # --- list item (with indented continuation lines) --------------------
        list_match = _LIST_RE.match(line)
        if list_match:
            flush_para()
            start = starts[i]
            end = line_end(i)
            result.links.extend(_extract_links(line))
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    break
                if _LIST_RE.match(nxt) or _ATX_RE.match(nxt) or _FENCE_RE.match(nxt):
                    break
                if not (nxt.startswith(" ") or nxt.startswith("\t")):
                    break  # lazy continuation ends the item (becomes a paragraph)
                end = line_end(j)
                result.links.extend(_extract_links(nxt))
                j += 1
            result.blocks.append(
                Block(
                    kind="list_item",
                    start=start,
                    end=end,
                    meta={"ordered": list_match.group(2)[0].isdigit()},
                )
            )
            i = j
            continue

        # --- pandoc-style definition line ------------------------------------
        definition = _DEF_RE.match(line)
        if definition:
            flush_para()
            result.blocks.append(
                Block(kind="definition", start=starts[i], end=line_end(i))
            )
            i += 1
            continue

        # --- plain paragraph line ---------------------------------------------
        result.links.extend(_extract_links(line))
        if para_start < 0:
            para_start = starts[i]
        para_end = line_end(i)
        para_lines.append(line)
        i += 1

    # --- end of input ------------------------------------------------------
    if fence is not None:
        result.blocks.append(Block(kind="code", start=fence[2], end=len(normalized)))
    flush_para()

    # --- title: front matter wins, otherwise the first H1 -------------------
    if result.title is None:
        for block in result.blocks:
            if block.kind == "heading" and block.level == 1 and block.heading_text:
                result.title = block.heading_text
                break

    return result
