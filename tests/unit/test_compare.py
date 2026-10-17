"""Unit tests for apps/api/app/services/compare.py (PRD FR-17 comparison)."""

import pytest
from ega_api.services.compare import ComparisonResult, compare_reports
from ega_schemas import PageType
from test_export_fixtures import build_report_a, build_report_b, build_report_c


@pytest.fixture
def result() -> ComparisonResult:
    return compare_reports(build_report_a(), build_report_b())


def _scores_by_key(result: ComparisonResult) -> dict:
    return {row["key"]: row for row in result.score_delta}


# ---------------------------------------------------------------- scores ---


def test_score_delta_up_down_and_same_tolerance(result):
    rows = _scores_by_key(result)
    assert len(result.score_delta) == 8
    assert rows["EOS"]["direction"] == "up"
    assert rows["EOS"]["delta"] == pytest.approx(1.5)
    assert rows["CWS"]["direction"] == "down"
    assert rows["CWS"]["delta"] == pytest.approx(-0.5)
    assert rows["KGR"]["direction"] == "same"
    assert rows["KGR"]["delta"] == pytest.approx(0.0)
    # 0.05 tolerance: 7.0 → 7.05 is "same", not "up".
    assert rows["PRS"]["direction"] == "same"
    assert rows["PRS"]["delta"] == pytest.approx(0.05)
    assert rows["EOS"]["label"] == "Entity Optimization Score"


def test_na_component_direction_is_n_a_not_zero(result):
    row = _scores_by_key(result)["TRUST"]
    assert row["baseline"] == 4.0
    assert row["candidate"] is None
    assert row["direction"] == "n_a"
    assert row["delta"] is None  # N/A must never be treated as 0


def test_composite_avr_delta(result):
    assert result.composite_delta["baseline"] == pytest.approx(5.9)
    assert result.composite_delta["candidate"] == pytest.approx(6.5)
    assert result.composite_delta["direction"] == "up"
    assert result.composite_delta["delta"] == pytest.approx(0.6)


def test_result_carries_run_ids(result):
    assert result.baseline_id == "run-a"
    assert result.candidate_id == "run-b"


# -------------------------------------------------------------- entities ---


def test_entity_added_removed_and_changed(result):
    changes = result.entity_changes
    assert changes["added"] == [
        {"id": "e7", "label": "Roastery Tours", "kind": "product_service"}
    ]
    assert changes["removed"] == [
        {"id": "e6", "label": "Old Vendor & Co", "kind": "organization"}
    ]
    keyed = {(c["label"], c["field"]): c for c in changes["changed"]}
    assert set(keyed) == {
        ("Café Noir Roastery", "occurrence_count"),
        ("single origin coffee", "is_central"),
        ("cold brew", "kind"),
    }
    assert keyed[("Café Noir Roastery", "occurrence_count")]["before"] == 3
    assert keyed[("Café Noir Roastery", "occurrence_count")]["after"] == 5
    assert keyed[("single origin coffee", "is_central")]["before"] is False
    assert keyed[("single origin coffee", "is_central")]["after"] is True
    assert keyed[("cold brew", "kind")]["before"] == "concept"
    assert keyed[("cold brew", "kind")]["after"] == "product_service"


# ------------------------------------------------------------------ EAV ---


def test_eav_improved_missing_to_explicit_and_vague_to_explicit(result):
    keyed = {(e["entity"].lower(), e["attribute"]): e for e in result.eav_improved}
    assert set(keyed) == {
        ("café noir roastery", "price_range"),
        ("single origin coffee", "definition"),
    }
    price = keyed[("café noir roastery", "price_range")]
    assert price["before_status"] == "missing"
    assert price["after_status"] == "explicit"
    assert price["evidence_excerpt"] == "Prices sit in the mid range (€€)."
    assert keyed[("single origin coffee", "definition")]["before_status"] == "vague"


def test_eav_regressed_explicit_to_missing(result):
    assert len(result.eav_regressed) == 1
    entry = result.eav_regressed[0]
    assert entry["entity"] == "Café Noir Roastery"
    assert entry["attribute"] == "flagship_location"
    assert entry["before_status"] == "explicit"
    assert entry["after_status"] == "missing"


def test_eav_not_applicable_excluded(result):
    attributes = {e["attribute"] for e in result.eav_improved + result.eav_regressed}
    assert "serving_temperature" not in attributes


# ------------------------------------------------------------- coverage ---


def test_coverage_improved_and_regressed(result):
    assert result.coverage_delta["improved"] == [
        {"query": "How much does Café Noir charge?", "before_status": "missing", "after_status": "partial"}
    ]
    assert result.coverage_delta["regressed"] == [
        {"query": "Is cold brew stronger than espresso?", "before_status": "partial", "after_status": "missing"}
    ]
    assert result.coverage_delta["added_queries"] == 0
    assert result.coverage_delta["removed_queries"] == 0


def test_coverage_added_removed_and_fcs_between_a_and_c():
    result = compare_reports(build_report_a(), build_report_c())
    assert result.coverage_delta["added_queries"] == 1
    assert result.coverage_delta["removed_queries"] == 1
    assert result.coverage_delta["baseline_fcs"] == pytest.approx(4.0)
    assert result.coverage_delta["candidate_fcs"] == pytest.approx(4.0)


def test_fcs_delta_from_scorecards(result):
    assert result.coverage_delta["baseline_fcs"] == pytest.approx(4.0)
    assert result.coverage_delta["candidate_fcs"] == pytest.approx(6.5)


# -------------------------------------------------------------- findings ---


