"""Unit tests for brand rules and recommendation priority (PRD §9.5, §9.6).

The brand/forbidden-claim evaluators and the priority formula are the two
deterministic rule engines behind the gate and the work order. These tests pin
the forbidden-claim patterns, banned-term matching with allowed contexts, value
normalization/fuzzy equality, canonical-conflict detection channels, and the
priority ordering with its gate-critical override.
"""

from __future__ import annotations

from types import SimpleNamespace

from ega_schemas.entities import EAVRow
from ega_schemas.enums import EAVStatus, Severity
from ega_scoring.state import normalize_name
from test_scoring_fixtures import build_finding

from auditor.rules.brand_rules import (
    RuleViolation,
    brand_pack_present,
    brand_rule_violations,
    collect_brand_inputs,
    detect_banned_terms,
    detect_canonical_fact_conflicts,
    detect_forbidden_claims,
    normalize_value,
    values_equal,
)
from auditor.rules.priority import (
    SEVERITY_RANK,
    assign_ranks,
    compute_priority,
    effective_effort,
    is_gate_critical,
    prioritize_findings,
    priority_sort,
)

CANONICAL = [
    {"fact_id": "cf", "entity": "Acme", "attribute": "availability", "canonical_value": "99.99%"}
]


# ------------------------------------------------------- forbidden claims ----


def test_forbidden_claims_detect_world_superlatives_and_100_percent() -> None:
    violations = detect_forbidden_claims("We are the best in the world and 100% proven.")
    assert len(violations) == 2
    assert all(v.severity is Severity.CRITICAL for v in violations)
    assert all(v.source == "forbidden_claim" for v in violations)
    assert all(v.detail.startswith("Critical Compliance Trigger") for v in violations)


def test_forbidden_claims_detect_cure_and_guaranteed_return() -> None:
    for text, marker in (
        ("This herb cures disease.", "cure"),
        ("Guaranteed returns every quarter.", "return"),
        ("It always works without fail.", "always"),
    ):
        violations = detect_forbidden_claims(text)
        assert violations, text
        assert any(marker in v.detail.lower() or marker in v.title.lower() for v in violations)


def test_forbidden_claims_clean_text_is_empty() -> None:
    assert detect_forbidden_claims("A clear, evidence-backed description.") == []
    assert detect_forbidden_claims("") == []


def test_forbidden_claims_offsets_point_at_the_match() -> None:
    text = "This is 100% guaranteed quality."
    violation = detect_forbidden_claims(text)[0]
    assert violation.start_offset is not None
    assert violation.evidence.strip().lower() in text.lower()


# ----------------------------------------------------------- banned terms ----


def test_banned_term_is_word_boundary_and_case_insensitive() -> None:
    hits = detect_banned_terms("Our ROCKSTAR engineer is here.", [{"term": "rockstar", "severity": "high"}])
    assert len(hits) == 1
    assert hits[0].rule_id == "banned_term:rockstar"
    assert hits[0].severity is Severity.HIGH

    assert detect_banned_terms("The rocketstar programme is unrelated.", [{"term": "rockstar"}]) == []


def test_banned_term_allowed_context_suppresses_hit() -> None:
    entry = {"term": "rockstar", "severity": "high", "allowed_contexts": ["rockstar team"]}
    assert detect_banned_terms("Meet the rockstar team today.", [entry]) == []
    assert detect_banned_terms("Our rockstar engineer left.", [entry]) != []


def test_banned_term_invalid_allowed_context_regex_is_ignored() -> None:
    entry = {"term": "rockstar", "allowed_contexts": ["(unclosed"]}
    hits = detect_banned_terms("Our rockstar engineer left.", [entry])
    assert len(hits) == 1  # the bad context pattern is dropped, the term still applies


def test_banned_term_severity_defaults_to_high_and_parses_strings() -> None:
    default = detect_banned_terms("rockstar here", [{"term": "rockstar"}])
    assert default[0].severity is Severity.HIGH

    medium = detect_banned_terms("rockstar here", [{"term": "rockstar", "severity": "medium"}])
    assert medium[0].severity is Severity.MEDIUM

    bogus = detect_banned_terms("rockstar here", [{"term": "rockstar", "severity": "urgent"}])
    assert bogus[0].severity is Severity.HIGH


def test_banned_term_empty_entry_is_skipped() -> None:
    assert detect_banned_terms("some text", [{"term": ""}, {}, {"term": "   "}]) == []
    assert detect_banned_terms("", [{"term": "rockstar"}]) == []


# ------------------------------------------------------- value normalization --


def test_normalize_value_folds_separators_case_and_symbols() -> None:
    assert normalize_value("100,000 Events/Sec") == "100000 events sec"
    assert normalize_value("  99.99% ") == "99.99 pct"
    assert normalize_value(None) == ""


