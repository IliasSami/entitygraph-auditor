"""Unit tests for the Brand / Claim / Compliance Gate (PRD §9.5).

The gate is the publication decision, deliberately independent of the composite
score. These tests pin the four terminal statuses (``FAIL``,
``PASS_WITH_FIXES``, ``PASS``, ``NOT_CONFIGURED``), the critical → not-publishable
mapping, every critical disqualifier channel, the non-critical advisory channel,
and the stable de-duplication of issue texts.
"""

from __future__ import annotations

from ega_schemas.claims import Claim
from ega_schemas.entities import EAVRow
from ega_schemas.enums import (
    ClaimRiskTier,
    EAVStatus,
    GateStatus,
    SensitivityTier,
    TripleStatus,
    TripleType,
    VerificationState,
)
from ega_schemas.triples import SemanticTriple
from ega_scoring.gate import (
    COMPLIANCE_PREFIX,
    build_gate_result,
    evaluate_gate,
    gate_is_publishable,
)
from test_scoring_fixtures import brand_pack, build_finding, gate_state

CANONICAL_FACT = [
    {"fact_id": "cf", "entity": "Acme", "attribute": "availability", "canonical_value": "99.99%"}
]


# ------------------------------------------------------------ forbidden ------


def test_forbidden_claim_triggers_compliance_critical() -> None:
    """Built-in prohibited-claim patterns are critical even with no brand pack."""
    gate = evaluate_gate(gate_state("This herb is 100% guaranteed to cure you."))
    assert gate.status is GateStatus.FAIL
    assert gate.publishable is False
    assert any(COMPLIANCE_PREFIX in issue for issue in gate.critical_issues)
    assert any("cure" in issue.lower() for issue in gate.critical_issues)


def test_no_forbidden_claim_in_plain_prose() -> None:
    """Ordinary prose triggers no compliance pattern."""
    gate = evaluate_gate(gate_state("We help teams model their data reliably."))
    assert not any(COMPLIANCE_PREFIX in issue for issue in gate.critical_issues)


# --------------------------------------------------------- banned terms -----


def test_critical_banned_term_is_a_critical_disqualifier() -> None:
    """A ``critical``-severity banned term blocks publication."""
    gate = evaluate_gate(
        gate_state(
            "Our engine is hyperloop-fast.",
            banned_terms=[{"term": "hyperloop", "severity": "critical", "reason": "internal codename"}],
        )
    )
    assert gate.status is GateStatus.FAIL
    assert gate.publishable is False
    assert any("Prohibited term detected" in i and "hyperloop" in i for i in gate.critical_issues)


def test_high_banned_term_is_non_critical() -> None:
    """A ``high`` (non-critical) banned term only asks for a fix."""
    gate = evaluate_gate(
        gate_state(
            "Our rockstar engineer shipped this.",
            banned_terms=[{"term": "rockstar", "severity": "high", "reason": "off-brand talent language"}],
        )
    )
    assert gate.status is GateStatus.PASS_WITH_FIXES
    assert gate.publishable is True
    assert not gate.critical_issues
    assert any("rockstar" in issue for issue in gate.noncritical_issues)


def test_banned_term_allowed_context_suppresses_the_hit() -> None:
    """A configured allowed-context regex exempts an otherwise banned term."""
    allowed = gate_state(
        "Meet the rockstar team behind the platform.",
        banned_terms=[{"term": "rockstar", "severity": "high", "allowed_contexts": ["rockstar team"]}],
    )
    assert evaluate_gate(allowed).status is GateStatus.PASS


def test_banned_term_is_word_boundary_matched() -> None:
    """``rocketstar`` must not match the banned term ``rockstar``."""
    gate = evaluate_gate(
        gate_state(
            "The rocketstar programme is unrelated.",
            banned_terms=[{"term": "rockstar", "severity": "high"}],
        )
    )
    assert not any("rockstar" in i for i in gate.noncritical_issues)


