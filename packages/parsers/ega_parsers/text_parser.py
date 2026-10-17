"""Plain-text parser.

Paragraphs are split on blank lines. Headings are recognised **only** when a
line is explicitly markdown-like (``# ``–``###### ``) or is a short ALL-CAPS
line without terminal punctuation — nothing else is guessed, so ordinary
uppercase sentences stay paragraph text.

Plain text carries no link, table or list markup; those stay empty and the
limitation is recorded on the source.
"""

from __future__ import annotations

import re

from ega_parsers.normalize import normalize_text
from ega_parsers.result import ParseResult
from ega_parsers.segment import Block

_MD_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*)$")
_MAX_CAPS_WORDS = 12
_MAX_CAPS_CHARS = 100
_TERMINAL_PUNCT = ".!?:;,"



def _is_caps_heading(line: str) -> bool:
    """True for a short ALL-CAPS line without terminal punctuation."""
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_CAPS_CHARS:
        return False
    if stripped[-1] in _TERMINAL_PUNCT:
        return False
    letters = [ch for ch in stripped if ch.isalpha()]
    if not letters:
        return False
    if any(ch.islower() for ch in letters):
        return False
    words = stripped.split()
    if not 1 <= len(words) <= _MAX_CAPS_WORDS:
        return False
    # Require the line to be a standalone unit: it must not look like an
    # acronym-heavy sentence fragment continuing somewhere else.
    return True


def scan_text(text: str) -> ParseResult:
    """Parse *text* as plain text into a pre-assembly :class:`ParseResult`."""
    normalized = normalize_text(text)
    result = ParseResult(raw_text=text, normalized_text=normalized)

    lines = normalized.split("\n")
    starts: list[int] = []
    pos = 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1

    para_start = -1
    para_end = -1

    def flush_para() -> None:
        nonlocal para_start, para_end
        if para_start >= 0:
            result.blocks.append(Block(kind="paragraph", start=para_start, end=para_end))
            para_start = -1
            para_end = -1

    for idx, line in enumerate(lines):
        line_start = starts[idx]
        line_end = line_start + len(line)

        if not line.strip():
            flush_para()
            continue

        md = _MD_HEADING_RE.match(line)
        if md:
            flush_para()
            level = len(md.group(1))
            heading_text = re.sub(r"[ \t]+#+[ \t]*$", "", md.group(2).rstrip())
            result.blocks.append(
                Block(
                    kind="heading",
                    start=line_start,
                    end=line_end,
                    level=level,
                    heading_text=heading_text.strip(),
                )
            )
            if level == 1 and result.title is None and heading_text.strip():
                result.title = heading_text.strip()
            continue

        if _is_caps_heading(line):
            flush_para()
            result.blocks.append(
                Block(
                    kind="heading",
                    start=line_start,
                    end=line_end,
                    level=1,
                    heading_text=line.strip(),
                )
            )
            continue

        if para_start < 0:
            para_start = line_start
        para_end = line_end

    flush_para()
    return result
