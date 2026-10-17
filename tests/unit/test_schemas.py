"""Unit tests for ega_schemas."""

from ega_schemas import (
    AuditMetadata,
    AuditReport,
    ComponentScore,
    Confidence,
    Entity,
    EntityKind,
    Finding,
    GateResult,
    GateStatus,
    PageType,
    ScoreKey,
    Severity,
)


def test_entity_creation():
    entity = Entity(
        entity_id="ent-1",
        canonical_name="Acme Corp",
        kind=EntityKind.ORGANIZATION,
        is_central=True,
    )
    assert entity.canonical_name == "Acme Corp"
    assert entity.is_central is True
    assert entity.kind == EntityKind.ORGANIZATION


def test_finding_priority_calculation():
    # Priority = (Impact × Confidence) / Effort
    # Impact=4, Confidence=5, Effort=2 -> (4 * 5) / 2 = 10.0
    finding = Finding(
        finding_id="F-001",
        category="eav_gap",
        severity=Severity.HIGH,
        title="Missing SLA",
        what="State explicit response time",
        impact=4,
        confidence_numeric=5,
        effort=2,
    )
    score = finding.calculate_priority()
    assert score == 10.0
    assert finding.priority_score == 10.0


def test_audit_report_serialization():
    meta = AuditMetadata(
        project_id="proj-1",
        run_id="run-1",
        page_type=PageType.SERVICE,
        created_at="2026-10-16T12:00:00Z",
        content_hash="abc123hash",
    )
    report = AuditReport(
        audit_metadata=meta,
        gate=GateResult(status=GateStatus.PASS),
        scores={
            ScoreKey.EOS.value: ComponentScore(
                score_key=ScoreKey.EOS,
                value=8.5,
                weight=15.0,
                confidence=Confidence.HIGH,
                rationale="Solid entity salience",
            )
        },
    )
    dumped = report.model_dump()
    assert dumped["audit_metadata"]["project_id"] == "proj-1"
    assert dumped["scores"]["EOS"]["value"] == 8.5
    assert dumped["gate"]["status"] == "pass"