# ------------------------------------------------------- canonical facts ----


def test_eav_contradicting_canonical_fact_is_critical() -> None:
    """An explicit EAV value that contradicts the pack fails the gate."""
    row = EAVRow(eav_id="x1", entity_name="Acme", attribute="availability", value="95%", status=EAVStatus.EXPLICIT)
    gate = evaluate_gate(
        gate_state("Availability is 95% today.", canonical_facts=CANONICAL_FACT, eav_rows=[row])
    )
    assert gate.status is GateStatus.FAIL
    assert any("Material contradiction with canonical brand pack" in i for i in gate.critical_issues)


def test_eav_matching_canonical_fact_passes() -> None:
    """A matching explicit value produces no conflict."""
    row = EAVRow(eav_id="x2", entity_name="Acme", attribute="availability", value="99.99%", status=EAVStatus.EXPLICIT)
    gate = evaluate_gate(
        gate_state("Availability is 99.99%.", canonical_facts=CANONICAL_FACT, eav_rows=[row])
    )
    assert gate.status is GateStatus.PASS
    assert not gate.critical_issues


def test_triple_contradicting_canonical_fact_is_critical() -> None:
    """A semantic triple with a conflicting object fails the gate."""
    triple = SemanticTriple(
        triple_id="t1",
        subject="Acme",
        predicate="availability is",
        object_="95%",
        status=TripleStatus.EXPLICIT,
        triple_type=TripleType.OTHER,
    )
    gate = evaluate_gate(
        gate_state("Acme availability is 95%.", canonical_facts=CANONICAL_FACT, triples=[triple])
    )
    assert gate.status is GateStatus.FAIL
    assert any("Triple" in i for i in gate.critical_issues)


def test_claim_numbers_contradicting_canonical_fact_is_critical() -> None:
    """A numeric claim that contradicts the pack number is critical."""
    claim = Claim(claim_id="c1", statement="Acme availability is 95 percent", requires_substantiation=False)
    gate = evaluate_gate(
        gate_state("Acme availability is 95 percent.", canonical_facts=CANONICAL_FACT, claims=[claim])
    )
    assert gate.status is GateStatus.FAIL
    assert any("Claim" in i for i in gate.critical_issues)


def test_agent_finding_reported_as_canonical_conflict_is_critical() -> None:
    """A synthesis finding whose category marks a canonical conflict blocks."""
    finding = build_finding("f1", category="canonical_fact_conflict")
    gate = evaluate_gate(gate_state("some prose", canonical_facts=CANONICAL_FACT, findings=[finding]))
    assert gate.status is GateStatus.FAIL
    assert any("canonical fact conflict" in i for i in gate.critical_issues)


def test_preflagged_pack_conflict_is_non_critical() -> None:
    """A pre-flagged pack fact asks for reconciliation, not a hard block."""
    fact = [{"fact_id": "cf", "entity": "Acme", "attribute": "x", "canonical_value": "y", "conflict": True}]
    gate = evaluate_gate(gate_state("nothing here", canonical_facts=fact))
    assert gate.status is GateStatus.PASS_WITH_FIXES
    assert any("Brand pack needs reconciliation" in i for i in gate.noncritical_issues)


# ------------------------------------------------------------- claims -------


def test_fabrication_risk_claim_is_critical() -> None:
    """A claim agent-flagged as fabricated blocks publication (PRD §9.5)."""
    claim = Claim(
        claim_id="c1",
        statement="We invented a benchmark number.",
        issue="fabricated data",
        requires_substantiation=True,
    )
    gate = evaluate_gate(gate_state("some prose", claims=[claim]))
    assert gate.status is GateStatus.FAIL
    assert any("Fabrication risk" in i for i in gate.critical_issues)


