"""Golden Evaluation Suite for EntityGraph Auditor (PRD §17, EVALUATION.md).

Verifies the four core archetypes:
1. High-quality SaaS/Tech guide (High EOS/PRS, Gate PASS)
2. Local emergency service (Austin plumber, high EAV completeness)
3. Keyword-stuffed thin affiliate (Low EOS, stuffing penalties detected)
4. High-risk medical hazard (Gate FAIL, critical compliance disqualifier)
"""

from ega_api.main import create_app
from ega_parsers import detect_repeated_phrases
from ega_schemas.audit import AuditCreateRequest
from ega_schemas.enums import GateStatus, PageType, ScoreKey
from fastapi.testclient import TestClient

from auditor.evaluation.golden_cases import (
    CASE_HEALTH_HAZARD,
    CASE_INFO_TECH,
    CASE_LOCAL_SERVICE,
    CASE_THIN_STUFFED,
)
from auditor.workflows.audit_graph import execute_audit


def test_case_info_tech_high_authority():
    """Golden Case 1: In-depth technical architecture guide."""
    req = AuditCreateRequest(
        content=CASE_INFO_TECH.content,
        title=CASE_INFO_TECH.name,
        page_type=PageType.ARTICLE,
    )
    state, report = execute_audit(req)

    # 1. Gate publication check
    assert report.gate.publishable is True
    assert report.gate.status in CASE_INFO_TECH.expected_gate_statuses
    assert len(report.gate.critical_issues) == 0

    # 2. Scorecard checks
    assert report.composite_avr is not None
    assert report.composite_avr >= CASE_INFO_TECH.min_composite_avr

    # EOS (Entity Orientation Score) must be strong
    eos = report.scores.get(ScoreKey.EOS.value)
    if eos:
        assert eos.value >= (CASE_INFO_TECH.min_eos or 7.0)

    # 3. Central Entity Identification
    assert "pgbouncer" in report.audit_metadata.central_entity.lower() or "postgresql" in report.audit_metadata.central_entity.lower()
    assert len(report.entities) >= 2


def test_case_local_service_entities_and_trust():
    """Golden Case 2: Local emergency service (Austin Emergency Plumber)."""
    req = AuditCreateRequest(
        content=CASE_LOCAL_SERVICE.content,
        title=CASE_LOCAL_SERVICE.name,
        page_type=PageType.SERVICE,
    )
    state, report = execute_audit(req)

    assert report.gate.publishable is True
    assert report.gate.status in CASE_LOCAL_SERVICE.expected_gate_statuses
    assert len(report.gate.critical_issues) == 0

    # Inferred or explicit page type
    assert report.audit_metadata.page_type == PageType.SERVICE
    assert "plumbing" in report.audit_metadata.central_entity.lower() or "austin" in report.audit_metadata.central_entity.lower()

    # EAV rows should reflect service attributes
    assert len(report.eav_rows) > 0


def test_case_thin_stuffed_penalized_for_repetition():
    """Golden Case 3: Keyword-stuffed thin affiliate page."""
    # Verify deterministic keyword stuffing detection
    repeated = detect_repeated_phrases(CASE_THIN_STUFFED.content, n_gram=2, min_count=4)
    assert len(repeated) > 0
    # "best vpn" must be flagged as heavily repeated
    assert any("best vpn" in phrase.lower() for phrase, count in repeated)

    req = AuditCreateRequest(
        content=CASE_THIN_STUFFED.content,
        title=CASE_THIN_STUFFED.name,
    )
    state, report = execute_audit(req)

    # Composite AVR should reflect thin content (penalized compared to rich technical guide)
    assert report.composite_avr is not None
    assert report.composite_avr <= CASE_THIN_STUFFED.max_composite_avr

    # EOS should reflect repetition penalties (stuffing explicitly flagged in lost points)
    eos = report.scores.get(ScoreKey.EOS.value)
    assert eos is not None
    assert any("stuffing" in reason.lower() for reason in eos.lost_points_reasons)


def test_case_health_hazard_triggers_gate_failure():
    """Golden Case 4: High-risk unsubstantiated miracle medical claims."""
    req = AuditCreateRequest(
        content=CASE_HEALTH_HAZARD.content,
        title=CASE_HEALTH_HAZARD.name,
    )
    state, report = execute_audit(req)

    # High-stakes medical claims must cause publication GATE FAILURE (PRD §9.5, §17)
    assert report.gate.status == GateStatus.FAIL
    assert report.gate.publishable is False
    assert len(report.gate.critical_issues) > 0

    # Ensure critical issue message pinpoints unverified / high-stakes compliance triggers
    issues_text = " ".join(report.gate.critical_issues).lower()
    assert any(term in issues_text for term in ("compliance", "high-risk", "unverified", "claim", "cure"))


def test_deterministic_reproducibility():
    """Principle 1: Bit-identical scores across runs for the exact same inputs."""
    req1 = AuditCreateRequest(content=CASE_INFO_TECH.content, page_type=PageType.ARTICLE)
    req2 = AuditCreateRequest(content=CASE_INFO_TECH.content, page_type=PageType.ARTICLE)

    state1, rep1 = execute_audit(req1, run_id="run_deterministic_1")
    state2, rep2 = execute_audit(req2, run_id="run_deterministic_2")

    assert rep1.composite_avr == rep2.composite_avr
    assert rep1.gate.status == rep2.gate.status
    assert len(rep1.entities) == len(rep2.entities)
    assert [s.value for s in rep1.scores.values()] == [s.value for s in rep2.scores.values()]


def test_golden_cases_via_api_e2e():
    """Validate golden cases running through the FastAPI REST layer."""
    app = create_app(init_database=True)
    with TestClient(app) as client:
        # Create Project
        proj_resp = client.post("/api/v1/projects", json={"name": "Eval Suite", "primary_domain": "eval.example.com"})
        assert proj_resp.status_code == 201
        pid = proj_resp.json()["project_id"]

        # 1. Ingest Case 1 (Tech Guide)
        c1_imp = client.post(
            f"/api/v1/content/import?project_id={pid}",
            json={"text": CASE_INFO_TECH.content, "format": "markdown", "filename": "pgbouncer_guide.md"},
        )
        assert c1_imp.status_code == 200
        c1_id = c1_imp.json()["content_version_id"]

        # Audit Case 1
        aud1 = client.post("/api/v1/audits", json={"project_id": pid, "content_version_id": c1_id, "deterministic_only": True})
        assert aud1.status_code == 202
        a1_id = aud1.json()["audit_id"]

        # Wait for completion
        import time
        for _ in range(30):
            st = client.get(f"/api/v1/audits/{a1_id}").json()
            if st["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.1)

        assert st["status"] == "succeeded"
        assert st["gate_status"] in ("pass", "pass_with_fixes", "not_configured")
        assert st["composite"] >= 5.0

        # 2. Ingest Case 4 (Health Hazard)
        c4_imp = client.post(
            f"/api/v1/content/import?project_id={pid}",
            json={"text": CASE_HEALTH_HAZARD.content, "format": "markdown", "filename": "miracle_cure.md"},
        )
        assert c4_imp.status_code == 200
        c4_id = c4_imp.json()["content_version_id"]

        aud4 = client.post("/api/v1/audits", json={"project_id": pid, "content_version_id": c4_id, "deterministic_only": True})
        assert aud4.status_code == 202
        a4_id = aud4.json()["audit_id"]

        for _ in range(30):
            st4 = client.get(f"/api/v1/audits/{a4_id}").json()
            if st4["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.1)

        assert st4["status"] == "succeeded"
        assert st4["gate_status"] == "fail"

