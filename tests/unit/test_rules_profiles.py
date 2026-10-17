"""Unit tests for page-type profiles and the attribute registry (PRD §5, §9.4).

PRD §5 requires a profile for every one of the 16 page types, and PRD §9.4 pins
the four composite weight columns exactly. These tests lock the registry
size, each page type's preset, the precise weight fractions, and the attribute
merge/dedup rules (including the FR-12 location additions).
"""

from __future__ import annotations

import pytest
from ega_schemas.entities import EAVRow
from ega_schemas.enums import EAVStatus, IntentClass, PageType

from auditor.rules.attributes import (
    REQUIRED_ATTRIBUTES,
    attributes_for,
    satisfied_attribute_keys,
)
from auditor.rules.page_profiles import (
    PAGE_PROFILES,
    WEIGHT_PRESETS,
    get_profile,
    weight_preset,
)

EXPECTED_PRESETS = {
    PageType.GLOSSARY: "informational",
    PageType.ARTICLE: "informational",
    PageType.DOCS: "informational",
    PageType.TRUST_POLICY: "informational",
    PageType.GENERAL: "informational",
    PageType.LISTICLE: "listicle",
    PageType.COMPARISON: "listicle",
    PageType.HOMEPAGE: "commercial",
    PageType.ABOUT: "commercial",
    PageType.SERVICE: "commercial",
    PageType.LOCAL_SERVICE: "commercial",
    PageType.SAAS_B2B: "commercial",
    PageType.INTEGRATION: "commercial",
    PageType.PAID_LANDING: "commercial",
    PageType.PRODUCT_CATEGORY: "commercial",
    PageType.CASE_STUDY: "case_study",
}

#: Exact PRD §9.4 composite weights (fractions summing to 1.0).
PRD_WEIGHTS = {
    "informational": {"EOS": 0.15, "ERS": 0.15, "KGR": 0.10, "FCS": 0.15, "PRS": 0.15, "CWS": 0.20, "HRS": 0.10},
    "listicle": {"EOS": 0.15, "ERS": 0.10, "KGR": 0.15, "FCS": 0.15, "PRS": 0.15, "CWS": 0.20, "HRS": 0.10},
    "commercial": {"EOS": 0.15, "ERS": 0.15, "KGR": 0.15, "FCS": 0.10, "PRS": 0.15, "CWS": 0.15, "HRS": 0.15},
    "case_study": {"EOS": 0.10, "ERS": 0.15, "KGR": 0.10, "FCS": 0.05, "PRS": 0.10, "CWS": 0.35, "HRS": 0.15},
}


# ---------------------------------------------------------------- profiles ---


def test_registry_covers_all_sixteen_page_types() -> None:
    """PRD §5 mandates a profile for every PageType value."""
    assert len(PAGE_PROFILES) == 16
    assert set(PAGE_PROFILES) == set(PageType)


def test_weight_presets_are_the_four_prd_columns() -> None:
    assert WEIGHT_PRESETS == ("informational", "listicle", "commercial", "case_study")


@pytest.mark.parametrize("page_type,expected", sorted(EXPECTED_PRESETS.items(), key=lambda x: x[0].value))
def test_every_page_type_maps_to_its_preset(page_type: PageType, expected: str) -> None:
    assert get_profile(page_type).score_preset == expected


def test_every_profile_is_well_formed() -> None:
    """Each profile carries descriptive content, not placeholders."""
    for page_type, profile in PAGE_PROFILES.items():
        assert profile.page_type is page_type
        assert profile.label.strip(), page_type.value
        assert profile.expected_central_entity_desc.strip(), page_type.value
        assert profile.likely_intents, page_type.value
        assert profile.expected_answer_shapes, page_type.value
        assert profile.common_failure_patterns, page_type.value
        assert profile.relevancy_penalties, page_type.value
        assert profile.score_preset in WEIGHT_PRESETS


def test_profile_required_attributes_match_the_registry() -> None:
    """A profile's required attributes are exactly the page-type registry slots."""
    for page_type, profile in PAGE_PROFILES.items():
        expected = tuple(spec.key for spec in REQUIRED_ATTRIBUTES.get(page_type, []))
        assert profile.required_attributes == expected, page_type.value


def test_only_local_service_is_local_relevant() -> None:
    """FR-12 local relevance is exclusive to the location-specific page type."""
    local = [pt for pt, prof in PAGE_PROFILES.items() if prof.local_relevant]
    assert local == [PageType.LOCAL_SERVICE]