def test_unverified_regulated_claim_is_critical_even_at_ordinary_sensitivity() -> None:
    """A REGULATED unverified claim is critical regardless of sensitivity tier."""
    claim = Claim(
        claim_id="c1",
        statement="This treats hypertension.",
        risk_tier=ClaimRiskTier.REGULATED,
        verification_state=VerificationState.UNVERIFIED,
        requires_substantiation=True,
    )
    gate = evaluate_gate(gate_state("some prose", claims=[claim], sensitivity=SensitivityTier.ORDINARY))
    assert gate.status is GateStatus.FAIL
    assert any("High-risk unverified claim" in i for i in gate.critical_issues)
    assert any("authoritative substantiation" in i for i in gate.critical_issues)


def test_unverified_high_stakes_claim_is_critical_at_high_sensitivity() -> None:
    """Under a non-ordinary sensitivity tier an unverified high-stakes claim blocks."""
    claim = Claim(
        claim_id="c1",
        statement="Clinically proven to help.",
        risk_tier=ClaimRiskTier.HIGH_STAKES,
        verification_state=VerificationState.UNVERIFIED,
        requires_substantiation=True,
    )
    gate = evaluate_gate(gate_state("some prose", claims=[claim], sensitivity=SensitivityTier.HIGH_STAKES))
    assert gate.status is GateStatus.FAIL


def test_unverified_high_stakes_claim_is_only_flagged_at_ordinary_sensitivity() -> None:
    """At ordinary sensitivity the same claim is advisory, not blocking."""
    claim = Claim(
        claim_id="c1",
        statement="Clinically proven to help.",
        risk_tier=ClaimRiskTier.HIGH_STAKES,
        verification_state=VerificationState.UNVERIFIED,
        requires_substantiation=True,
    )
    gate = evaluate_gate(gate_state("some prose", claims=[claim], sensitivity=SensitivityTier.ORDINARY))
    assert gate.status is GateStatus.PASS_WITH_FIXES
    assert not gate.critical_issues
    assert any("not yet substantiated" in i for i in gate.noncritical_issues)


def test_ordinary_claim_without_reference_is_non_critical() -> None:
    """A substantiation-required claim with no reference is only advisory."""
    claim = Claim(claim_id="c1", statement="It is faster than alternatives.", requires_substantiation=True)
    gate = evaluate_gate(gate_state("some prose", claims=[claim]))
    assert gate.status is GateStatus.PASS_WITH_FIXES
    assert any("lacking a reference" in i for i in gate.noncritical_issues)


# ------------------------------------------------------------ findings ------


def test_open_critical_finding_blocks_publication() -> None:
    """Any open critical finding is a critical disqualifier (PRD §9.5/§9.6)."""
    gate = evaluate_gate(gate_state("some prose", findings=[build_finding("f1", severity="critical", status="open")]))
    assert gate.status is GateStatus.FAIL
    assert any("resolve before publishing" in i for i in gate.critical_issues)


def test_resolved_critical_finding_is_not_blocking() -> None:
    """A critical finding already done/dismissed no longer blocks."""
    gate = evaluate_gate(gate_state("some prose", findings=[build_finding("f1", severity="critical", status="done")]))
    assert not gate.critical_issues
    assert gate.status is GateStatus.NOT_CONFIGURED


def test_high_severity_finding_is_non_critical() -> None:
    """High/medium/low findings are advisory."""
    gate = evaluate_gate(gate_state("some prose", findings=[build_finding("f1", severity="high", status="open")]))
    assert gate.status is GateStatus.PASS_WITH_FIXES
    assert any("needs attention" in i for i in gate.noncritical_issues)


# ------------------------------------------------------------- statuses -----


def test_clean_run_with_pack_is_pass() -> None:
    """A clean run with a configured brand pack is PASS and publishable."""
    gate = evaluate_gate(
        gate_state("Acme helps data teams model streaming workloads clearly.", context_packs=[brand_pack()])
    )
    assert gate.status is GateStatus.PASS
    assert gate.publishable is True
    assert gate.critical_issues == []
    assert gate.noncritical_issues == []