def test_values_equal_on_normalized_variants() -> None:
    assert values_equal("100,000 events/sec", "100000 events/sec") is True
    assert values_equal("99.99%", "99.99%") is True
    assert values_equal("95%", "99.99%") is False
    assert values_equal("", "anything") is False


def test_values_equal_respects_fuzzy_threshold() -> None:
    assert values_equal("acme corp", "acme corporation", fuzzy_threshold=0.7) is True
    assert values_equal("acme corp", "acme corporation", fuzzy_threshold=0.99) is False


def test_normalize_name_differs_from_normalize_value() -> None:
    """Entity-name normalization strips symbols without percent/plus rewrites."""
    assert normalize_name("Acme, Inc.") == "acme inc"


# ------------------------------------------------------- canonical conflicts --


def test_canonical_conflict_requires_entity_match() -> None:
    row = EAVRow(eav_id="r1", entity_name="Other Co", attribute="availability", value="95%", status=EAVStatus.EXPLICIT)
    assert detect_canonical_fact_conflicts(CANONICAL, eav_rows=[row]) == []


def test_canonical_conflict_requires_a_non_terminal_status() -> None:
    for status in (EAVStatus.VAGUE, EAVStatus.MISSING, EAVStatus.NOT_APPLICABLE):
        row = EAVRow(eav_id="r1", entity_name="Acme", attribute="availability", value="95%", status=status)
        assert detect_canonical_fact_conflicts(CANONICAL, eav_rows=[row]) == []


def test_canonical_conflict_requires_a_different_value() -> None:
    row = EAVRow(eav_id="r1", entity_name="Acme", attribute="availability", value="99.99%", status=EAVStatus.EXPLICIT)
    assert detect_canonical_fact_conflicts(CANONICAL, eav_rows=[row]) == []


def test_canonical_conflict_fires_on_different_value() -> None:
    row = EAVRow(eav_id="r1", entity_name="Acme", attribute="availability", value="95%", status=EAVStatus.EXPLICIT)
    violations = detect_canonical_fact_conflicts(CANONICAL, eav_rows=[row])
    assert len(violations) == 1
    assert violations[0].severity is Severity.CRITICAL
    assert violations[0].source == "canonical_fact"
    assert "Acme.availability" in violations[0].detail


def test_canonical_conflict_requires_attribute_name() -> None:
    row = EAVRow(eav_id="r1", entity_name="Acme", attribute="throughput", value="95%", status=EAVStatus.EXPLICIT)
    assert detect_canonical_fact_conflicts(CANONICAL, eav_rows=[row]) == []


def test_preflagged_pack_fact_is_a_noncritical_pack_conflict() -> None:
    fact = [{"fact_id": "cf", "entity": "Acme", "attribute": "x", "canonical_value": "y", "conflict": True}]
    violations = detect_canonical_fact_conflicts(fact)
    assert len(violations) == 1
    assert violations[0].source == "pack_conflict"
    assert violations[0].severity is Severity.MEDIUM


def test_incomplete_canonical_fact_is_ignored() -> None:
    assert detect_canonical_fact_conflicts([{"fact_id": "cf", "entity": "Acme"}]) == []
    assert detect_canonical_fact_conflicts([]) == []


# ------------------------------------------------------------- pack helpers --


def test_collect_brand_inputs_merges_state_and_packs() -> None:
    rules, terms, facts = collect_brand_inputs(
        brand_rules=[1],
        banned_terms=[2],
        context_packs=[{"brand_rules": [3], "banned_terms": [4], "canonical_facts": [5]}],
    )
    assert rules == [1, 3]
    assert terms == [2, 4]
    assert facts == [5]


def test_brand_pack_present_detects_any_payload() -> None:
    assert brand_pack_present() is False
    assert brand_pack_present(banned_terms=[{"term": "x"}]) is True
    assert brand_pack_present(canonical_facts=[{"fact_id": "x"}]) is True
    assert brand_pack_present(brand_rules=[{"rule_id": "x"}]) is True


# ---------------------------------------------------------- brand rules ----


def test_brand_rule_pattern_violation() -> None:
    violations = brand_rule_violations("We are ALWAYS cheap", [{"rule_id": "r1", "pattern": "always", "severity": "high"}])
    assert len(violations) == 1
    assert violations[0].source == "brand_rule"
    assert violations[0].severity is Severity.HIGH
    assert "ALWAYS" in violations[0].evidence


def test_brand_rule_pre_flagged_violation() -> None:
    violations = brand_rule_violations("text", [{"rule_id": "r2", "violated": True, "statement": "no hype"}])
    assert len(violations) == 1
    assert "no hype" in violations[0].detail


def test_brand_rule_without_markers_is_configuration_only() -> None:
    assert brand_rule_violations("text", [{"rule_id": "r3", "statement": "just guidance"}]) == []


def test_brand_rule_conflict_flag_is_left_to_canonical_channel() -> None:
    assert brand_rule_violations("text", [{"rule_id": "r4", "conflict": True}]) == []


