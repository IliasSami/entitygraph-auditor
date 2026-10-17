"""Honesty tests for the deterministic content brief generator (PRD: no fabricated evidence).

The brief generator is a template engine, not a research engine. These tests pin
that it never claims to have consulted a source it did not (e.g. "Google PAA",
"Perplexity"), never invents a "verified" fact when the active context pack has
none, and always labels its output as an internal editorial heuristic.
"""

from __future__ import annotations

import pytest
from ega_api.services.briefs import generate_content_brief

FABRICATED_ATTRIBUTIONS = ("Google PAA", "Perplexity", "AI Citation Gap", "Entity Hub")


def test_ungrounded_brief_has_no_fabricated_source_attributions() -> None:
    brief = generate_content_brief(target_query="roof inspection cost", location="Austin, TX")

    assert brief["grounded"] is False
    for source in brief["sources"]:
        assert source["source"] not in FABRICATED_ATTRIBUTIONS


def test_ungrounded_brief_never_claims_a_fact_is_verified() -> None:
    brief = generate_content_brief(target_query="roof inspection cost")

    # The fact-type source is a placeholder, not a verified fact.
    fact_sources = [s for s in brief["sources"] if s["type"] == "fact"]
    assert fact_sources, "expected a fact-type source"
    for source in fact_sources:
        assert source["tag"] != "Verified fact"
        assert "Unverified" in source["source"] or "placeholder" in source["source"].lower()

    # Section facts must say they are placeholders, not fabricated claims.
    for section in brief["sections"]:
        for fact in section["facts"]:
            assert "No verified fact" in fact or "No brand-rule fact" in fact


def test_brief_always_carries_a_disclaimer() -> None:
    for grounded in (False, True):
        pack = (
            {"canonical_facts": [{"key": "founded", "value": "1999"}]} if grounded else None
        )
        brief = generate_content_brief(
            target_query="bookkeeping for creative agencies", context_pack_data=pack
        )
        assert isinstance(brief["disclaimer"], str)
        assert brief["disclaimer"].strip()
        assert "internal editorial heuristic" in brief["disclaimer"].lower()


def test_grounded_brief_uses_real_pack_facts_and_labels_them() -> None:
    pack = {
        "canonical_facts": [
            {"key": "founded", "value": "1999"},
            {"key": "headquarters", "value": "Oslo"},
        ],
        "brand_rules": [{"statement": "Never promise guaranteed outcomes"}],
        "banned_terms": ["best in the world"],
    }
    brief = generate_content_brief(
        target_query="bookkeeping for creative agencies", context_pack_data=pack
    )

    assert brief["grounded"] is True
    # Real pack facts surface verbatim in the fact-type source.
    fact_sources = [s for s in brief["sources"] if s["type"] == "fact"]
    assert fact_sources[0]["source"] == "Context pack · canonical fact"
    assert "founded" in fact_sources[0]["title"]

    # Banned terms from the pack are carried into the lexicon avoid list.
    assert "best in the world" in brief["lexicon"]["avoid"]

    # Lexicon "include" is limited to the real query + pack-derived heads.
    assert "bookkeeping for creative agencies" in brief["lexicon"]["include"]


@pytest.mark.parametrize("query,expected", [
    ("how to choose a bookkeeper", "Informational / Educational"),
    ("bookkeeping pricing per month", "Commercial / Transactional"),
    ("best bookkeeping agency", "Commercial / Advisory"),
])
def test_intent_classification_is_deterministic(query: str, expected: str) -> None:
    brief = generate_content_brief(target_query=query)
    assert brief["intent"] == expected


def test_ungrounded_brief_does_not_invent_a_brand_or_location() -> None:
    """With no brand/location supplied the generator uses neutral placeholders.

    It must never inject a specific company name or city, nor invent "standard
    pricing tiers" for an unknown market.
    """
    brief = generate_content_brief(target_query="roof inspection cost")

    assert brief["brand_name"] == "Your brand"
    assert brief["location"] == "your market"

    serialized = repr(brief)
    assert "Aentio Advisory" not in serialized
    assert "Austin, TX" not in serialized

    fact = next(s for s in brief["sources"] if s["type"] == "fact")
    assert "No verified pricing fact" in fact["title"]