def test_findings_resolved_and_new(result):
    resolved = {f.finding_id for f in result.resolved_findings}
    new = {f.finding_id for f in result.new_findings}
    assert resolved == {"rec-1", "rec-5"}  # rec-1 done, rec-5 dropped
    # rec-1 is resolved because the CANDIDATE marks it done (base stays open).
    candidate = build_report_b()
    cand_rec1 = next(f for f in candidate.recommendations if f.finding_id == "rec-1")
    assert cand_rec1.status.value == "done"
    assert new == {"rec-6"}


def test_still_open_and_title_fallback_matching(result):
    assert set(result.still_open) == {
        "rec-2",
        "rec-3",
        "rec-4b",  # matched to base rec-4 by normalized title
        "pf-1",
        "pf-2",
        "pf-3",
        "pf-4",
    }
    assert "rec-4" not in result.still_open


# ---------------------------------------------------------------- claims ---


def test_claim_newly_supported(result):
    assert len(result.claims_newly_supported) == 1
    entry = result.claims_newly_supported[0]
    assert entry["claim"] == "The roastery produces 12 tons of green coffee every year."
    assert entry["baseline_state"] == "unverified"
    assert entry["candidate_state"] == "verified"


def test_claim_newly_unsupported(result):
    assert len(result.claims_newly_unsupported) == 1
    entry = result.claims_newly_unsupported[0]
    assert entry["claim"] == "Café Noir sources beans from Ethiopian farmers."
    assert entry["baseline_state"] == "verified"
    assert entry["candidate_state"] == "unverified"


def test_claims_are_never_invented(result):
    base = build_report_a()
    cand = build_report_b()
    base_statements = {c.statement for c in base.claims}
    cand_statements = {c.statement for c in cand.claims}
    for entry in result.claims_newly_supported + result.claims_newly_unsupported:
        assert entry["claim"] in base_statements
        assert entry["claim"] in cand_statements


# ----------------------------------------------------------- like-for-like ---


def test_like_for_like_true_for_identical_dimensions(result):
    assert result.like_for_like is True
    assert result.warnings == []


def test_like_for_like_false_warns_about_profile_provider_context():
    result = compare_reports(build_report_a(), build_report_c())
    assert result.like_for_like is False
    assert len(result.warnings) == 3
    assert any(
        "Comparisons may not be like-for-like: score profile version differs"
        " (1.0 vs 1.1)" in w
        for w in result.warnings
    )
    assert any("provider model differs (local/llama-3.1 vs openai/gpt-4o-mini)" in w for w in result.warnings)
    assert any(
        "context packs differ (['brand-pack@1.0'] vs ['brand-pack@2.0'])" in w
        for w in result.warnings
    )
    # Deltas are still computed even when not like-for-like.
    assert result.score_delta
    assert all(row["direction"] == "same" for row in result.score_delta)


def test_like_for_like_warns_when_page_type_differs():
    cand = build_report_c()
    cand.audit_metadata = cand.audit_metadata.model_copy(
        update={"page_type": PageType.HOMEPAGE}
    )
    result = compare_reports(build_report_a(), cand)
    assert result.like_for_like is False
    assert any(
        "page type differs (article vs homepage)" in w for w in result.warnings
    )


# ------------------------------------------------------------------ gate ---


def test_gate_change_fail_to_pass_improved(result):
    gate = result.gate_change
    assert gate["baseline"] == "fail"
    assert gate["candidate"] == "pass"
    assert gate["improved"] is True
    assert gate["new_critical"] == []
    assert set(gate["removed_critical"]) == {
        "Fabricated statistic in intro",
        "Prohibited cure claim",
    }


def test_gate_change_detects_new_and_removed_critical_issues():
    result = compare_reports(build_report_a(), build_report_c())
    gate = result.gate_change
    assert gate["improved"] is False
    assert gate["new_critical"] == ["Unverifiable safety certification claim"]
    assert gate["removed_critical"] == ["Prohibited cure claim"]


# ---------------------------------------------------------------- triples ---


def test_triple_changes_added_removed_status_changed(result):
    changes = result.triple_changes
    assert [t["id"] for t in changes["added"]] == ["t6"]
    assert changes["added"][0]["triple"] == "Café Noir Roastery — runs → roastery tours"
    assert [t["id"] for t in changes["removed"]] == ["t5"]
    assert changes["status_changed"] == [
        {
            "triple": "Café Noir Roastery — roasts_in_batches_on → 5 kg drum roaster",
            "before": "implied",
            "after": "explicit",
        }
    ]


# ------------------------------------------------------------ identical ---


def test_identical_reports_produce_all_same_and_no_changes():
    report = build_report_a()
    result = compare_reports(report, build_report_a())
    assert result.like_for_like is True
    assert result.warnings == []
    assert result.score_delta
    assert all(row["direction"] == "same" for row in result.score_delta)
    assert all(row["delta"] == pytest.approx(0.0) for row in result.score_delta)
    assert result.composite_delta["direction"] == "same"
    assert result.composite_delta["delta"] == pytest.approx(0.0)
    assert result.entity_changes == {"added": [], "removed": [], "changed": []}
    assert result.eav_improved == []
    assert result.eav_regressed == []
    assert result.triple_changes == {"added": [], "removed": [], "status_changed": []}
    assert result.coverage_delta["improved"] == []
    assert result.coverage_delta["regressed"] == []
    assert result.coverage_delta["added_queries"] == 0
    assert result.coverage_delta["removed_queries"] == 0
    assert result.claims_newly_supported == []
    assert result.claims_newly_unsupported == []
    assert result.resolved_findings == []
    assert result.new_findings == []
    assert result.gate_change["improved"] is False
    assert result.gate_change["new_critical"] == []
    assert result.gate_change["removed_critical"] == []
