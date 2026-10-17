"""Recommendation priority ordering (PRD §9.6).

Priority = (Impact × Confidence) / Effort with an explicit gate override:
gate-critical findings always float to the top regardless of score. Effort is
guarded with a minimum of 1 so the division can never explode.
"""

from __future__ import annotations

from ega_schemas.enums import RecommendationStatus, Severity
from ega_schemas.findings import Finding

#: Severity ordering used as a tiebreaker after the priority score.
SEVERITY_RANK: dict[str, int] = {
    Severity.CRITICAL.value: 4,
    Severity.HIGH.value: 3,
    Severity.MEDIUM.value: 2,
    Severity.LOW.value: 1,
    Severity.INFO.value: 0,
}

_OPEN_STATUSES = (RecommendationStatus.OPEN, RecommendationStatus.IN_PROGRESS)


def effective_effort(finding: Finding) -> int:
    """Effort used in the priority formula, guarded to a minimum of 1 (PRD §9.6)."""
    try:
        return max(1, int(finding.effort))
    except (TypeError, ValueError):
        return 1


def compute_priority(finding: Finding) -> float:
    """Compute and persist ``priority_score`` = (impact × confidence) / effort."""
    impact = max(1, int(finding.impact))
    confidence = max(1, int(finding.confidence_numeric))
    finding.priority_score = round(impact * confidence / effective_effort(finding), 1)
    return finding.priority_score


def is_gate_critical(finding: Finding) -> bool:
    """True for open gate-critical findings (PRD §9.5/§9.6).

    The schema has no explicit ``gate_critical`` flag, so an open finding with
    ``critical`` severity is treated as gate-critical.
    """
    return finding.severity == Severity.CRITICAL and finding.status in _OPEN_STATUSES


def _sort_key(finding: Finding) -> tuple[int, float, int, int, str]:
    return (
        0 if is_gate_critical(finding) else 1,          # gate-critical first
        -finding.priority_score,                        # priority score desc
        -SEVERITY_RANK.get(finding.severity.value, 1),  # severity desc
        effective_effort(finding),                      # effort asc
        finding.finding_id,                             # stable, reproducible
    )


def priority_sort(findings: list[Finding]) -> list[Finding]:
    """Recompute priorities and return findings in recommended work order.

    Ordering: gate-critical first, then priority score (desc), severity (desc),
    effort (asc), and finally ``finding_id`` so the order is reproducible.
    The rank of a finding is its 1-based position in the returned list.
    """
    for finding in findings:
        compute_priority(finding)
    return sorted(findings, key=_sort_key)


def assign_ranks(findings: list[Finding]) -> dict[str, int]:
    """Return ``{finding_id: 1-based rank}`` for the recommended work order."""
    return {f.finding_id: rank for rank, f in enumerate(priority_sort(findings), start=1)}


prioritize_findings = priority_sort
__all__ = [
    "SEVERITY_RANK",
    "effective_effort",
    "compute_priority",
    "is_gate_critical",
    "priority_sort",
    "prioritize_findings",
    "assign_ranks",
]

