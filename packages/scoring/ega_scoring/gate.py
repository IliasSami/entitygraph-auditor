"""Brand, Claim and Compliance Gate (PRD §9.5, FR-11).

The gate is the *publication* decision, deliberately independent of the
composite score: "A page can receive a high AVR but still fail publication
gating" (PRD §9.5). It is deterministic — every input is structured state or a
brand-pack rule, never an LLM judgement.

Critical disqualifiers (PRD §9.5) map to ``GateStatus.FAIL`` and
``publishable=False``:

* fabricated data / quotes / credentials (fabrication-risk claims);
* material contradictions with a canonical brand pack;
* high-risk false legal / medical / safety claims (prohibited claim patterns
  and unverified high-stakes claims under a non-ordinary sensitivity tier);
* a prohibited claim (brand pack or built-in compliance patterns);
* any *open critical* finding raised by the specialist agents.

Everything else that needs attention is a non-critical issue →
``PASS_WITH_FIXES``. A clean run with a configured brand pack is ``PASS``; a
clean run with **no** brand pack and no compliance triggers is
``NOT_CONFIGURED`` because the brand/claim gate had nothing to evaluate.

Issue lists contain plain strings so that downstream handoff/export code can
format them directly (``scorecard.gate.critical_issues``).
"""

from __future__ import annotations

from typing import Any

from ega_schemas.enums import ClaimRiskTier, GateStatus, SensitivityTier, Severity
from ega_schemas.scores import GateResult

from auditor.rules.brand_rules import (
    brand_pack_present,
    brand_rule_violations,
    detect_banned_terms,
    detect_canonical_fact_conflicts,
    detect_forbidden_claims,
)
from auditor.rules.priority import is_gate_critical
from ega_scoring.state import (
    claim_is_fabrication_risk,
    claim_is_high_stakes,
    document_text,
    get_banned_terms,
    get_brand_rules,
    get_canonical_facts,
    get_claims,
    get_eav_rows,
    get_findings,
    get_passage_findings,
    get_sensitivity,
    get_triples,
)

#: Prefix used for built-in compliance-pattern triggers so the reason is obvious
#: in reports and downstream summaries.
COMPLIANCE_PREFIX = "Critical Compliance Trigger"


def _critical_text(prefix: str, detail: str) -> str:
    return f"{prefix}: {detail}" if prefix else detail


# --------------------------------------------------------------------------
# Individual disqualifier checks (each returns (critical, noncritical) texts)
# --------------------------------------------------------------------------


def _compliance_violation_texts(text: str) -> list[str]:
    """Built-in prohibited-claim patterns (always checked, pack or not)."""
    return [
        violation.detail
        if violation.detail.startswith(COMPLIANCE_PREFIX)
        else _critical_text(COMPLIANCE_PREFIX, violation.detail)
        for violation in detect_forbidden_claims(text)
    ]


def _brand_violation_texts(
    text: str,
    brand_rules: list[Any],
    banned_terms: list[Any],
) -> tuple[list[str], list[str]]:
    """Banned-term and machine-checkable brand-rule violations."""
    critical: list[str] = []
    noncritical: list[str] = []
    for violation in detect_banned_terms(text, banned_terms):
        message = f"Prohibited term detected: {violation.detail}"
        (critical if violation.severity == Severity.CRITICAL else noncritical).append(message)
    for violation in brand_rule_violations(text, brand_rules):
        message = f"Brand rule violation: {violation.detail}"
        (critical if violation.severity == Severity.CRITICAL else noncritical).append(message)
    return critical, noncritical


def _claim_texts(claims: list[Any], sensitivity: SensitivityTier) -> tuple[list[str], list[str]]:
    """Fabricated, high-stakes-unverified and unsubstantiated claim checks."""
    critical: list[str] = []
    noncritical: list[str] = []
    for claim in claims:
        if claim_is_fabrication_risk(claim):
            critical.append(
                f"Fabrication risk: claim '{claim.statement}' looks fabricated, invented or "
                f"materially conflicting (PRD §9.5)."
            )
            continue
        if claim_is_high_stakes(claim):
            verified = bool(claim.evidence_source_ids) or claim.verification_state.value == "verified"
            if verified:
                continue
            regulated = claim.risk_tier == ClaimRiskTier.REGULATED
            if regulated or sensitivity != SensitivityTier.ORDINARY:
                critical.append(
                    f"High-risk unverified claim under '{sensitivity.value}' sensitivity: "
                    f"'{claim.statement}' requires authoritative substantiation (PRD §9.5)."
                )
            else:
                noncritical.append(
                    f"High-stakes claim not yet substantiated: '{claim.statement}' "
                    f"(ordinary sensitivity — flagged, not blocking)."
                )
            continue
        if claim.requires_substantiation and not claim.evidence_source_ids:
            noncritical.append(f"Ordinary claim lacking a reference: '{claim.statement}'.")
    return critical, noncritical


def _canonical_conflict_texts(
    canonical_facts: list[Any],
    eav_rows: list[Any],
    claims: list[Any],
    triples: list[Any],
    text: str,
    findings: list[Any],
) -> tuple[list[str], list[str]]:
    """Canonical brand-pack contradictions (critical) and pack conflicts (non-critical)."""
    critical: list[str] = []
    noncritical: list[str] = []
    for violation in detect_canonical_fact_conflicts(
        canonical_facts,
        eav_rows=eav_rows,
        claims=claims,
        triples=triples,
        text=text,
        findings=findings,
    ):
        if violation.source == "pack_conflict":
            noncritical.append(f"Brand pack needs reconciliation: {violation.detail}")
        else:
            critical.append(
                _critical_text("Material contradiction with canonical brand pack", violation.detail)
            )
    return critical, noncritical


