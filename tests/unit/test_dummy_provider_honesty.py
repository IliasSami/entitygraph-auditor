"""Honesty tests for the deterministic (zero-API) provider.

``DummyDeterministicProvider`` is the default provider in deterministic-only
mode, so whatever it returns lands in every real report. These tests pin that it
never invents facts: no canned "verified" claim, no content-independent triples,
no fabricated coverage, no boilerplate recommendation, and no invented EAV
attribute values. (Historically it returned a fixed "Engineered for
high-concurrency transactional workloads." claim marked *verified* with a fake
source id, plus "Core Architecture / failover" recommendations for every page.)
"""

from __future__ import annotations

from ega_providers.dummy import DummyDeterministicProvider


def test_claims_are_never_marked_verified() -> None:
    provider = DummyDeterministicProvider()

    assert provider._extract_claims("A polite page with no figures at all.")["claims"] == []

    out = provider._extract_claims("We reduce cooling costs by up to 40% and lead the market.")
    assert out["claims"], "the numeric claim should be detected"
    for claim in out["claims"]:
        assert claim["verification_state"] == "unverified"
        assert claim["requires_substantiation"] is True
        assert claim["evidence_source_ids"] == []


def test_claims_never_include_the_retired_canned_claim() -> None:
    provider = DummyDeterministicProvider()
    statements = [c["statement"].lower() for c in provider._extract_claims("Anything at all.")["claims"]]
    assert not any("high-concurrency transactional" in s for s in statements)


def test_triples_are_content_derived_only() -> None:
    provider = DummyDeterministicProvider()

    assert provider._extract_triples("A short, vague paragraph about nothing.")["triples"] == []

    out = provider._extract_triples("Acme provides enterprise data migration for banks.")
    assert [t["object_"] for t in out["triples"]] == ["enterprise data migration for banks"]
    for triple in out["triples"]:
        assert triple["object_"] not in {"high performance", "security standards"}


def test_coverage_is_not_fabricated() -> None:
    provider = DummyDeterministicProvider()
    assert provider._coverage("Some content.")["coverage_rows"] == []


def test_recommendations_are_derived_from_real_gaps() -> None:
    provider = DummyDeterministicProvider()

    empty = provider._handoff("content", "Central Entity: X\nGate Status: pass\n")
    assert empty["recommendations"] == []
    assert empty["measurement_plan"] == []

    prompt = (
        "Central Entity: X\n"
        "Gate Status: pass_with_fixes\n"
        "Weaknesses: vague pricing\n"
        "Key Gaps: 3 of 6 required attributes have no explicit value (price, process, guarantee)\n"
        "<untrusted_content>\ncontent\n</untrusted_content>\n"
    )
    out = provider._handoff("content", prompt)

    assert out["recommendations"], "real gaps must yield recommendations"
    joined = " ".join(r["what"] for r in out["recommendations"])
    assert "required attributes" in joined
    assert "failover" not in joined.lower()
    # Parenthesis-aware split must keep the gap text intact.
    assert any("price, process, guarantee" in r["what"] for r in out["recommendations"])
    # FR-18: the measurement plan is carried from the real gaps.
    assert out["measurement_plan"]


def test_eav_never_invents_attribute_values() -> None:
    provider = DummyDeterministicProvider()
    result = provider._extract_entities_eav("A page about nothing in particular.")
    attributes = {row["attribute"] for row in result["eav_rows"]}
    assert "protocol" not in attributes
    assert "encryption" not in attributes
    assert "category" not in attributes


def test_known_standards_are_surfaced_as_trust_entities() -> None:
    provider = DummyDeterministicProvider()
    result = provider._extract_entities_eav("We are SOC-2 Type II compliant and AES-256 encrypted.")
    standards = {e["canonical_name"] for e in result["entities"] if e["kind"] == "standard"}
    assert {"SOC 2", "AES-256"} <= standards
