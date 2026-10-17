"""Unit tests for the context/skill pack importer (PRD FR-16, FR-24, §18).

All archives are built in memory (``io.BytesIO``) — nothing is downloaded or
written to disk except the temporary directories used by the
``parse_pack_directory`` tests.  The suite covers the happy path (skill header,
brand rules, canonical facts, claims, topical map, links, scoring config,
handoff template, source registry), the FR-16 "scripts are never executed"
contract, and the FR-24 "reject unsafe archive paths and zip bombs" guards.
"""

from __future__ import annotations

import gzip
import io
import os
import stat
import tarfile
import zipfile
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from ega_api.services.packs import (
    ImportedPack,
    _safe_member_path,
    import_pack,
    pack_version_hash,
    parse_pack_directory,
)

# --------------------------------------------------------------------------- #
# Fixtures: in-memory archives
# --------------------------------------------------------------------------- #

SKILL = b"""---
name: acme-audit
version: 1.2.3
---
# Acme Audit

Audit methodology for Acme.
"""
BRAND = b"""name: Acme
voice: direct
banned_terms:
  hype: unsubstantiated superlative
  revolutionary: requires evidence
"""
FACTS = b'{"founded": "1999", "hq": "Oslo"}'
CLAIMS = b"""- claim: Founded in 1999
  source: https://example.com/about
"""
TOPICAL = b'query,intent\n"audit ai",informational\n'
LINKS = b"url,label\nhttps://example.com/,Acme\n"
SCORING = b"max_score: 100\nweight_evidence: 0.4\n"
SOURCES = b"# Sources\n\n- https://example.com/about\n"
HANDOFF = b"# Handoff\n\nWrite concise intros.\n"
HELPER = b"print('reference only')\n"
BUILD = b"#!/bin/sh\necho build\n"
README = b"# Docs\n\nPack documentation.\n"

HAPPY_FILES: dict[str, bytes] = {
    "SKILL.md": SKILL,
    "brand.yml": BRAND,
    "facts.json": FACTS,
    "claims.yml": CLAIMS,
    "topical_map.csv": TOPICAL,
    "links.csv": LINKS,
    "scoring.yml": SCORING,
    "sources.md": SOURCES,
    "writer_handoff.md": HANDOFF,
    "helper.py": HELPER,
    "scripts/build.sh": BUILD,
    "docs/README.md": README,
}

SYMLINK_MODE = 0o120777 << 16


