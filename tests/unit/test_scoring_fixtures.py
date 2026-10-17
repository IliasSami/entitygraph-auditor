"""Fixture loader for the deterministic scoring test-suite (PRD §9).

``tests/fixtures/scoring/builders.py`` is *outside* the installed packages, so
it cannot be imported by module name. This module loads it once via
``importlib`` relative to ``__file__`` and re-exports the builders. The other
``test_scoring_*`` / ``test_rules_*`` modules import them from here (the repo
already uses this pattern for ``test_export_fixtures``).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_BUILDERS_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "scoring" / "builders.py"
)


def _load_builders(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("ega_scoring_test_builders", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load scoring fixture builders from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BUILDERS = _load_builders(_BUILDERS_PATH)

FIXTURES_DIR: Path = _BUILDERS.FIXTURES_DIR
brand_pack = _BUILDERS.brand_pack
build_finding = _BUILDERS.build_finding
empty_state = _BUILDERS.empty_state
gate_state = _BUILDERS.gate_state
load_json = _BUILDERS.load_json
parse_document = _BUILDERS.parse_document
rich_state = _BUILDERS.rich_state


def test_fixture_builders_module_loads() -> None:
    """The fixture builders module is discoverable from ``__file__``."""
    assert _BUILDERS_PATH.exists()
    assert isinstance(FIXTURES_DIR, Path)
    assert FIXTURES_DIR.name == "scoring"


def test_brand_pack_fixture_shape() -> None:
    """The brand pack fixture carries rules, banned terms and canonical facts."""
    pack = brand_pack()
    assert pack["pack_id"] == "pack-acme-001"
    assert any(term["severity"] == "critical" for term in pack["banned_terms"])
    assert pack["canonical_facts"][0]["canonical_value"] == "99.99%"
    assert pack["internal_links"][0]["target_url"] == "/guides/streaming-data"


def test_rich_state_fixture_is_fully_populated() -> None:
    """The rich fixture state exposes every input the core scorers consult."""
    state = rich_state()
    assert state.page_type.value == "service"
    assert state.central_entity == "Acme Analytics Engine"
    assert len(state.entities) == 7
    assert len(state.eav_rows) == 7
    assert len(state.triples) == 8
    assert len(state.fanout_queries) == 5
    assert len(state.coverage_rows) == 5
    assert len(state.claims) == 2
    assert len(state.evidence_sources) == 2
    assert state.parsed_doc is not None and state.parsed_doc.passages
    assert state.context_packs and state.context_packs[0]["pack_id"] == "pack-acme-001"


def test_empty_state_fixture_has_no_inputs() -> None:
    """The empty fixture state carries no assessable inputs at all."""
    state = empty_state()
    assert state.parsed_doc is None
    assert not state.entities
    assert not state.coverage_rows
    assert not state.claims
    assert not state.context_packs


def test_rich_state_overrides_are_applied() -> None:
    """Keyword overrides replace fixture defaults (and nothing else)."""
    from ega_schemas import PageType

    state = rich_state(page_type=PageType.ARTICLE, claims=[])
    assert state.page_type.value == "article"
    assert state.claims == []
    assert len(state.entities) == 7


def test_gate_state_is_minimal_and_overridable() -> None:
    """The gate-only builder returns a minimal, fully-overridable namespace."""
    from ega_schemas.enums import SensitivityTier

    state = gate_state("hello world", claims=[])
    assert state.content == "hello world"
    assert state.sensitivity.value == "ordinary"
    assert state.claims == []
    state2 = gate_state("x", sensitivity=SensitivityTier.REGULATED)
    assert state2.sensitivity.value == "regulated"


def test_parse_document_helper_returns_passages() -> None:
    """The parse helper produces a ParsedDocument with retrievable passages."""
    doc = parse_document("# Title\n\nFirst sentence. Second sentence.")
    assert doc.raw_text.startswith("# Title")
    assert doc.passages
    assert doc.normalized_text


def test_build_finding_helper_shape() -> None:
    """The finding helper builds an open high-severity schema Finding."""
    finding = build_finding("f-x", severity="critical", impact=5, effort=1)
    assert finding.finding_id == "f-x"
    assert finding.severity.value == "critical"
    assert finding.status.value == "open"
    assert finding.impact == 5
    assert finding.effort == 1


def test_load_json_rejects_missing_file() -> None:
    """Loading a missing fixture raises rather than silently returning empty."""
    import pytest

    with pytest.raises(FileNotFoundError):
        load_json("does-not-exist.json")
