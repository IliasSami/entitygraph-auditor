"""Text normalization shared by every parser.

All offsets stored in :class:`ega_schemas.content.ParsedDocument` refer to the
*normalized* text, so normalization must be deterministic and every parser must
derive its structure from the normalized string (Markdown/plain text) or build
the normalized string block-by-block before recording spans (HTML/DOCX).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

# Zero-width characters, soft hyphen, byte-order mark and directional controls
# that carry no semantic content but shift offsets.
_INVISIBLE_CHARS = frozenset(
    {
        "\u00ad",  # soft hyphen
        "\u200b",  # zero width space
        "\u200c",  # zero width non-joiner
        "\u200d",  # zero width joiner
        "\ufeff",  # BOM / zero width no-break space
        "\u200e",  # left-to-right mark
        "\u200f",  # right-to-left mark
        "\u061c",  # arabic letter mark
        "\u202a",  # left-to-right embedding
        "\u202b",  # right-to-left embedding
        "\u202c",  # pop directional formatting
        "\u202d",  # left-to-right override
        "\u202e",  # right-to-left override
        "\u2066",  # left-to-right isolate
        "\u2067",  # right-to-left isolate
        "\u2068",  # first strong isolate
        "\u2069",  # pop directional isolate
    }
)

_RUN_OF_NEWLINES = re.compile(r"\n{3,}")
_TRAILING_SPACES = re.compile(r"[ \t]+$", re.MULTILINE)
_INNER_RUN_OF_NEWLINES = re.compile(r"\n{2,}")


def strip_invisible(text: str) -> str:
    """Remove zero-width, soft-hyphen, BOM and directional control characters."""
    return "".join(ch for ch in text if ch not in _INVISIBLE_CHARS)


def normalize_text(text: str) -> str:
    """Return the canonical normalized form of *text*.

    Steps (in order):

    1. NFKC Unicode normalization (compatibility forms such as U+FB01 ``fi`` ligature -> ``fi``).
    2. CRLF / lone CR → LF.
    3. Strip zero-width, soft-hyphen, BOM and directional control characters.
    4. Collapse runs of 3+ newlines to a single blank line (``\\n\\n``).
    5. Strip trailing spaces/tabs on every line.

    The function is idempotent: ``normalize_text(normalize_text(x)) ==
    normalize_text(x)``, which keeps recorded offsets stable.
    """
    out = unicodedata.normalize("NFKC", text)
    out = out.replace("\r\n", "\n").replace("\r", "\n")
    out = strip_invisible(out)
    out = _RUN_OF_NEWLINES.sub("\n\n", out)
    out = _TRAILING_SPACES.sub("", out)
    return out


def content_hash(normalized_text: str) -> str:
    """Return ``"sha256:<hex>"`` for the normalized text."""
    digest = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def block_normalized(raw_block: str) -> str:
    """Normalize a single content block prior to assembling visible text.

    HTML and DOCX extraction build ``normalized_text`` by joining pre-normalized
    blocks with blank lines. Inner newlines are collapsed to one so that the
    assembled document is already in normalized form (joining with ``"\\n\\n"``
    then re-normalizing changes nothing, keeping block spans exact).
    """
    out = normalize_text(raw_block)
    out = _INNER_RUN_OF_NEWLINES.sub("\n", out)
    return out.strip(" \t")
