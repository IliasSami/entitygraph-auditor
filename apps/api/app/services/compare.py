"""Multi-version audit comparison (PRD FR-17).

Compares two ``AuditReport`` instances and reports score, entity, EAV, triple,
coverage, claim, finding and gate deltas — always flagging comparisons that are
not like-for-like (different score profile version, page type, provider model or
context pack versions). Claims and findings are only ever reported from the two
input reports; nothing is invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ega_schemas.findings import Finding
from ega_schemas.report import AuditReport

#: Direction tolerance for score deltas (PRD §9.5: one decimal place is enough).
TOLERANCE = 0.05

#: EAV status quality order. ``not_applicable`` is excluded from comparisons.
EAV_RANK = {
    "explicit": 4,
    "unverified": 3,
    "vague": 2,
    "conflicting": 1,
    "missing": 0,
    "not_applicable": -1,
}

#: Fan-out coverage ranks (PRD §9.2-D). ``excluded`` is not ranked.
COVERAGE_RANK = {"covered": 1.0, "partial": 0.5, "missing": 0.0}

#: Gate status improvement order (unknown states never count as improvements).
GATE_RANK = {
    "fail": 0,
    "not_configured": 0,
    "not_assessed": 0,
    "pass_with_fixes": 1,
    "pass": 2,
}

_SCORE_LABELS = {
    "EOS": "Entity Optimization Score",
    "ERS": "Entity Relationship Score",
    "KGR": "Knowledge-Graph Readiness",
    "FCS": "Fan-out Coverage Score",
    "PRS": "Passage Retrievability Score",
    "CWS": "Citation-Worthiness / Information Gain",
    "HRS": "Human Readability & Utility",
    "AVR": "Composite AVR",
    "INTENT": "Intent Alignment",
    "LOCAL_FIT": "Local Fit",
    "PAID_FIT": "Paid Landing Page Fit",
    "CONVERSION": "Conversion Readiness",
    "TRUST": "Trust / E-E-A-T Coverage",
    "LINKS": "Internal-Link Readiness",
}

_FINDING_ID_LIKE = "open"


@dataclass
class ComparisonResult:
    """Structured FR-17 comparison output (serializable by FastAPI)."""

    baseline_id: str
    candidate_id: str
    score_delta: list[dict] = field(default_factory=list)
    composite_delta: dict | None = None
    entity_changes: dict = field(default_factory=dict)
    eav_improved: list[dict] = field(default_factory=list)
    eav_regressed: list[dict] = field(default_factory=list)
    triple_changes: dict = field(default_factory=dict)
    coverage_delta: dict = field(default_factory=dict)
    claims_newly_supported: list[dict] = field(default_factory=list)
    claims_newly_unsupported: list[dict] = field(default_factory=list)
    # finding_id is a str in ega_schemas.findings.Finding, so still-open ids are
    # strings (the spec's list[int] would not represent ids like "rec-4b").
    resolved_findings: list[Finding] = field(default_factory=list)
    new_findings: list[Finding] = field(default_factory=list)
    still_open: list[str] = field(default_factory=list)
    gate_change: dict | None = None
    like_for_like: bool = True
    warnings: list[str] = field(default_factory=list)


def _norm(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def _issue_text(issue) -> str:
    """Gate issue lists accept str | GateIssue; normalize for set diffs."""
    if isinstance(issue, str):
        return issue
    for attr in ("message", "title", "detail", "issue_id"):
        value = getattr(issue, attr, None)
        if value:
            return str(value)
    return str(issue)


def _composite_avr(report: AuditReport) -> float | None:
    if report.composite_avr is not None:
        return report.composite_avr
    return getattr(report.scores, "avr", None)


def _delta(baseline: float | None, candidate: float | None) -> tuple[float | None, str]:
    """→ (delta, direction); N/A is never treated as zero."""
    if baseline is None or candidate is None:
        return None, "n_a"
    delta = candidate - baseline
    if abs(delta) <= TOLERANCE:
        return delta, "same"
    return delta, "up" if delta > 0 else "down"


def _like_for_like(base: AuditReport, cand: AuditReport) -> tuple[bool, list[str]]:
    b, c = base.audit_metadata, cand.audit_metadata
    warnings: list[str] = []
    if b.score_profile_version != c.score_profile_version:
        warnings.append(
            "Comparisons may not be like-for-like: score profile version differs"
            f" ({b.score_profile_version} vs {c.score_profile_version})"
        )
    if b.page_type != c.page_type:
        warnings.append(
            "Comparisons may not be like-for-like: page type differs"
            f" ({b.page_type.value} vs {c.page_type.value})"
        )
    bm, cm = b.provider_model, c.provider_model
    if bm != cm and not (bm is None and cm is None):
        warnings.append(
            "Comparisons may not be like-for-like: provider model differs"
            f" ({bm} vs {cm})"
        )
    if set(b.context_pack_versions) != set(c.context_pack_versions):
        warnings.append(
            "Comparisons may not be like-for-like: context packs differ"
            f" ({sorted(b.context_pack_versions)} vs {sorted(c.context_pack_versions)})"
        )
    return not warnings, warnings


def _score_delta(base: AuditReport, cand: AuditReport) -> list[dict]:
    rows: list[dict] = []
    keys = list(base.scores) + [k for k in cand.scores if k not in base.scores]
    for key in keys:
        b_item = base.scores[key] if key in base.scores else None
        c_item = cand.scores[key] if key in cand.scores else None
        b = getattr(b_item, "value", None) if not isinstance(b_item, dict) else b_item.get("value")
        c = getattr(c_item, "value", None) if not isinstance(c_item, dict) else c_item.get("value")
        delta, direction = _delta(b, c)
        rows.append(
            {
                "key": key,
                "label": _SCORE_LABELS.get(key, key),
                "baseline": b,
                "candidate": c,
                "delta": delta,
                "direction": direction,
            }
        )
    return rows


def _composite_delta(base: AuditReport, cand: AuditReport) -> dict | None:
    b = _composite_avr(base)
    c = _composite_avr(cand)
    if b is None and c is None:
        return None
    delta, direction = _delta(b, c)
    return {
        "baseline": b,
        "candidate": c,
        "delta": delta,
        "direction": direction,
    }


def _entity_changes(base: AuditReport, cand: AuditReport) -> dict:
    def by_label(entities):
        out = {}
        for e in entities:
            out.setdefault(e.canonical_name.lower().strip(), e)
        return out

    b, c = by_label(base.entities), by_label(cand.entities)
    added = [
        {"id": e.entity_id, "label": e.canonical_name, "kind": e.kind.value}
        for label, e in c.items()
        if label not in b
    ]
    removed = [
        {"id": e.entity_id, "label": e.canonical_name, "kind": e.kind.value}
        for label, e in b.items()
        if label not in c
    ]
    changed = []
    for label in [x for x in b if x in c]:
        be, ce = b[label], c[label]
        comparisons = (
            ("occurrence_count", len(be.occurrences), len(ce.occurrences)),
            ("is_central", be.is_central, ce.is_central),
            ("kind", be.kind.value, ce.kind.value),
        )
        for field_name, before, after in comparisons:
            if before != after:
                changed.append(
                    {
                        "label": ce.canonical_name,
                        "field": field_name,
                        "before": before,
                        "after": after,
                    }
                )
    return {"added": added, "removed": removed, "changed": changed}


def _eav_changes(base: AuditReport, cand: AuditReport) -> tuple[list[dict], list[dict]]:
    def by_key(rows):
        out = {}
        for r in rows:
            out.setdefault((r.entity_name.lower().strip(), r.attribute), r)
        return out

    b, c = by_key(base.eav_rows), by_key(cand.eav_rows)
    improved: list[dict] = []
    regressed: list[dict] = []
    for key, br in b.items():
        cr = c.get(key)
        if cr is None:
            continue
        before, after = br.status.value, cr.status.value
        if before == "not_applicable" or after == "not_applicable":
            continue
        b_rank, c_rank = EAV_RANK.get(before, -1), EAV_RANK.get(after, -1)
        if b_rank == c_rank:
            continue
        entry = {
            "entity": cr.entity_name,
            "attribute": cr.attribute,
            "before_status": before,
            "after_status": after,
        }
        if cr.evidence_excerpt:
            entry["evidence_excerpt"] = cr.evidence_excerpt
        (improved if c_rank > b_rank else regressed).append(entry)
    return improved, regressed


def _triple_changes(base: AuditReport, cand: AuditReport) -> dict:
    def triple_text(t) -> str:
        return f"{t.subject} — {t.predicate} → {t.object_}"

    def by_id(triples):
        out = {}
        for t in triples:
            out.setdefault(t.triple_id, t)
        return out

    def by_spo(triples):
        out = {}
        for t in triples:
            key = (_norm(t.subject), _norm(t.predicate), _norm(t.object_))
            out.setdefault(key, t)
        return out

    b_id, c_id = by_id(base.triples), by_id(cand.triples)
    c_spo = by_spo(cand.triples)
    added, removed, status_changed = [], [], []
    matched_c: set[str] = set()
    for tid, bt in b_id.items():
        ct = c_id.get(tid)
        if ct is None:
            ct = c_spo.get((_norm(bt.subject), _norm(bt.predicate), _norm(bt.object_)))
        if ct is None:
            removed.append(
                {
                    "id": bt.triple_id,
                    "triple": triple_text(bt),
                    "type": bt.triple_type.value,
                    "status": bt.status.value,
                }
            )
            continue
        matched_c.add(ct.triple_id)
        if bt.status != ct.status:
            status_changed.append(
                {
                    "triple": triple_text(ct),
                    "before": bt.status.value,
                    "after": ct.status.value,
                }
            )
    for tid, ct in c_id.items():
        if tid in matched_c:
            continue
        if (_norm(ct.subject), _norm(ct.predicate), _norm(ct.object_)) in {
            (_norm(b.subject), _norm(b.predicate), _norm(b.object_))
            for b in base.triples
        }:
            continue
        added.append(
            {
                "id": ct.triple_id,
                "triple": triple_text(ct),
                "type": ct.triple_type.value,
                "status": ct.status.value,
            }
        )
    return {"added": added, "removed": removed, "status_changed": status_changed}


def _coverage_delta(base: AuditReport, cand: AuditReport) -> dict:
    def by_query(rows):
        out = {}
        for r in rows:
            out.setdefault(_norm(r.query_text), r)
        return out

    b, c = by_query(base.coverage_rows), by_query(cand.coverage_rows)
    improved, regressed = [], []
    for key, br in b.items():
        cr = c.get(key)
        if cr is None:
            continue
        before, after = br.status.value, cr.status.value
        if before not in COVERAGE_RANK or after not in COVERAGE_RANK:
            continue
        b_rank, c_rank = COVERAGE_RANK[before], COVERAGE_RANK[after]
        if b_rank == c_rank:
            continue
        entry = {
            "query": cr.query_text,
            "before_status": before,
            "after_status": after,
        }
        (improved if c_rank > b_rank else regressed).append(entry)
    added_queries = len([k for k in c if k not in b])
    removed_queries = len([k for k in b if k not in c])
    fcs_b = base.scores["FCS"].value if "FCS" in base.scores else None
    fcs_c = cand.scores["FCS"].value if "FCS" in cand.scores else None

    def _is_covered(r):
        st = r.status.value if hasattr(r.status, "value") else str(r.status)
        return st in ("covered", "partial")

    base_covered = len([r for r in base.coverage_rows if _is_covered(r)])
    cand_covered = len([r for r in cand.coverage_rows if _is_covered(r)])
    total_queries = max(len(base.coverage_rows), len(cand.coverage_rows), 1 if (base_covered or cand_covered) else 0)

    return {
        "improved": improved,
        "regressed": regressed,
        "added_queries": added_queries,
        "removed_queries": removed_queries,
        "baseline_fcs": fcs_b,
        "candidate_fcs": fcs_c,
        "baseline_covered": base_covered,
        "candidate_covered": cand_covered,
        "total": total_queries,
    }



def _claim_changes(base: AuditReport, cand: AuditReport) -> tuple[list[dict], list[dict]]:
    c_by_stmt = {}
    for c in cand.claims:
        c_by_stmt.setdefault(_norm(c.statement), c)
    supported, unsupported = [], []
    for b_claim in base.claims:
        c_claim = c_by_stmt.get(_norm(b_claim.statement))
        if c_claim is None:
            continue
        before = b_claim.verification_state.value
        after = c_claim.verification_state.value
        entry = {
            "claim": b_claim.statement,
            "baseline_id": b_claim.claim_id,
            "candidate_id": c_claim.claim_id,
            "baseline_state": before,
            "candidate_state": after,
        }
        if before == "unverified" and after == "verified":
            supported.append(entry)
        elif before == "verified" and after in ("unverified", "conflicting"):
            unsupported.append(entry)
    return supported, unsupported


def _report_findings(report: AuditReport) -> list[Finding]:
    """Every Finding in the report (findings + recommendations + passage findings)."""
    seen: dict[str, Finding] = {}
    for group in (report.findings, report.recommendations, report.passage_findings):
        for finding in group:
            seen.setdefault(finding.finding_id, finding)
    return list(seen.values())


def _finding_changes(base: AuditReport, cand: AuditReport) -> tuple[list[Finding], list[Finding], list[str]]:
    cand_findings = _report_findings(cand)
    cand_by_id = {f.finding_id: f for f in cand_findings}
    remaining = list(cand_findings)
    resolved: list[Finding] = []
    new: list[Finding] = []
    still_open: list[str] = []
    for bf in _report_findings(base):
        cf = cand_by_id.get(bf.finding_id)
        if cf is not None:
            remaining.remove(cf)
        else:
            # Fallback: match by normalized title.
            cf = next(
                (x for x in remaining if _norm(x.title) == _norm(bf.title)), None
            )
            if cf is not None:
                remaining.remove(cf)
        if cf is None:
            resolved.append(bf)
        elif cf.status.value == "done":
            resolved.append(bf)
        elif cf.status.value == _FINDING_ID_LIKE:
            still_open.append(cf.finding_id)
    new.extend(remaining)
    return resolved, new, still_open


def _gate_change(base: AuditReport, cand: AuditReport) -> dict | None:
    b_status = base.gate.status.value
    c_status = cand.gate.status.value
    b_crit = [_issue_text(i) for i in base.gate.critical_issues]
    c_crit = [_issue_text(i) for i in cand.gate.critical_issues]
    if b_status == "not_configured" and c_status == "not_configured" and not b_crit and not c_crit:
        return None
    return {
        "baseline": b_status,
        "candidate": c_status,
        "improved": GATE_RANK.get(c_status, 0) > GATE_RANK.get(b_status, 0),
        "new_critical": [i for i in c_crit if i not in b_crit],
        "removed_critical": [i for i in b_crit if i not in c_crit],
    }


def compare_reports(base: AuditReport, cand: AuditReport) -> ComparisonResult:
    """Compare two audit reports (PRD FR-17).

    Deltas are always computed; when the runs are not like-for-like the result
    carries ``like_for_like=False`` plus warnings naming exactly what differs.
    """
    like_for_like, warnings = _like_for_like(base, cand)
    eav_improved, eav_regressed = _eav_changes(base, cand)
    supported, unsupported = _claim_changes(base, cand)
    resolved, new, still_open = _finding_changes(base, cand)
    return ComparisonResult(
        baseline_id=base.audit_metadata.run_id,
        candidate_id=cand.audit_metadata.run_id,
        score_delta=_score_delta(base, cand),
        composite_delta=_composite_delta(base, cand),
        entity_changes=_entity_changes(base, cand),
        eav_improved=eav_improved,
        eav_regressed=eav_regressed,
        triple_changes=_triple_changes(base, cand),
        coverage_delta=_coverage_delta(base, cand),
        claims_newly_supported=supported,
        claims_newly_unsupported=unsupported,
        resolved_findings=resolved,
        new_findings=new,
        still_open=still_open,
        gate_change=_gate_change(base, cand),
        like_for_like=like_for_like,
        warnings=warnings,
    )
