"""HTML parser built on BeautifulSoup (``html.parser`` backend, no network).

Extraction contract:

* ``<title>`` (falling back to the first H1), meta description, canonical
  link, ``<html lang>``, robots meta (with an explicit ``noindex`` flag),
  raw ``application/ld+json`` blocks (metadata key ``json_ld``), form and code
  block counts for the classifier.
* Visible body text in document order, **skipping** ``script``/``style``/
  ``nav``/``footer``/``aside``/``head``/``noscript``/``iframe``/``svg``,
  comments and hidden elements. Text from ``nav``/``footer``/``aside`` is
  still collected as *boilerplate lines* so template menus contribute to the
  boilerplate ratio without polluting content passages.
* Heading tree from H1–H6, tables (row → cells), lists (per-item, nested
  lists become their own items), definitions (``<dd>``), ``<pre>`` blocks, and
  every ``<a href>`` (document order, with ``rel`` and internal detection
  resolved later against ``base_url``).

``normalized_text`` is assembled block-by-block in document order: each block
is normalized first, then joined with blank lines, so every recorded span is
an exact slice of the final normalized text.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Comment
from bs4.element import NavigableString, Tag

from ega_parsers.normalize import block_normalized
from ega_parsers.result import ParseResult, RawLink
from ega_parsers.segment import Block

# Elements whose subtrees never contribute visible text.
_SKIP_TAGS = frozenset(
    {"script", "style", "nav", "footer", "aside", "head", "noscript",
     "iframe", "svg", "canvas", "template", "object", "embed"}
)
# Of those, these are template/boilerplate regions: their text still feeds
# the boilerplate ratio.
_BOILERPLATE_TAGS = frozenset({"nav", "footer", "aside"})

_HEADINGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

# Container elements we recurse through (never emit directly).
_CONTAINERS = frozenset(
    {"html", "body", "main", "article", "section", "div", "header", "figure",
     "figcaption", "details", "summary", "blockquote", "form", "fieldset",
     "ul", "ol", "dl", "table", "thead", "tbody", "tfoot", "tr", "select",
     "optgroup", "picture", "video", "audio", "dialog", "search"}
)

_WS_RUN = re.compile(r"\s+")
_HIDDEN_STYLE_RE = re.compile(r"(display\s*:\s*none|visibility\s*:\s*hidden)", re.IGNORECASE)


def _collapse(text: str) -> str:
    return _WS_RUN.sub(" ", text).strip()


def _emit(result: ParseResult, kind: str, raw: str, meta: dict[str, Any] | None = None) -> None:
    """Normalize one raw block and record its span in the assembled text.

    The assembled ``normalized_text`` starts empty; every block is normalized
    first and joined with a blank line, so the final string is already in
    normalized form and each block's span is an exact slice.
    """
    normalized = block_normalized(raw)
    if not normalized:
        return
    if result.normalized_text:
        result.normalized_text += "\n\n"
    start = len(result.normalized_text)
    result.normalized_text += normalized
    block = Block(kind=kind, start=start, end=start + len(normalized), meta=meta or {})
    if kind == "heading":
        block.level = block.meta["level"]
        block.heading_text = block.meta["heading_text"]
    result.blocks.append(block)


class _Walker:
    """Depth-first extractor producing ordered blocks, links and metadata."""

    def __init__(self, result: ParseResult) -> None:
        self.result = result

    # -- helpers ---------------------------------------------------------
    def _flush_run(self, parts: list[str]) -> None:
        raw = "".join(parts)
        if raw.strip():
            _emit(self.result, "paragraph", raw)
        parts.clear()

    def _emit_li(self, tag: Tag) -> None:
        own: list[str] = []
        for child in tag.children:
            if isinstance(child, NavigableString):
                own.append(str(child))
            elif isinstance(child, Tag) and child.name in ("ul", "ol"):
                continue  # nested list handled separately
            elif isinstance(child, Tag):
                own.append(child.get_text())
        raw = "".join(own)
        if raw.strip():
            ordered = isinstance(tag.parent, Tag) and tag.parent.name == "ol"
            _emit(self.result, "list_item", raw, {"ordered": ordered})
        # Recurse into nested lists so their items become passages too.
        for child in tag.children:
            if isinstance(child, Tag) and child.name in ("ul", "ol"):
                self.walk(child)

    def _emit_tr(self, tag: Tag) -> None:
        cells = [
            _collapse(cell.get_text())
            for cell in tag.find_all(["td", "th"], recursive=False)
        ]
        if not any(cells):
            return
        raw = " | ".join(cells)
        _emit(self.result, "table_row", raw, {"cells": cells})

    # -- main walk -------------------------------------------------------
    def walk(self, container: Tag) -> None:
        run_parts: list[str] = []
        for child in container.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                run_parts.append(str(child))
                continue
            if not isinstance(child, Tag):
                continue
            name = child.name
            if name in _SKIP_TAGS or child.get("hidden") is not None:
                continue
            if isinstance(child.get("style"), str) and _HIDDEN_STYLE_RE.search(child.get("style", "")):
                continue
            if name in _HEADINGS:
                self._flush_run(run_parts)
                text = _collapse(child.get_text())
                if text:
                    _emit(
                        self.result,
                        "heading",
                        text,
                        {"level": int(name[1]), "heading_text": text},
                    )
                continue
            if name == "p":
                self._flush_run(run_parts)
                _emit(self.result, "paragraph", child.get_text())
                continue
            if name == "pre":
                self._flush_run(run_parts)
                _emit(self.result, "code", child.get_text())
                continue
            if name == "li":
                self._flush_run(run_parts)
                self._emit_li(child)
                continue
            if name == "tr":
                self._flush_run(run_parts)
                self._emit_tr(child)
                continue
            if name == "dt":
                self._flush_run(run_parts)
                _emit(self.result, "paragraph", child.get_text())
                continue
            if name == "dd":
                self._flush_run(run_parts)
                _emit(self.result, "definition", child.get_text())
                continue
            if name in _CONTAINERS:
                self._flush_run(run_parts)
                self.walk(child)
                continue
            # Unknown/inline element: part of the surrounding text run.
            run_parts.append(child.get_text())
        self._flush_run(run_parts)


def scan_html(html: str) -> ParseResult:
    """Parse *html* into a pre-assembly :class:`ParseResult`.

    Raises whatever BeautifulSoup raises on pathological input; the public
    :func:`ega_parsers.parse_html` catches that and falls back to plain-text
    parsing with an explicit limitation note.
    """
    result = ParseResult(raw_text=html, normalized_text="")
    soup = BeautifulSoup(html, "html.parser")

    # ---- metadata before any subtree is removed --------------------------
    if soup.title and soup.title.string:
        result.title = _collapse(soup.title.string)

    meta: dict[str, Any] = {
        "description": "",
        "canonical": "",
        "lang": "",
        "robots": "",
        "robots_noindex": False,
        "json_ld": [],
        "form_count": 0,
        "code_block_count": 0,
    }
    for tag in soup.find_all("meta"):
        name = (tag.get("name") or "").lower()
        if name == "description" and tag.get("content"):
            meta["description"] = tag["content"]
        elif name == "robots" and tag.get("content"):
            content = tag["content"]
            meta["robots"] = content
            meta["robots_noindex"] = "noindex" in content.lower()
    canonical = soup.find("link", rel=lambda v: v and "canonical" in v)
    if canonical and canonical.get("href"):
        meta["canonical"] = canonical["href"]
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        meta["lang"] = html_tag["lang"]
    for script in soup.find_all("script", type=lambda v: v and "ld+json" in v.lower()):
        raw = script.string if script.string is not None else script.get_text()
        if raw:
            meta["json_ld"].append(raw)
    meta["form_count"] = len(soup.find_all("form"))
    meta["code_block_count"] = len(soup.find_all("pre"))
    result.metadata = meta

    # First H1 as title fallback.
    if result.title is None:
        first_h1 = soup.find("h1")
        if first_h1:
            result.title = _collapse(first_h1.get_text()) or None

    # ---- links (collected before skip regions are removed) ---------------
    for a in soup.find_all("a", href=True):
        href = a["href"]
        rel = a.get("rel")
        rel_text = " ".join(rel) if isinstance(rel, list) else str(rel or "")
        result.links.append(
            RawLink(
                url=href,
                anchor_text=_collapse(a.get_text()),
                rel=rel_text,
                is_anchor=href.startswith("#"),
            )
        )

    # ---- boilerplate lines from nav/footer/aside -------------------------
    for name in _BOILERPLATE_TAGS:
        for tag in soup.find_all(name):
            if tag.decomposed:
                continue
            text = tag.get_text("\n")
            result.boilerplate_lines.extend(
                ln.strip() for ln in text.splitlines() if ln.strip()
            )

    # ---- remove non-visible subtrees -------------------------------------
    for tag in soup.find_all(list(_SKIP_TAGS)):
        if not tag.decomposed:
            tag.decompose()
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    # <br> becomes a real line break in the extracted text.
    for br in soup.find_all("br"):
        br.replace_with(NavigableString("\n"))

    # ---- visible text walk ------------------------------------------------
    walker = _Walker(result)
    root = soup.body if soup.body else soup
    walker.walk(root)

    return result
