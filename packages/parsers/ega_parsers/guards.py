"""Failure guards: never let pathological content escape the parsers.

A format scanner that raises on hostile or malformed input falls back to
plain-text extraction; the failure and its consequence are recorded as notes
and limitations on the parse result (and later, on ``ContentSourceMeta``).
"""

from __future__ import annotations

from ega_parsers.normalize import normalize_text
from ega_parsers.result import ParseResult


def fallback_result(raw_text: str, reason: str, limitation: str) -> ParseResult:
    """Plain-text fallback for *raw_text* with an explicit reason attached."""
    from ega_parsers.text_parser import scan_text  # local import: avoids cycles

    try:
        result = scan_text(raw_text)
    except Exception:  # pragma: no cover - last-resort normalization only
        result = ParseResult(raw_text=raw_text, normalized_text=normalize_text(raw_text))
    result.fallback_used = True
    result.notes.append(reason)
    result.limitations.append(limitation)
    return result


def guarded_scan(scan, raw_text: str, parser_name: str) -> ParseResult:
    """Run *scan* over *raw_text*; fall back to plain text with a note."""
    try:
        return scan(raw_text)
    except Exception as exc:  # noqa: BLE001 - hostile input must not escape
        return fallback_result(
            raw_text,
            reason=(
                f"{parser_name} parsing failed "
                f"({type(exc).__name__}: {exc}); fell back to plain-text extraction."
            ),
            limitation=(
                f"{parser_name} structure (headings/links/tables) could not be "
                "extracted reliably; document treated as plain text."
            ),
        )
