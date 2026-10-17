"""Intermediate parse results shared by the format parsers.

Each format parser walks its input and produces a :class:`ParseResult`: the
verbatim raw text, the normalized text, classified blocks with exact spans,
plus extraction by-products (links, metadata, boilerplate lines, honest
notes/limitations). The assembly layer converts a ``ParseResult`` into the
shared :class:`ega_schemas.content.ParsedDocument` exactly once, so schema
knowledge lives in a single module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ega_parsers.segment import Block


@dataclass
class RawLink:
    """A hyperlink as found in the source, before URL resolution."""

    url: str
    anchor_text: str
    rel: str = ""
    is_anchor: bool = False


@dataclass
class ParseResult:
    """Everything a format parser extracted, pre-assembly."""

    raw_text: str
    normalized_text: str
    blocks: list[Block] = field(default_factory=list)
    links: list[RawLink] = field(default_factory=list)
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    boilerplate_lines: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    fallback_used: bool = False