def test_clean_run_without_pack_is_not_configured() -> None:
    """No brand pack at all means the gate had nothing to enforce (PRD §9.5)."""
    gate = evaluate_gate(gate_state("Acme helps data teams model streaming workloads clearly."))
    assert gate.status is GateStatus.NOT_CONFIGURED
    assert gate.publishable is True
    assert "not configured" in gate.rationale.lower()


def test_issue_texts_are_stable_and_deduplicated() -> None:
    """Identical issue texts are collapsed while preserving first-seen order."""
    gate = evaluate_gate(gate_state("We are 100% guaranteed and 100% guaranteed every time."))
    assert len(gate.critical_issues) == 1

    gate = evaluate_gate(
        gate_state("rockstar rockstar engineer", banned_terms=[{"term": "rockstar", "severity": "high"}])
    )
    assert len(gate.noncritical_issues) == 1


def test_issue_lists_are_plain_strings() -> None:
    """Downstream code joins/format issue lists directly, so they are strings."""
    gate = evaluate_gate(gate_state("This herb 100% cures cancer."))
    assert all(isinstance(issue, str) for issue in gate.critical_issues)


# ------------------------------------------------------- build_gate_result ---


def test_build_gate_result_critical_maps_to_fail() -> None:
    result = build_gate_result(critical=["a"], noncritical=[], pack_configured=False)
    assert result.status is GateStatus.FAIL
    assert result.publishable is False
    assert "high composite AVR cannot override" in result.rationale


def test_build_gate_result_non_critical_maps_to_pass_with_fixes() -> None:
    result = build_gate_result(critical=[], noncritical=["b"], pack_configured=True)
    assert result.status is GateStatus.PASS_WITH_FIXES
    assert result.publishable is True


def test_build_gate_result_clean_with_pack_is_pass() -> None:
    result = build_gate_result(critical=[], noncritical=[], pack_configured=True)
    assert result.status is GateStatus.PASS
    assert result.publishable is True
    assert "brand pack loaded" in result.rationale


def test_build_gate_result_clean_without_pack_is_not_configured() -> None:
    result = build_gate_result(critical=[], noncritical=[], pack_configured=False)
    assert result.status is GateStatus.NOT_CONFIGURED
    assert result.publishable is True


def test_gate_is_publishable_only_excludes_fail() -> None:
    assert gate_is_publishable(build_gate_result(critical=[], noncritical=[], pack_configured=True)) is True
    assert gate_is_publishable(build_gate_result(critical=["x"], noncritical=[], pack_configured=True)) is False


# --------------------------------------------------------- legacy signature --


def test_evaluate_gate_accepts_claims_list_signature() -> None:
    """Back-compat: ``evaluate_gate(claims, context_packs, raw_text)`` still works."""
    claim = Claim(
        claim_id="c1",
        statement="Totally proven.",
        risk_tier=ClaimRiskTier.HIGH_STAKES,
        verification_state=VerificationState.UNVERIFIED,
        requires_substantiation=True,
    )
    gate = evaluate_gate([claim])
    assert gate.status is GateStatus.PASS_WITH_FIXES
    assert any("substantiated" in i for i in gate.noncritical_issues)


def test_evaluate_gate_legacy_signature_with_packs_and_text() -> None:
    """Back-compat path flattens brand rules, banned terms and raw text."""
    gate = evaluate_gate(
        [],
        context_packs=[{"banned_terms": [{"term": "forbidden", "severity": "high"}]}],
        raw_text="this is forbidden wording",
    )
    assert gate.status is GateStatus.PASS_WITH_FIXES
    assert any("forbidden" in i for i in gate.noncritical_issues)


def test_gate_reports_sensitivity_tier_in_pass_rationale() -> None:
    """The PASS rationale names the sensitivity tier it was evaluated under."""
    gate = evaluate_gate(
        gate_state("clean prose", context_packs=[brand_pack()], sensitivity=SensitivityTier.REGULATED)
    )
    assert gate.status is GateStatus.PASS
    assert "regulated" in gate.rationale