def _finding_texts(findings: list[Any]) -> tuple[list[str], list[str]]:
    """Open critical findings block publication; lower severities are advisory."""
    critical: list[str] = []
    noncritical: list[str] = []
    for finding in findings:
        if is_gate_critical(finding):
            critical.append(
                f"Critical finding '{finding.title}' ({finding.finding_id}) is open — "
                f"resolve before publishing (PRD §9.5/§9.6)."
            )
        elif finding.severity in (Severity.HIGH, Severity.MEDIUM, Severity.LOW):
            noncritical.append(f"Finding '{finding.title}' ({finding.finding_id}) needs attention.")
    return critical, noncritical


def _dedupe(values: list[str]) -> list[str]:
    """Stable de-duplication preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def evaluate_gate(
    state: Any = None,
    context_packs: Any = None,
    raw_text: Any = None,
) -> GateResult:
    """Evaluate the brand/claim/compliance gate for ``state`` (PRD §9.5).

    Returns a ``GateResult`` whose ``status`` is one of ``FAIL``,
    ``PASS_WITH_FIXES``, ``PASS`` or ``NOT_CONFIGURED`` and whose
    ``publishable`` flag is ``False`` only for ``FAIL``. The two issue lists are
    plain strings so they can be rendered directly by the report/handoff layer.
    """
    if isinstance(state, (list, tuple)) or context_packs is not None or raw_text is not None:
        from types import SimpleNamespace
        claims = list(state) if isinstance(state, (list, tuple)) else []
        text = str(raw_text or "")
        c_packs = context_packs or []
        state = SimpleNamespace(
            claims=claims,
            context_packs=c_packs,
            content=text,
            brand_rules=[],
            banned_terms=[],
            canonical_facts=[],
            eav_rows=[],
            triples=[],
            findings=[],
            passage_findings=[],
            sensitivity=SensitivityTier.ORDINARY,
        )

    text = document_text(state)
    brand_rules = get_brand_rules(state)
    banned_terms = get_banned_terms(state)
    canonical_facts = get_canonical_facts(state)
    claims = get_claims(state)
    eav_rows = get_eav_rows(state)
    triples = get_triples(state)
    findings = [*get_findings(state), *get_passage_findings(state)]
    sensitivity = get_sensitivity(state)


    critical: list[str] = []
    noncritical: list[str] = []

    critical.extend(_compliance_violation_texts(text))

    brand_critical, brand_noncritical = _brand_violation_texts(text, brand_rules, banned_terms)
    critical.extend(brand_critical)
    noncritical.extend(brand_noncritical)

    conflict_critical, conflict_noncritical = _canonical_conflict_texts(
        canonical_facts, eav_rows, claims, triples, text, findings
    )
    critical.extend(conflict_critical)
    noncritical.extend(conflict_noncritical)

    claim_critical, claim_noncritical = _claim_texts(claims, sensitivity)
    critical.extend(claim_critical)
    noncritical.extend(claim_noncritical)

    finding_critical, finding_noncritical = _finding_texts(findings)
    critical.extend(finding_critical)
    noncritical.extend(finding_noncritical)

    critical = _dedupe(critical)
    noncritical = _dedupe(noncritical)

    pack_configured = brand_pack_present(brand_rules, banned_terms, canonical_facts)

    return build_gate_result(
        critical=critical,
        noncritical=noncritical,
        pack_configured=pack_configured,
        sensitivity=sensitivity,
    )


def build_gate_result(
    *,
    critical: list[str],
    noncritical: list[str],
    pack_configured: bool,
    sensitivity: SensitivityTier = SensitivityTier.ORDINARY,
) -> GateResult:
    """Map collected issue texts onto a ``GateStatus`` (PRD §9.5).

    Kept separate from :func:`evaluate_gate` so the mapping rule is unit-testable
    without constructing a whole run state.
    """
    if critical:
        return GateResult(
            status=GateStatus.FAIL,
            critical_issues=critical,
            noncritical_issues=noncritical,
            publishable=False,
            rationale=(
                f"Not publishable as-is: {len(critical)} critical disqualifier(s) detected "
                f"(PRD §9.5). A high composite AVR cannot override this gate."
            ),
        )
    if noncritical:
        return GateResult(
            status=GateStatus.PASS_WITH_FIXES,
            critical_issues=[],
            noncritical_issues=noncritical,
            publishable=True,
            rationale=(
                f"Publishable with fixes: {len(noncritical)} non-critical issue(s) to resolve "
                f"(PRD §9.5)."
            ),
        )
    if pack_configured:
        return GateResult(
            status=GateStatus.PASS,
            critical_issues=[],
            noncritical_issues=[],
            publishable=True,
            rationale=(
                "Pass: brand pack loaded and no prohibited claims, banned terms, canonical-fact "
                f"contradictions or open critical findings under '{sensitivity.value}' sensitivity."
            ),
        )
    return GateResult(
        status=GateStatus.NOT_CONFIGURED,
        critical_issues=[],
        noncritical_issues=[],
        publishable=True,
        rationale=(
            "Gate not configured: no brand pack (brand rules, banned terms or canonical facts) "
            "was supplied, so no brand/claim rules could be enforced. Built-in compliance "
            "patterns ran clean (PRD §9.5 'not configured / not assessed')."
        ),
    )


def gate_is_publishable(result: GateResult) -> bool:
    """True when the gate permits publication (i.e. not ``FAIL``)."""
    return result.status != GateStatus.FAIL


__all__ = [
    "COMPLIANCE_PREFIX",
    "build_gate_result",
    "evaluate_gate",
    "gate_is_publishable",
]