def zip_bytes(
    entries: Sequence[tuple[str, bytes]],
    *,
    mode: int = zipfile.ZIP_DEFLATED,
    attrs: Mapping[str, int] | None = None,
) -> bytes:
    """Build ZIP bytes from ``(name, data)`` pairs, optionally setting attrs."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", mode) as archive:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = mode
            info.external_attr = (attrs or {}).get(name, 0)
            archive.writestr(info, data)
    return buffer.getvalue()


def make_zip(files: Mapping[str, bytes], **kwargs: Any) -> bytes:
    """ZIP archive of ``files`` (insertion order preserved)."""
    return zip_bytes(list(files.items()), **kwargs)


def tar_gz_bytes(members: Sequence[tuple[tarfile.TarInfo, bytes | None]]) -> bytes:
    """Build ``.tar.gz`` bytes from explicit (TarInfo, payload) members."""
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as archive:
            for info, data in members:
                archive.addfile(info, None if data is None else io.BytesIO(data))
    return buffer.getvalue()


def make_tar_gz(files: Mapping[str, bytes]) -> bytes:
    """``.tar.gz`` archive of ``files`` as regular file members."""
    members = []
    for name, data in files.items():
        info = tarfile.TarInfo(name)
        info.size = len(data)
        info.mtime = 0
        members.append((info, data))
    return tar_gz_bytes(members)


def archive_entry(pack: ImportedPack, path: str) -> dict:
    """Manifest entry for ``path`` (fails the test when absent)."""
    return next(entry for entry in pack.manifest if entry["path"] == path)


# --------------------------------------------------------------------------- #
# Happy path (FR-16 import manifest contract)
# --------------------------------------------------------------------------- #


def test_import_pack_builds_the_full_parsed_pack() -> None:
    pack = import_pack(make_zip(HAPPY_FILES), "acme.zip")

    # Identity from SKILL.md front matter and the source file name.
    assert isinstance(pack, ImportedPack)
    assert pack.name == "acme-audit"
    assert pack.version == "1.2.3"
    assert pack.source_file == "acme.zip"

    # Manifest / file inventory (paths relative, forward slashes, sorted).
    assert pack.files == sorted(HAPPY_FILES)
    assert len(pack.manifest) == len(HAPPY_FILES)
    assert all(len(entry["sha256"]) == 64 for entry in pack.manifest)
    assert archive_entry(pack, "scripts/build.sh")["kind"] == "script"
    assert archive_entry(pack, "scripts/build.sh")["parsed"] is False
    assert archive_entry(pack, "SKILL.md")["parsed"] is True

    # Structured content extraction.
    assert pack.brand_rules[0]["path"] == "brand.yml"
    assert pack.brand_rules[0]["rules"]["voice"] == "direct"
    assert pack.banned_terms == [
        {"term": "hype", "reason": "unsubstantiated superlative"},
        {"term": "revolutionary", "reason": "requires evidence"},
    ]
    assert pack.canonical_facts == [
        {"key": "founded", "value": "1999"},
        {"key": "hq", "value": "Oslo"},
    ]
    assert pack.approved_claims == [
        {"claim": "Founded in 1999", "source": "https://example.com/about"}
    ]
    assert pack.topical_map_rows == [{"query": "audit ai", "intent": "informational"}]
    assert pack.internal_link_targets == [
        {"url": "https://example.com/", "label": "Acme"}
    ]
    assert pack.scoring_config == {"max_score": 100, "weight_evidence": 0.4}
    assert pack.writer_handoff_template is not None
    assert "Write concise intros" in pack.writer_handoff_template
    assert {doc["kind"] for doc in pack.documents} == {
        "skill",
        "source_registry",
        "reference",
    }

    # Scripts recorded as paths only; conflicts/hash/warnings are honest.
    assert pack.scripts == ["helper.py", "scripts/build.sh"]
    assert pack.conflicts == []
    assert len(pack.version_hash) == 64
    assert pack.version_hash == pack_version_hash(pack)
    assert pack.warnings == [
        "Imported scripts are stored for reference and are never executed."
    ]


def test_version_hash_is_stable_across_archive_order() -> None:
    files = {"SKILL.md": SKILL, "a.md": b"# A\n", "b.md": b"# B\n"}
    first = import_pack(make_zip(files), "pack.zip")
    reversed_files = dict(reversed(list(files.items())))
    second = import_pack(make_zip(reversed_files), "pack.zip")

    assert first.version_hash == second.version_hash
    assert first.files == second.files
    assert first.manifest == second.manifest


def test_version_hash_changes_when_content_changes() -> None:
    files = {"SKILL.md": SKILL, "a.md": b"# A\n"}
    original = import_pack(make_zip(files), "pack.zip")
    changed = dict(files, **{"a.md": b"# A changed\n"})
    assert import_pack(make_zip(changed), "pack.zip").version_hash != original.version_hash


def test_tar_gz_import_works() -> None:
    pack = import_pack(
        make_tar_gz({"SKILL.md": SKILL, "facts.json": b'{"founded": "1999"}'}),
        "pack.tgz",
    )
    assert pack.name == "acme-audit"
    assert pack.files == ["SKILL.md", "facts.json"]
    assert pack.canonical_facts == [{"key": "founded", "value": "1999"}]


def test_format_is_detected_by_magic_bytes_not_extension() -> None:
    zip_named_targz = import_pack(make_zip({"SKILL.md": SKILL}), "pack.tar.gz")
    assert zip_named_targz.name == "acme-audit"
    assert any("extension does not match" in w for w in zip_named_targz.warnings)

    tgz_named_zip = import_pack(make_tar_gz({"SKILL.md": SKILL}), "pack.zip")
    assert tgz_named_zip.name == "acme-audit"
    assert any("extension does not match" in w for w in tgz_named_zip.warnings)


def test_empty_archive_warns_and_falls_back_to_the_file_name() -> None:
    pack = import_pack(make_zip({}), "empty-pack.zip")
    assert pack.name == "empty-pack"
    assert pack.version == "0.0.0"
    assert pack.files == []
    assert any("Pack is empty" in warning for warning in pack.warnings)
    assert any("SKILL.md not found" in warning for warning in pack.warnings)
    assert len(pack.version_hash) == 64
    assert pack.version_hash == pack_version_hash(pack)


# --------------------------------------------------------------------------- #
# FR-16: scripts are data, never executed
# --------------------------------------------------------------------------- #


def test_scripts_are_recorded_but_never_executed(tmp_path: Any) -> None:
    marker = tmp_path / "pwned-marker"
    files = {
        "SKILL.md": SKILL,
        "scripts/build.sh": f"#!/bin/sh\ntouch {marker}\n".encode(),
        "helper.py": b"raise SystemExit('this file must never run')\n",
    }
    pack = import_pack(make_zip(files), "pack.zip")

    assert pack.scripts == ["helper.py", "scripts/build.sh"]
    assert "never executed" in " ".join(pack.warnings)
    assert not marker.exists()
    assert archive_entry(pack, "scripts/build.sh")["kind"] == "script"
    assert archive_entry(pack, "scripts/build.sh")["parsed"] is False
    assert "scripts/build.sh" in pack.files


# --------------------------------------------------------------------------- #
# FR-24: unsafe archive paths
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name",
    ["../evil.txt", "../../etc/passwd", "a/../../evil.txt", "..\\..\\evil.txt"],
)
def test_zip_slip_traversal_is_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="traversal"):
        import_pack(make_zip({name: b"x"}), "pack.zip")


@pytest.mark.parametrize("name", ["/etc/passwd", "/tmp/evil.md"])
def test_absolute_paths_are_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="absolute"):
        import_pack(make_zip({name: b"x"}), "pack.zip")


@pytest.mark.parametrize("name", ["C:\\Windows\\evil.dll", "D:/data/evil.md"])
def test_windows_drive_prefixes_are_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="drive-prefixed"):
        import_pack(make_zip({name: b"x"}), "pack.zip")


@pytest.mark.parametrize(
    "name",
    ["evil\x00.md", "", "..", "/abs.md", "C:/x.md", "./..", "..\\..\\x.md"],
)
def test_unsafe_member_paths_are_refused_by_the_gate(name: str) -> None:
    with pytest.raises(ValueError):
        _safe_member_path(name, origin="test")


def test_safe_member_paths_are_normalized() -> None:
    assert _safe_member_path("./docs/./note.md", origin="test") == "docs/note.md"
    assert _safe_member_path("docs\\note.md", origin="test") == "docs/note.md"


# --------------------------------------------------------------------------- #
# FR-24: unsafe archive members (links, devices)
# --------------------------------------------------------------------------- #


def test_zip_symlink_member_is_rejected() -> None:
    payload = zip_bytes(
        [("link.md", b"../outside.md")], attrs={"link.md": SYMLINK_MODE}
    )
    with pytest.raises(ValueError, match="symbolic link"):
        import_pack(payload, "pack.zip")
    assert stat.S_ISLNK(SYMLINK_MODE >> 16)


def test_tar_symlink_member_is_rejected() -> None:
    link = tarfile.TarInfo("link.md")
    link.type = tarfile.SYMTYPE
    link.linkname = "../outside.md"
    with pytest.raises(ValueError, match="link"):
        import_pack(tar_gz_bytes([(link, None)]), "pack.tar.gz")


def test_tar_hardlink_member_is_rejected() -> None:
    link = tarfile.TarInfo("hard.md")
    link.type = tarfile.LNKTYPE
    link.linkname = "real.md"
    with pytest.raises(ValueError, match="link"):
        import_pack(tar_gz_bytes([(link, None)]), "pack.tar.gz")


def test_tar_device_member_is_rejected() -> None:
    device = tarfile.TarInfo("dev")
    device.type = tarfile.CHRTYPE
    device.devmajor = 1
    device.devminor = 3
    with pytest.raises(ValueError, match="unsupported type"):
        import_pack(tar_gz_bytes([(device, None)]), "pack.tar.gz")


# --------------------------------------------------------------------------- #
# FR-24: bombs and size limits
# --------------------------------------------------------------------------- #


def test_zip_bomb_compression_ratio_is_rejected() -> None:
    with pytest.raises(ValueError, match="compression ratio"):
        import_pack(make_zip({"bomb.txt": b"A" * 1_000_000}), "pack.zip")


def test_targz_decompression_bomb_is_rejected() -> None:
    payload = make_tar_gz({"big.bin": b"\x00" * 2_000_000})
    with pytest.raises(ValueError, match="limit"):
        import_pack(payload, "pack.tar.gz", max_total_uncompressed=100_000)


def test_oversized_single_file_is_skipped_with_a_warning() -> None:
    files = {"SKILL.md": SKILL, "huge.bin": b"A" * 10_000_001}
    pack = import_pack(make_zip(files, mode=zipfile.ZIP_STORED), "pack.zip")

    assert "huge.bin" not in pack.files
    assert not any(entry["path"] == "huge.bin" for entry in pack.manifest)
    assert any("per-file limit and was skipped" in w for w in pack.warnings)


def test_file_count_limit_is_enforced() -> None:
    files = {f"note{i}.md": b"x" for i in range(4)}
    with pytest.raises(ValueError, match="exceeds the limit of 3"):
        import_pack(make_zip(files), "pack.zip", max_files=3)


def test_total_uncompressed_limit_is_enforced() -> None:
    files = {"a.txt": b"A" * 150, "b.txt": b"B" * 150}
    with pytest.raises(ValueError, match="total limit"):
        import_pack(make_zip(files), "pack.zip", max_total_uncompressed=200)


@pytest.mark.parametrize("data", [b"", b"not an archive at all", b'{"json": true}'])
def test_non_archive_bytes_are_rejected(data: bytes) -> None:
    with pytest.raises(ValueError, match="Unrecognized archive format"):
        import_pack(data, "pack.zip")


def test_truncated_zip_is_rejected() -> None:
    with pytest.raises(ValueError, match="malformed"):
        import_pack(b"PK\x03\x04junkjunk", "pack.zip")


@pytest.mark.parametrize("data", ["a string", 123, None])
def test_non_bytes_input_is_rejected(data: Any) -> None:
    with pytest.raises(ValueError, match="must be bytes"):
        import_pack(data, "pack.zip")


@pytest.mark.parametrize(
    "kwargs", [{"max_files": 0}, {"max_total_uncompressed": 0}]
)
def test_import_limits_must_be_positive(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        import_pack(make_zip({}), "pack.zip", **kwargs)


# --------------------------------------------------------------------------- #
# Conflicts and parse failures (surfaced, never silently reconciled)
# --------------------------------------------------------------------------- #


def test_conflicting_canonical_facts_are_surfaced() -> None:
    files = {"facts.json": b'{"founded": "1999"}', "facts.yml": b"founded: '2001'\n"}
    pack = import_pack(make_zip(files), "pack.zip")

    assert any("Conflicting canonical fact 'founded'" in c for c in pack.conflicts)
    assert len(pack.canonical_facts) == 2


def test_same_basename_in_two_directories_is_surfaced() -> None:
    files = {"a/rules.yml": b"x: 1\n", "b/rules.yml": b"y: 2\n"}
    pack = import_pack(make_zip(files), "pack.zip")
    assert any("Same file name 'rules.yml'" in c for c in pack.conflicts)


def test_unparseable_json_is_kept_as_raw_text_with_a_warning() -> None:
    pack = import_pack(make_zip({"facts.json": b"{not json"}), "pack.zip")

    assert any("Could not parse 'facts.json' as JSON" in w for w in pack.warnings)
    entry = archive_entry(pack, "facts.json")
    assert entry["kind"] == "facts"
    assert entry["parsed"] is False
    assert pack.canonical_facts == []
    assert any(
        doc["path"] == "facts.json" and doc["text"] == "{not json"
        for doc in pack.documents
    )


def test_binary_files_are_recorded_but_not_parsed() -> None:
    pack = import_pack(make_zip({"logo.bin": b"\x00\x01\x02\x03"}), "pack.zip")
    assert archive_entry(pack, "logo.bin")["parsed"] is False
    assert any("binary" in warning for warning in pack.warnings)


# --------------------------------------------------------------------------- #
# Directory import (development helper)
# --------------------------------------------------------------------------- #


def test_directory_import_parses_a_pack(tmp_path: Any) -> None:
    root = tmp_path / "pack"
    (root / "docs").mkdir(parents=True)
    (root / "SKILL.md").write_bytes(SKILL)
    (root / "docs" / "note.md").write_text("# Note\n", encoding="utf-8")

    pack = parse_pack_directory(root)
    assert pack.name == "acme-audit"
    assert pack.files == ["SKILL.md", "docs/note.md"]
    assert pack.source_file == str(root)
    assert pack.version_hash == pack_version_hash(pack)


def test_directory_symlinks_are_skipped_and_never_followed(tmp_path: Any) -> None:
    root = tmp_path / "pack"
    root.mkdir()
    (root / "SKILL.md").write_bytes(SKILL)
    outside = tmp_path / "secret.md"
    outside.write_text("TOP SECRET", encoding="utf-8")
    os.symlink(outside, root / "linked.md")

    pack = parse_pack_directory(root)
    assert "linked.md" not in pack.files
    assert any("Skipped symbolic link 'linked.md'" in w for w in pack.warnings)
    assert all("TOP SECRET" not in doc["text"] for doc in pack.documents)


def test_directory_import_rejects_a_missing_directory(tmp_path: Any) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        parse_pack_directory(tmp_path / "missing")


def test_directory_import_rejects_a_file_path(tmp_path: Any) -> None:
    target = tmp_path / "file.txt"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not a directory"):
        parse_pack_directory(target)