def test_brand_rule_bad_regex_is_skipped() -> None:
    assert brand_rule_violations("text", [{"rule_id": "r5", "pattern": "(unclosed"}]) == []


def test_brand_rule_empty_text_is_empty() -> None:
    assert brand_rule_violations("", [{"rule_id": "r6", "pattern": "x"}]) == []


def test_rule_violation_equality_and_hash() -> None:
    a = RuleViolation(rule_id="x", title="t", detail="d", severity=Severity.HIGH, start_offset=3)
    b = RuleViolation(rule_id="x", title="t", detail="other", severity=Severity.HIGH, start_offset=3)
    c = RuleViolation(rule_id="x", title="t", detail="d", severity=Severity.HIGH, start_offset=9)
    assert a == b
    assert a != c
    assert hash(a) == hash(b)


# ---------------------------------------------------------------- priority ----


def test_effective_effort_is_guarded_to_at_least_one() -> None:
    assert effective_effort(SimpleNamespace(effort=5)) == 5
    assert effective_effort(SimpleNamespace(effort=0)) == 1
    assert effective_effort(SimpleNamespace(effort=None)) == 1
    assert effective_effort(SimpleNamespace(effort="x")) == 1


def test_compute_priority_uses_the_formula_and_persists() -> None:
    finding = build_finding("f1", impact=5, confidence_numeric=4, effort=2)
    assert compute_priority(finding) == 10.0
    assert finding.priority_score == 10.0

    finding2 = build_finding("f2", impact=1, confidence_numeric=1, effort=5)
    assert compute_priority(finding2) == 0.2


def test_is_gate_critical_only_for_open_critical_findings() -> None:
    assert is_gate_critical(build_finding("a", severity="critical", status="open")) is True
    assert is_gate_critical(build_finding("b", severity="critical", status="in_progress")) is True
    assert is_gate_critical(build_finding("c", severity="critical", status="done")) is False
    assert is_gate_critical(build_finding("d", severity="high", status="open")) is False


def test_priority_sort_puts_gate_critical_first_despite_low_score() -> None:
    findings = [
        build_finding("low", severity="low", impact=2, confidence_numeric=3, effort=5),
        build_finding("crit", severity="critical", status="open", impact=1, confidence_numeric=1, effort=5),
        build_finding("high", severity="high", impact=5, confidence_numeric=5, effort=1),
    ]
    ordered = priority_sort(findings)
    assert [f.finding_id for f in ordered] == ["crit", "high", "low"]
    assert ordered[0].priority_score == 0.2  # lowest score yet ranked first
    assert ordered[2].priority_score == 1.2


def test_priority_sort_orders_by_descending_priority_within_group() -> None:
    findings = [
        build_finding("small", severity="medium", impact=1, confidence_numeric=2, effort=4),
        build_finding("big", severity="medium", impact=5, confidence_numeric=5, effort=1),
        build_finding("mid", severity="medium", impact=3, confidence_numeric=3, effort=3),
    ]
    ordered = priority_sort(findings)
    assert [f.finding_id for f in ordered] == ["big", "mid", "small"]
    assert [f.priority_score for f in ordered] == [25.0, 3.0, 0.5]


def test_priority_sort_breaks_ties_by_finding_id() -> None:
    findings = [
        build_finding("zz", severity="medium", impact=4, confidence_numeric=4, effort=2),
        build_finding("aa", severity="medium", impact=4, confidence_numeric=4, effort=2),
    ]
    assert [f.finding_id for f in priority_sort(findings)] == ["aa", "zz"]


def test_priority_sort_is_stable_and_pure_of_order_input() -> None:
    a = build_finding("f1", impact=3, confidence_numeric=3, effort=3)
    b = build_finding("f2", impact=3, confidence_numeric=3, effort=3)
    assert [f.finding_id for f in priority_sort([a, b])] == [f.finding_id for f in priority_sort([a, b])]


def test_assign_ranks_is_one_based() -> None:
    findings = [
        build_finding("f1", severity="high", impact=5, confidence_numeric=5, effort=1),
        build_finding("f2", severity="low", impact=1, confidence_numeric=1, effort=5),
    ]
    assert assign_ranks(findings) == {"f1": 1, "f2": 2}


def test_severity_rank_orders_critical_to_info() -> None:
    assert SEVERITY_RANK["critical"] > SEVERITY_RANK["high"]
    assert SEVERITY_RANK["high"] > SEVERITY_RANK["medium"]
    assert SEVERITY_RANK["medium"] > SEVERITY_RANK["low"]
    assert SEVERITY_RANK["low"] > SEVERITY_RANK["info"]


def test_prioritize_findings_is_the_shared_sort() -> None:
    assert prioritize_findings is priority_sort


def test_priority_sort_handles_empty_list() -> None:
    assert priority_sort([]) == []
    assert assign_ranks([]) == {}