def test_only_glossary_requires_an_early_definition() -> None:
    early = [pt for pt, prof in PAGE_PROFILES.items() if prof.glossary_early_definition]
    assert early == [PageType.GLOSSARY]


def test_get_profile_override_changes_only_the_preset() -> None:
    """An override swaps the weight column but keeps every other attribute."""
    base = get_profile(PageType.SERVICE)
    over = get_profile(PageType.SERVICE, "case_study")
    assert base.score_preset == "commercial"
    assert over.score_preset == "case_study"
    assert over.label == base.label
    assert over.likely_intents == base.likely_intents
    assert over.required_attributes == base.required_attributes


def test_get_profile_rejects_an_unknown_override() -> None:
    with pytest.raises(ValueError, match="Unknown score preset"):
        get_profile(PageType.SERVICE, "bogus")


def test_get_profile_same_preset_short_circuits() -> None:
    profile = get_profile(PageType.SERVICE, "commercial")
    assert profile is get_profile(PageType.SERVICE)


# ----------------------------------------------------------- weight tables ---


@pytest.mark.parametrize("preset", ["informational", "listicle", "commercial", "case_study"])
def test_weight_preset_matches_prd_exactly(preset: str) -> None:
    """The AVR weight table must equal the PRD §9.4 column, to the decimal."""
    assert weight_preset(preset) == PRD_WEIGHTS[preset]
    assert sum(weight_preset(preset).values()) == pytest.approx(1.0)


def test_weight_preset_returns_a_copy() -> None:
    """Callers cannot corrupt the shared table through the accessor."""
    table = weight_preset("commercial")
    table["EOS"] = 99.0
    assert weight_preset("commercial")["EOS"] == 0.15


def test_weight_preset_rejects_unknown_preset() -> None:
    with pytest.raises(ValueError, match="Unknown score preset"):
        weight_preset("nope")


def test_case_study_is_cws_heavy_and_fcs_light() -> None:
    """The case-study column weights CWS at 35% and FCS at 5% (PRD §9.4)."""
    table = weight_preset("case_study")
    assert table["CWS"] == 0.35
    assert table["FCS"] == 0.05


# -------------------------------------------------------------- attributes ---


def test_service_required_attributes() -> None:
    keys = [spec.key for spec in REQUIRED_ATTRIBUTES[PageType.SERVICE]]
    assert keys == ["price", "timeframe", "process", "guarantee", "coverage_area", "availability"]


def test_general_page_has_no_required_attributes() -> None:
    assert REQUIRED_ATTRIBUTES[PageType.GENERAL] == []


def test_attributes_for_without_extras_is_the_page_type_set() -> None:
    keys = [spec.key for spec in attributes_for(PageType.SERVICE)]
    assert keys == ["price", "timeframe", "process", "guarantee", "coverage_area", "availability"]


def test_attributes_for_adds_intent_derived_slots() -> None:
    keys = [spec.key for spec in attributes_for(PageType.GENERAL, [IntentClass.TRANSACTIONAL])]
    assert "cta" in keys
    assert "price" in keys


def test_attributes_for_adds_location_slots_only_with_a_target() -> None:
    without = [spec.key for spec in attributes_for(PageType.SERVICE)]
    with_target = [spec.key for spec in attributes_for(PageType.SERVICE, location_target="Berlin")]
    assert "location" not in without
    assert "location" in with_target
    assert "service_area" in with_target


def test_attributes_for_dedupes_and_keeps_page_type_priority() -> None:
    """Page-type slots win the dedup, and no key repeats."""
    specs = attributes_for(PageType.SERVICE, [IntentClass.COMMERCIAL, IntentClass.LOCAL])
    keys = [spec.key for spec in specs]
    assert len(keys) == len(set(keys))
    assert keys[0] == "price"
    price = next(s for s in specs if s.key == "price")
    assert price.required_for is PageType.SERVICE  # page-type entry, not intent entry


def test_satisfied_attribute_keys_is_explicit_and_lowercased() -> None:
    rows = [
        EAVRow(eav_id="1", entity_name="A", attribute="Price", value="x", status=EAVStatus.EXPLICIT),
        EAVRow(eav_id="2", entity_name="A", attribute="guarantee", value="", status=EAVStatus.EXPLICIT),
        EAVRow(eav_id="3", entity_name="A", attribute="process", value="y", status=EAVStatus.VAGUE),
        EAVRow(eav_id="4", entity_name="A", attribute="timeframe", value="z", status=EAVStatus.MISSING),
    ]
    assert satisfied_attribute_keys(rows) == {"price"}


def test_satisfied_attribute_keys_empty_inventory() -> None:
    assert satisfied_attribute_keys([]) == set()
