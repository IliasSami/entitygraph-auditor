"""Context / skill pack importer (PRD FR-16, FR-02; §18 threat model).

Reads ZIP and gzip-compressed tar (``.tar.gz``/``.tgz``) archives — detected
by magic bytes, not extension — or an already-extracted directory, and turns
the contents into an :class:`ImportedPack` of structured data.

**Security contract (PRD FR-16 / FR-24, §18 "Malicious ZIP/skill pack"):**

* Imported content is *data and methodology, not authority to change
  application security* (FR-16, verbatim).  This module NEVER executes,
  evaluates, compiles, imports or obeys any code, script or command found in
  a pack.  Scripts (``scripts/**``, ``*.py``, ``*.sh``, ``*.js``) are recorded
  as file paths only, and a warning states they are never executed.
* Nothing is ever extracted to disk: entries are read in memory with path
  validation (no absolute paths, no ``..`` traversal, no Windows drive
  prefixes, no NUL bytes), symlink/hardlink/device members rejected, file
  count and per-file/total size limits enforced, and a compression-ratio
  guard rejects zip bombs (PRD FR-24 "reject unsafe archive paths and zip
  bombs").
* Conflicts between files are surfaced in ``conflicts`` — never silently
  reconciled (FR-01/FR-16).
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import stat
import tarfile
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

try:  # YAML support is optional; a constrained fallback parser is bundled.
    import yaml
except ImportError:  # pragma: no cover - environment without PyYAML
    yaml = None  # type: ignore[assignment]

__all__ = [
    "ImportedPack",
    "import_pack",
    "pack_version_hash",
    "parse_pack_directory",
]

MAX_PER_FILE_BYTES = 10_000_000
DEFAULT_MAX_TOTAL_UNCOMPRESSED = 50_000_000
DEFAULT_MAX_FILES = 500
MAX_COMPRESSION_RATIO = 200
_CHUNK_SIZE = 64 * 1024
_BINARY_SNIFF_BYTES = 8192

#: Sentinel for "this file could not be parsed as structured data".
_FAILED: Any = object()


@dataclass
class ImportedPack:
    """Parsed context/skill pack (PRD FR-16 import manifest contract).

    ``manifest`` holds one entry per file: ``path``, ``size``, ``sha256``,
    ``kind`` and ``parsed``.  All paths are relative and use forward slashes.
    ``scripts`` are file paths only — stored for reference, never executed.
    """

    name: str = ""
    version: str = ""
    version_hash: str = ""
    source_file: str = ""
    files: list[str] = field(default_factory=list)
    documents: list[dict] = field(default_factory=list)
    brand_rules: list[dict] = field(default_factory=list)
    canonical_facts: list[dict] = field(default_factory=list)
    banned_terms: list[dict] = field(default_factory=list)
    approved_claims: list[dict] = field(default_factory=list)
    topical_map_rows: list[dict] = field(default_factory=list)
    internal_link_targets: list[dict] = field(default_factory=list)
    scoring_config: dict = field(default_factory=dict)
    writer_handoff_template: str | None = None
    scripts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    manifest: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class _FileEntry:
    """One in-memory file from a pack: validated relative path + raw bytes."""

    path: str
    data: bytes


# --------------------------------------------------------------------------- #
# Path and format safety (PRD FR-24)
# --------------------------------------------------------------------------- #


def _safe_member_path(name: str, *, origin: str) -> str:
    """Normalize an archive/directory member name to a safe relative path.

    Rejects absolute paths, ``..`` traversal, Windows drive/UNC prefixes and
    NUL bytes — the zip-slip class of attacks (§18 "Malicious ZIP/skill
    pack").  Returns the forward-slash relative path on success.
    """
    if not name:
        raise ValueError(f"Unsafe file name in {origin}: the name is empty.")
    if "\x00" in name:
        raise ValueError(f"Unsafe file name in {origin}: NUL bytes are not allowed.")
    normalized = name.replace("\\", "/")
    if re.match(r"^[A-Za-z]:", normalized):
        raise ValueError(
            f"Unsafe file name in {origin}: drive-prefixed path {name!r} is not allowed."
        )
    if normalized.startswith("/"):
        raise ValueError(
            f"Unsafe file name in {origin}: absolute path {name!r} is not allowed."
        )
    parts = [segment for segment in normalized.split("/") if segment not in ("", ".")]
    if not parts:
        raise ValueError(f"Unsafe file name in {origin}: the name is empty.")
    if any(segment == ".." for segment in parts):
        raise ValueError(
            f"Unsafe path in {origin}: path traversal {name!r} is not allowed."
        )
    return "/".join(parts)


def _detect_format(data: bytes) -> str:
    """Detect ``zip`` or ``tgz`` from magic bytes (never from the extension)."""
    if data[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
        return "zip"
    if data[:2] == b"\x1f\x8b":
        return "tgz"
    raise ValueError(
        "Unrecognized archive format: expected a ZIP archive or a "
        "gzip-compressed tarball (.tar.gz/.tgz)."
    )


# --------------------------------------------------------------------------- #
# In-memory readers
# --------------------------------------------------------------------------- #


def _read_zip_member(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, path: str, warnings: list[str]
) -> bytes | None:
    """Stream one zip member with a hard cap; return ``None`` if it overruns."""
    chunks: list[bytes] = []
    total = 0
    try:
        with archive.open(info) as handle:
            while True:
                chunk = handle.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_PER_FILE_BYTES:
                    warnings.append(
                        f"File '{path}' exceeded the {MAX_PER_FILE_BYTES}-byte limit "
                        "while reading and was skipped."
                    )
                    return None
                chunks.append(chunk)
    except (zipfile.BadZipFile, EOFError, OSError, ValueError) as exc:
        raise ValueError(f"Archive entry '{path}' could not be read safely.") from exc
    return b"".join(chunks)


def _read_zip(
    data: bytes, *, max_total_uncompressed: int, max_files: int
) -> tuple[list[_FileEntry], list[str]]:
    """Read zip entries in memory with all FR-24 safety guards."""
    warnings: list[str] = []
    entries: list[_FileEntry] = []
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise ValueError("The ZIP archive is malformed and cannot be imported.") from exc
    with archive:
        normalized = [
            (_safe_member_path(info.filename, origin="ZIP archive"), info)
            for info in archive.infolist()
        ]
        file_pairs = [(path, info) for path, info in normalized if not info.is_dir()]
        if len(file_pairs) > max_files:
            raise ValueError(
                f"The archive contains {len(file_pairs)} files which exceeds "
                f"the limit of {max_files}."
            )
        file_pairs.sort(key=lambda pair: pair[0])
        seen: set[str] = set()
        total = 0
        for path, info in file_pairs:
            if path in seen:
                warnings.append(
                    f"Duplicate path '{path}' in archive; kept the first occurrence."
                )
                continue
            seen.add(path)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(
                    f"The archive contains a symbolic link at '{path}'; links are "
                    "not allowed (PRD FR-24)."
                )
            if info.file_size > 0 and (
                info.compress_size == 0
                or info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
            ):
                raise ValueError(
                    f"Archive entry '{path}' has a suspicious compression ratio "
                    "(possible zip bomb) and was rejected."
                )
            if info.file_size > MAX_PER_FILE_BYTES:
                warnings.append(
                    f"File '{path}' exceeds the {MAX_PER_FILE_BYTES}-byte per-file "
                    "limit and was skipped."
                )
                continue
            payload = _read_zip_member(archive, info, path, warnings)
            if payload is None:
                continue
            total += len(payload)
            if total > max_total_uncompressed:
                raise ValueError(
                    f"Uncompressed content exceeds the {max_total_uncompressed}-byte "
                    "total limit."
                )
            entries.append(_FileEntry(path=path, data=payload))
    return entries, warnings


def _gunzip_limited(data: bytes, limit: int) -> bytes:
    """Decompress gzip data in chunks, refusing to exceed ``limit`` bytes."""
    handle = gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb")
    chunks: list[bytes] = []
    total = 0
    with handle:
        while True:
            chunk = handle.read(_CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise ValueError(
                    f"Uncompressed content exceeds the {limit}-byte total limit "
                    "(possible compression bomb)."
                )
            chunks.append(chunk)
    return b"".join(chunks)


def _read_tar_gz(
    data: bytes, *, max_total_uncompressed: int, max_files: int
) -> tuple[list[_FileEntry], list[str]]:
    """Read a gzip-compressed tarball in memory with all FR-24 safety guards."""
    warnings: list[str] = []
    entries: list[_FileEntry] = []
    try:
        raw = _gunzip_limited(data, max_total_uncompressed)
    except (gzip.BadGzipFile, EOFError, OSError, zlib.error) as exc:
        raise ValueError("The gzip stream is malformed and cannot be imported.") from exc
    try:
        archive = tarfile.open(fileobj=io.BytesIO(raw), mode="r:")
    except tarfile.TarError as exc:
        raise ValueError(
            "The gzip data does not contain a readable tar archive."
        ) from exc
    with archive:
        members = archive.getmembers()
        normalized = [
            (_safe_member_path(member.name, origin="tar archive"), member)
            for member in members
        ]
        for path, member in normalized:
            if member.issym() or member.islnk():
                raise ValueError(
                    f"The archive contains a link at '{path}'; symbolic and hard "
                    "links are not allowed (PRD FR-24)."
                )
            if not (member.isfile() or member.isdir()):
                raise ValueError(
                    f"Archive member '{path}' has an unsupported type (device, FIFO "
                    "or special file) and was rejected."
                )
        file_pairs = [(path, member) for path, member in normalized if member.isfile()]
        if len(file_pairs) > max_files:
            raise ValueError(
                f"The archive contains {len(file_pairs)} files which exceeds "
                f"the limit of {max_files}."
            )
        file_pairs.sort(key=lambda pair: pair[0])
        seen: set[str] = set()
        total = 0
        for path, member in file_pairs:
            if path in seen:
                warnings.append(
                    f"Duplicate path '{path}' in archive; kept the first occurrence."
                )
                continue
            seen.add(path)
            if member.size > MAX_PER_FILE_BYTES:
                warnings.append(
                    f"File '{path}' exceeds the {MAX_PER_FILE_BYTES}-byte per-file "
                    "limit and was skipped."
                )
                continue
            source = archive.extractfile(member)
            if source is None:
                warnings.append(f"File '{path}' could not be read and was skipped.")
                continue
            with source:
                payload = source.read(MAX_PER_FILE_BYTES + 1)
            if len(payload) > MAX_PER_FILE_BYTES:
                warnings.append(
                    f"File '{path}' exceeds the {MAX_PER_FILE_BYTES}-byte per-file "
                    "limit and was skipped."
                )
                continue
            total += len(payload)
            if total > max_total_uncompressed:
                raise ValueError(
                    f"Uncompressed content exceeds the {max_total_uncompressed}-byte "
                    "total limit."
                )
            entries.append(_FileEntry(path=path, data=payload))
    return entries, warnings


def _read_file_capped(path: Path, relative: str, warnings: list[str]) -> bytes | None:
    """Read a directory file in chunks with the per-file cap; ``None`` if over."""
    chunks: list[bytes] = []
    total = 0
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_PER_FILE_BYTES:
                    warnings.append(
                        f"File '{relative}' exceeds the {MAX_PER_FILE_BYTES}-byte "
                        "per-file limit and was skipped."
                    )
                    return None
                chunks.append(chunk)
    except OSError as exc:
        warnings.append(
            f"File '{relative}' could not be read and was skipped ({type(exc).__name__})."
        )
        return None
    return b"".join(chunks)


# --------------------------------------------------------------------------- #
# Structured parsing helpers
# --------------------------------------------------------------------------- #


def _decode_text(data: bytes) -> str:
    """Decode pack text as UTF-8 (BOM tolerated, replacement chars tolerated)."""
    return data.decode("utf-8-sig", errors="replace")


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _stable(value: Any) -> str:
    """Deterministic comparable form of a value for conflict detection."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _parse_structured(path: str, text: str, warnings: list[str]) -> Any:
    """Parse JSON/YAML text; return ``_FAILED`` (plus a warning) when unsable.

    YAML uses PyYAML's ``safe_load`` when available.  Otherwise a constrained
    built-in YAML subset parser runs; if the text is outside that subset the
    file is kept as raw text with the explicit warning required by FR-16.
    """
    lower = path.lower()
    if lower.endswith(".json"):
        try:
            loaded: Any = json.loads(text)
        except ValueError:
            warnings.append(f"Could not parse '{path}' as JSON; stored as raw text.")
            return _FAILED
    elif lower.endswith((".yml", ".yaml")):
        if yaml is not None:
            try:
                loaded = yaml.safe_load(text)
            except Exception:  # PyYAML raises several error classes; never trust input
                warnings.append(f"Could not parse '{path}' as YAML; stored as raw text.")
                return _FAILED
        else:
            loaded = _mini_yaml(text)
            if loaded is None and text.strip():
                warnings.append(
                    "YAML parsed as raw text (no YAML library installed); "
                    f"file: {path}"
                )
                return _FAILED
            if loaded is not None:
                warnings.append(
                    f"YAML in '{path}' parsed with a built-in fallback parser "
                    "(no YAML library installed)."
                )
    else:
        warnings.append(
            f"Unsupported structured format for '{path}'; stored as raw text."
        )
        return _FAILED
    if loaded is None:
        warnings.append(f"'{path}' contains no structured data.")
        return _FAILED
    return loaded


def _table_rows(path: str, text: str, warnings: list[str]) -> Any:
    """Parse CSV/TSV text into row dicts (first row is the header)."""
    delimiter = "\t" if path.lower().endswith(".tsv") else ","
    try:
        raw_rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except csv.Error:
        warnings.append(f"Could not parse '{path}' as a table; stored as raw text.")
        return _FAILED
    if not raw_rows:
        warnings.append(f"'{path}' contains no data rows.")
        return []
    header = [cell.strip() for cell in raw_rows[0]]
    if not any(header):
        warnings.append(f"'{path}' has no header row; stored as raw text.")
        return _FAILED
    records: list[dict] = []
    for row in raw_rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        record: dict[str, str] = {}
        for index, key in enumerate(header):
            cell = row[index].strip() if index < len(row) else ""
            record[key or f"column_{index + 1}"] = cell
        records.append(record)
    if not records:
        warnings.append(f"'{path}' contains no data rows.")
    return records


def _generic_rows(obj: Any) -> list[dict]:
    """Normalize a parsed structured value into a list of row dicts."""
    if isinstance(obj, list):
        rows: list[dict] = []
        for item in obj:
            if isinstance(item, dict):
                rows.append(item)
            elif item is not None:
                rows.append({"value": item})
        return rows
    if isinstance(obj, dict):
        for key in ("rows", "items", "queries", "links"):
            inner = obj.get(key)
            if isinstance(inner, list):
                return _generic_rows(inner)
        if obj and all(_is_scalar(value) for value in obj.values()):
            return [dict(obj)]
        return [{"key": str(key), "value": value} for key, value in obj.items()]
    if _is_scalar(obj):
        return [{"value": obj}]
    return []


def _fact_rows(obj: Any) -> list[dict]:
    """Normalize canonical-fact content into ``{key, value}`` rows."""
    if isinstance(obj, dict):
        return [{"key": str(key), "value": value} for key, value in obj.items()]
    rows: list[dict] = []
    for item in _generic_rows(obj):
        if "key" in item or "value" not in item:
            rows.append(item)
            continue
        if _is_scalar(item.get("value")):
            rows.append({"key": str(item["value"]), "value": None})
        else:
            rows.append({"key": str(item), "value": None})
    return rows


def _term_rows(obj: Any) -> list[dict]:
    """Normalize banned-term content into ``{term, reason}`` rows."""
    if isinstance(obj, dict):
        rows: list[dict] = []
        for key, value in obj.items():
            if _is_scalar(value):
                rows.append({"term": str(key), "reason": value})
            else:
                rows.append({"term": str(key), "details": value})
        return rows
    rows = []
    for item in _generic_rows(obj):
        row = dict(item)
        if "term" not in row and "name" in row:
            row["term"] = str(row.pop("name"))
        rows.append(row)
    return rows


def _term_payload(row: dict) -> str:
    """Comparable payload of a banned-term row (everything except the term)."""
    return _stable({key: value for key, value in row.items() if key != "term"})


# --------------------------------------------------------------------------- #
# Minimal YAML subset (used only when PyYAML is unavailable)
# --------------------------------------------------------------------------- #


class _MiniYamlError(ValueError):
    """Raised when text falls outside the supported YAML subset."""


def _mini_yaml_scalar(token: str) -> Any:
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    if token.startswith(("[", "{", "|", ">", "&", "*", "!", "?", "@", "`")):
        raise _MiniYamlError("unsupported YAML construct")
    if " #" in token:
        token = token.split(" #", 1)[0].rstrip()
    if token in ("", "~", "null", "Null", "NULL"):
        return None
    if token in ("true", "True", "TRUE"):
        return True
    if token in ("false", "False", "FALSE"):
        return False
    try:
        return int(token, 10)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def _mini_yaml_split_key(content: str) -> tuple[str, str] | None:
    """Split ``key: value`` only when a colon is EOL or followed by whitespace.

    Requiring whitespace after the colon mirrors YAML's plain-scalar rule and
    keeps URLs such as ``http://example.com`` from being read as mappings.
    """
    for index, char in enumerate(content):
        if char != ":":
            continue
        if index + 1 != len(content) and not content[index + 1].isspace():
            continue
        key = content[:index].strip().strip("\"'")
        if not key:
            return None
        return key, content[index + 1 :].strip()
    return None


def _mini_yaml_parse_map(
    lines: list[tuple[int, str]], position: int, indent: int
) -> tuple[dict, int]:
    mapping: dict[str, Any] = {}
    while position < len(lines):
        cur_indent, content = lines[position]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise _MiniYamlError("unexpected indentation")
        if content == "-" or content.startswith("- "):
            raise _MiniYamlError("sequence item where a mapping key was expected")
        split = _mini_yaml_split_key(content)
        if split is None:
            raise _MiniYamlError("expected 'key: value'")
        key, value = split
        position += 1
        if value == "":
            if position < len(lines) and lines[position][0] > indent:
                nested, position = _mini_yaml_parse_nodes(
                    lines, position, lines[position][0]
                )
                mapping[key] = nested
            else:
                mapping[key] = None
        else:
            mapping[key] = _mini_yaml_scalar(value)
    return mapping, position


def _mini_yaml_parse_list(
    lines: list[tuple[int, str]], position: int, indent: int
) -> tuple[list, int]:
    items: list[Any] = []
    while position < len(lines):
        cur_indent, content = lines[position]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise _MiniYamlError("unexpected indentation in sequence")
        if not (content == "-" or content.startswith("- ")):
            break
        item_text = content[1:].strip()
        position += 1
        if not item_text:
            if position < len(lines) and lines[position][0] > indent:
                nested, position = _mini_yaml_parse_nodes(
                    lines, position, lines[position][0]
                )
                items.append(nested)
            else:
                items.append(None)
            continue
        split = _mini_yaml_split_key(item_text)
        if split is None:
            items.append(_mini_yaml_scalar(item_text))
            continue
        pairs = [split]
        while position < len(lines):
            next_indent, next_text = lines[position]
            if next_indent <= indent or (
                next_text == "-" or next_text.startswith("- ")
            ):
                break
            next_split = _mini_yaml_split_key(next_text)
            if next_split is None:
                raise _MiniYamlError("expected 'key: value' inside sequence item")
            pairs.append(next_split)
            position += 1
        item_map: dict[str, Any] = {}
        for key, value in pairs:
            if value == "" and position < len(lines) and lines[position][0] > indent:
                nested, position = _mini_yaml_parse_nodes(
                    lines, position, lines[position][0]
                )
                item_map[key] = nested
            elif value == "":
                item_map[key] = None
            else:
                item_map[key] = _mini_yaml_scalar(value)
        items.append(item_map)
    return items, position


def _mini_yaml_parse_nodes(
    lines: list[tuple[int, str]], position: int, indent: int
) -> tuple[Any, int]:
    if position >= len(lines):
        raise _MiniYamlError("unexpected end of input")
    content = lines[position][1]
    if content == "-" or content.startswith("- "):
        return _mini_yaml_parse_list(lines, position, indent)
    return _mini_yaml_parse_map(lines, position, indent)


def _mini_yaml(text: str) -> Any:
    """Parse a constrained YAML subset (mappings, sequences, scalars, quotes).

    Returns ``None`` for anything outside the subset so callers can fall back
    to raw text.  Used only when PyYAML is not installed — no dependency is
    added by this module (FR-16 tooling stays dependency-free).
    """
    try:
        lines: list[tuple[int, str]] = []
        for raw_line in text.splitlines():
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue
            lead = raw_line[: len(raw_line) - len(raw_line.lstrip(" "))]
            if "\t" in lead:
                raise _MiniYamlError("tab indentation is not supported")
            lines.append((len(lead), raw_line.strip()))
        if lines and lines[0][1] in ("---", "..."):
            lines = lines[1:]
        if lines and lines[-1][1] in ("---", "..."):
            lines = lines[:-1]
        if not lines:
            return None
        value, position = _mini_yaml_parse_nodes(lines, 0, lines[0][0])
        if position != len(lines):
            raise _MiniYamlError("trailing content")
        return value
    except _MiniYamlError:
        return None


# --------------------------------------------------------------------------- #
# Classification and skill header
# --------------------------------------------------------------------------- #


def _classify(relpath: str) -> str:
    """Map a pack-relative path to its kind (PRD FR-16 file-type detection)."""
    lower = relpath.lower()
    basename = PurePosixPath(lower).name
    stem = PurePosixPath(lower).stem
    suffix = PurePosixPath(lower).suffix
    if basename == "skill.md":
        return "skill"
    if lower.startswith("scripts/") or suffix in {".py", ".sh", ".js"}:
        return "script"
    if suffix in {".md", ".markdown"} and (
        stem.startswith("handoff") or stem.startswith("writer")
    ):
        return "writer_handoff"
    if stem.startswith(("sources", "registry")):
        return "source_registry"
    if suffix in {".yml", ".yaml", ".json"} and stem.startswith("brand"):
        return "brand"
    if suffix in {".yml", ".yaml", ".json"} and stem.startswith("facts"):
        return "facts"
    if suffix in {".yml", ".yaml", ".json"} and stem.startswith("claims"):
        return "claims"
    if suffix in {".csv", ".tsv", ".yml", ".yaml", ".json"} and stem.startswith(
        "topical"
    ) and "map" in stem:
        return "topical_map"
    if suffix in {".yml", ".yaml", ".csv"} and stem.startswith("links"):
        return "links"
    if suffix in {".yml", ".yaml", ".json"} and stem.startswith("scoring"):
        return "scoring"
    return "reference"


def _parse_skill_header(text: str) -> tuple[str | None, str | None]:
    """Extract ``(name, version)`` from SKILL.md front matter or headings."""
    lines = text.splitlines()
    name: str | None = None
    version: str | None = None
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() in ("---", "..."):
                break
            key, sep, value = line.partition(":")
            if not sep:
                continue
            key = key.strip().lower()
            value = value.strip().strip("\"'")
            if key == "name" and value and name is None:
                name = value
            elif key == "version" and value and version is None:
                version = value
    if name is None:
        for line in lines:
            if line.lstrip().startswith("#"):
                name = line.lstrip().lstrip("#").strip() or None
                break
    if version is None:
        for line in lines:
            key, sep, value = line.partition(":")
            if sep and key.strip().lower() == "version":
                version = value.strip().strip("\"'") or None
                break
    return name, version


# --------------------------------------------------------------------------- #
# Pack assembly
# --------------------------------------------------------------------------- #


def pack_version_hash(pack: ImportedPack) -> str:
    """Deterministic sha256 over sorted ``path:sha256`` manifest lines.

    The hash depends only on file paths and content hashes — never on the
    order in which an archive stored them (PRD FR-16 version hash).
    """
    lines = sorted(
        f"{entry['path']}:{entry['sha256']}"
        for entry in pack.manifest
        if "path" in entry and "sha256" in entry
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _build_pack(
    entries: list[_FileEntry], *, source_file: str, warnings: list[str]
) -> ImportedPack:
    """Classify and parse validated in-memory entries into an :class:`ImportedPack`."""
    pack_warnings = list(warnings)
    conflicts: list[str] = []
    seen_conflicts: set[str] = set()

    def add_conflict(message: str) -> None:
        if message not in seen_conflicts:
            seen_conflicts.add(message)
            conflicts.append(message)

    ordered = sorted(entries, key=lambda entry: entry.path)
    if not ordered:
        pack_warnings.append("Pack is empty: no files were found.")

    documents: list[dict] = []
    brand_rules: list[dict] = []
    canonical_facts: list[dict] = []
    banned_terms: list[dict] = []
    approved_claims: list[dict] = []
    topical_map_rows: list[dict] = []
    internal_link_targets: list[dict] = []
    scoring_config: dict = {}
    scripts: list[str] = []
    manifest: list[dict] = []
    writer_handoff_template: str | None = None
    handoff_path: str | None = None
    skill_paths: list[str] = []
    skill_name: str | None = None
    skill_version: str | None = None
    fact_seen: dict[str, tuple[Any, str]] = {}
    term_seen: dict[str, tuple[str, str]] = {}
    scoring_sources: dict[str, str] = {}

    for entry in ordered:
        path = entry.path
        kind = _classify(path)
        digest = hashlib.sha256(entry.data).hexdigest()
        parsed = False
        is_binary = b"\x00" in entry.data[:_BINARY_SNIFF_BYTES]

        if kind == "script":
            # FR-16: scripts are stored for reference and NEVER parsed/executed.
            scripts.append(path)
        elif is_binary:
            pack_warnings.append(f"File '{path}' is binary and was not parsed.")
        else:
            text = _decode_text(entry.data)
            if kind == "skill":
                skill_paths.append(path)
                documents.append(
                    {"path": path, "kind": "skill", "text": text, "sha256": digest}
                )
                skill_name, skill_version = _parse_skill_header(text)
                parsed = True
            elif kind == "writer_handoff":
                if handoff_path is None:
                    writer_handoff_template = text
                    handoff_path = path
                    parsed = True
                else:
                    pack_warnings.append(
                        f"Additional writer handoff template '{path}' ignored; "
                        f"using '{handoff_path}'."
                    )
            elif kind == "source_registry":
                documents.append(
                    {
                        "path": path,
                        "kind": "source_registry",
                        "text": text,
                        "sha256": digest,
                    }
                )
                parsed = True
            elif kind in ("brand", "facts", "claims", "scoring"):
                structured = _parse_structured(path, text, pack_warnings)
                if structured is _FAILED:
                    documents.append(
                        {"path": path, "kind": "reference", "text": text, "sha256": digest}
                    )
                else:
                    parsed = True
                    if kind == "brand":
                        brand_rules.append({"path": path, "rules": structured})
                        extracted = (
                            _term_rows(structured.get("banned_terms"))
                            if isinstance(structured, dict)
                            and "banned_terms" in structured
                            else []
                        )
                        for row in extracted:
                            term = str(row.get("term", "")).strip()
                            if not term:
                                continue
                            banned_terms.append(row)
                            payload = _term_payload(row)
                            previous = term_seen.get(term)
                            if previous is None:
                                term_seen[term] = (payload, path)
                            elif previous[0] != payload:
                                add_conflict(
                                    f"Conflicting banned term '{term}': {previous[0]} "
                                    f"in {previous[1]} vs {payload} in {path}"
                                )
                    elif kind == "facts":
                        fact_rows = _fact_rows(structured)
                        canonical_facts.extend(fact_rows)
                        for row in fact_rows:
                            raw_key = row.get(
                                "key", row.get("name", row.get("id", row.get("fact")))
                            )
                            if raw_key is None:
                                continue
                            key = str(raw_key)
                            value = row.get("value")
                            previous = fact_seen.get(key)
                            if previous is None:
                                fact_seen[key] = (value, path)
                            elif _stable(previous[0]) != _stable(value):
                                add_conflict(
                                    f"Conflicting canonical fact '{key}': value "
                                    f"{previous[0]!r} in {previous[1]} vs {value!r} "
                                    f"in {path}"
                                )
                    elif kind == "claims":
                        approved_claims.extend(_generic_rows(structured))
                    else:  # scoring
                        if isinstance(structured, dict):
                            for key in sorted(structured, key=str):
                                value = structured[key]
                                key_text = str(key)
                                previous = scoring_config.get(key_text)
                                if key_text in scoring_config and _stable(
                                    previous
                                ) != _stable(value):
                                    add_conflict(
                                        f"Scoring config key '{key_text}' overridden: "
                                        f"{previous!r} in {scoring_sources[key_text]} "
                                        f"vs {value!r} in {path}"
                                    )
                                scoring_config[key_text] = value
                                scoring_sources[key_text] = path
                        else:
                            pack_warnings.append(
                                f"Scoring config '{path}' is not a key/value mapping; "
                                "ignored."
                            )
            elif kind in ("topical_map", "links"):
                if path.lower().endswith((".csv", ".tsv")):
                    rows = _table_rows(path, text, pack_warnings)
                else:
                    structured = _parse_structured(path, text, pack_warnings)
                    rows = _FAILED if structured is _FAILED else _generic_rows(structured)
                if rows is _FAILED:
                    documents.append(
                        {"path": path, "kind": "reference", "text": text, "sha256": digest}
                    )
                else:
                    parsed = True
                    if kind == "topical_map":
                        topical_map_rows.extend(rows)
                    else:
                        internal_link_targets.extend(rows)
            else:
                documents.append(
                    {"path": path, "kind": "reference", "text": text, "sha256": digest}
                )
                parsed = True

        manifest.append(
            {
                "path": path,
                "size": len(entry.data),
                "sha256": digest,
                "kind": kind,
                "parsed": parsed,
            }
        )

    # Conflicts: same file name in different directories (surfaced, FR-16).
    by_basename: dict[str, list[str]] = {}
    for entry in ordered:
        base = entry.path.rsplit("/", 1)[-1].lower()
        by_basename.setdefault(base, []).append(entry.path)
    for base in sorted(by_basename):
        paths = by_basename[base]
        if len(paths) > 1:
            add_conflict(
                f"Same file name '{base}' appears in multiple locations: "
                f"{', '.join(paths)}."
            )

    if not skill_paths:
        pack_warnings.append(
            "SKILL.md not found; pack name and version were derived from the "
            "source file name."
        )
    elif len(skill_paths) > 1:
        pack_warnings.append(
            f"Multiple SKILL.md files found; using '{skill_paths[0]}'."
        )
    if not brand_rules:
        pack_warnings.append(
            "No brand rules found (expected brand*.yml, brand*.yaml or brand*.json)."
        )
    if scripts:
        pack_warnings.append(
            "Imported scripts are stored for reference and are never executed."
        )

    default_name = Path(source_file).stem.strip() or "pack"
    if default_name.lower().endswith(".tar"):
        default_name = default_name[: -len(".tar")]
    name = (skill_name or default_name).strip() or "pack"
    version = (skill_version or "0.0.0").strip() or "0.0.0"

    pack = ImportedPack(
        name=name,
        version=version,
        version_hash="",
        source_file=source_file,
        files=[entry.path for entry in ordered],
        documents=documents,
        brand_rules=brand_rules,
        canonical_facts=canonical_facts,
        banned_terms=banned_terms,
        approved_claims=approved_claims,
        topical_map_rows=topical_map_rows,
        internal_link_targets=internal_link_targets,
        scoring_config=scoring_config,
        writer_handoff_template=writer_handoff_template,
        scripts=scripts,
        warnings=pack_warnings,
        conflicts=conflicts,
        manifest=manifest,
    )
    pack.version_hash = pack_version_hash(pack)
    return pack


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def import_pack(
    data: bytes,
    filename: str,
    *,
    max_total_uncompressed: int = DEFAULT_MAX_TOTAL_UNCOMPRESSED,
    max_files: int = DEFAULT_MAX_FILES,
) -> ImportedPack:
    """Import a context/skill pack archive (PRD FR-16).

    Accepts ZIP and ``.tar.gz``/``.tgz`` archives detected by **magic bytes**
    (``PK\\x03\\x04`` / gzip), not by ``filename``.  Entries are parsed fully
    in memory — nothing touches the filesystem.

    Safety (PRD FR-16/FR-24, §18 "Malicious ZIP/skill pack"): unsafe paths
    (absolute, ``..``, drive prefixes, NUL), symlinks/hardlinks, zip bombs
    (compression ratio > {ratio}x or oversized totals) and over-limit
    archives/files raise :class:`ValueError`; oversized single files are
    skipped with a warning.  Conflicts across files are surfaced in
    ``conflicts``, never silently reconciled.

    **Imported content is data and methodology, not authority to change
    application security (PRD FR-16).  Nothing in a pack is ever executed,
    evaluated, imported or obeyed — scripts are recorded as file paths only.**

    Args:
        data: Raw archive bytes.
        filename: Original upload name (used for the default pack name and
            extension-mismatch warnings only).
        max_total_uncompressed: Hard cap on total decompressed bytes.
        max_files: Hard cap on the number of files in the archive.

    Returns:
        The parsed :class:`ImportedPack` with manifest, warnings and conflicts.

    Raises:
        ValueError: The bytes are not a recognized archive, or the archive
            violates a path/size/count/compression safety rule.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ValueError("Archive data must be bytes.")
    if max_total_uncompressed <= 0 or max_files <= 0:
        raise ValueError("Import limits must be positive.")
    raw = bytes(data)
    detected = _detect_format(raw)

    warnings: list[str] = []
    lower_name = (filename or "").lower()
    if detected == "zip" and lower_name.endswith((".tar", ".tar.gz", ".tgz")):
        warnings.append(
            "Archive extension does not match the detected content (detected ZIP)."
        )
    elif detected == "tgz" and lower_name.endswith(".zip"):
        warnings.append(
            "Archive extension does not match the detected content (detected tar.gz)."
        )

    if detected == "zip":
        entries = _read_zip(
            raw, max_total_uncompressed=max_total_uncompressed, max_files=max_files
        )
    else:
        entries = _read_tar_gz(
            raw, max_total_uncompressed=max_total_uncompressed, max_files=max_files
        )
    pack_entries, entry_warnings = entries
    warnings.extend(entry_warnings)
    return _build_pack(
        pack_entries, source_file=filename or "pack.zip", warnings=warnings
    )


def parse_pack_directory(
    root_path: Any,
    *,
    max_total_uncompressed: int = DEFAULT_MAX_TOTAL_UNCOMPRESSED,
    max_files: int = DEFAULT_MAX_FILES,
) -> ImportedPack:
    """Import a pack from an already-extracted directory (development helper).

    Applies the same path/size/count rules as :func:`import_pack`.  Symlinks
    are never followed — they are skipped with a warning so a link cannot pull
    files from outside the pack directory (PRD FR-24).
    """
    root = Path(root_path)
    if not root.exists():
        raise ValueError(f"Directory '{root}' does not exist.")
    if not root.is_dir():
        raise ValueError(f"'{root}' is not a directory.")
    if max_total_uncompressed <= 0 or max_files <= 0:
        raise ValueError("Import limits must be positive.")

    warnings: list[str] = []
    root_resolved = root.resolve()
    candidates: list[tuple[str, Path]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            warnings.append(
                f"Skipped symbolic link '{relative}' (links are never followed "
                "or imported)."
            )
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            continue
        safe = _safe_member_path(relative, origin="directory")
        try:
            resolved = path.resolve()
        except OSError:
            warnings.append(f"File '{safe}' could not be resolved and was skipped.")
            continue
        if not resolved.is_relative_to(root_resolved):
            warnings.append(
                f"File '{safe}' resolves outside the pack directory and was skipped."
            )
            continue
        candidates.append((safe, path))

    if len(candidates) > max_files:
        raise ValueError(
            f"The directory contains {len(candidates)} files which exceeds "
            f"the limit of {max_files}."
        )

    entries: list[_FileEntry] = []
    total = 0
    for relative, path in sorted(candidates):
        payload = _read_file_capped(path, relative, warnings)
        if payload is None:
            continue
        total += len(payload)
        if total > max_total_uncompressed:
            raise ValueError(
                f"Uncompressed content exceeds the {max_total_uncompressed}-byte "
                "total limit."
            )
        entries.append(_FileEntry(path=relative, data=payload))
    return _build_pack(entries, source_file=str(root_path), warnings=warnings)
