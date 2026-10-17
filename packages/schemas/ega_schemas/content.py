"""Content and structural text schemas for EntityGraph Auditor."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from ega_schemas.enums import AnswerShape


class TextSpan(BaseModel):
    """Character offset span in normalized text."""

    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    text: str = ""


class ContentSourceMeta(BaseModel):
    """Metadata about a retrieved or ingested content source."""

    source_id: str = ""
    source_type: str = "text"
    kind: str = "text"
    original_format: str = "markdown"
    filename: Optional[str] = None
    size_bytes: Optional[int] = None
    parser: str = "deterministic"
    url: Optional[str] = None
    fetched_at: Optional[str] = None
    http_status: Optional[int] = None
    canonical_url: Optional[str] = None
    render_mode: str = "text_only"
    extraction_notes: list[str] = Field(default_factory=list)
    extraction_loss: float = 0.0
    limitations: list[str] = Field(default_factory=list)
    hash: str = ""





class Heading(BaseModel):
    """Heading node extracted from document structure."""

    level: int = Field(ge=1, le=6, description="Heading level 1-6")
    text: str
    id: str = ""
    offset: int = 0


class Link(BaseModel):
    """Hyperlink detected in document."""

    url: str
    anchor_text: str
    is_internal: bool = False
    is_anchor: bool = False


class Passage(BaseModel):
    """Atomic retrievable passage (paragraph, list item, or callout)."""

    passage_id: str
    section_id: str = ""
    text: str
    word_count: int = Field(ge=0)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    named_subject: bool = False
    answer_first: bool = False
    answer_shape: Optional[AnswerShape] = None
    issues: list[str] = Field(default_factory=list)


class Section(BaseModel):
    """Document section under a heading or logical block."""

    section_id: str
    heading: Optional[Heading] = None
    passages: list[Passage] = Field(default_factory=list)
    raw_text: str = ""
    word_count: int = Field(ge=0, default=0)


class ParsedDocument(BaseModel):
    """Normalized document parsed into structural components."""

    raw_text: str
    original_text: str = ""
    normalized_text: str

    title: Optional[str] = None
    sections: list[Section] = Field(default_factory=list)
    passages: list[Passage] = Field(default_factory=list)
    headings: list[Heading] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    tables: list[Any] = Field(default_factory=list)
    lists: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    text_stats: dict[str, Any] = Field(default_factory=dict)
    suggested_page_type: Optional[str] = None
    confidence: Optional[str] = None
    rationale: Optional[str] = None
    word_count: int = Field(ge=0, default=0)
    char_count: int = Field(ge=0, default=0)
    reading_time_minutes: float = Field(ge=0.0, default=0.0)
    content_hash: str = ""
