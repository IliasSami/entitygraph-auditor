"""End-to-end integration test for the EGA FastAPI service and audit pipeline."""

import time

import pytest
from ega_api.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    # Use temporary or fresh db
    app = create_app(init_database=True)
    with TestClient(app) as test_client:
        yield test_client


def test_api_e2e_lifecycle(client):
    # 1. Health checks
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

    ready_resp = client.get("/api/v1/health/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] in ("ok", "degraded")

    # 2. Model providers
    providers_resp = client.get("/api/v1/models/providers")
    assert providers_resp.status_code == 200
    providers_data = providers_resp.json()
    assert "providers" in providers_data
    provider_types = [p["type"] for p in providers_data["providers"]]
    assert any(pt in provider_types for pt in ("deterministic", "dummy", "ollama"))

    # 3. Create Project
    proj_payload = {
        "name": "CloudDB Auditing",
        "primary_domain": "clouddb.example.com",
        "description": "High throughput cloud database project",
    }
    proj_resp = client.post("/api/v1/projects", json=proj_payload)
    assert proj_resp.status_code == 201
    proj_data = proj_resp.json()
    project_id = proj_data["project_id"]
    assert bool(project_id)

    # 4. Ingest content
    doc_markdown = """# CloudDB Titan
CloudDB Titan is a distributed, low-latency NewSQL database engineered for high-concurrency transactional workloads.

## Core Capabilities
- Multi-master active-active replication with Raft consensus.
- ACID transactions across multi-datacenter shards with sub-5ms P99 latency.
- Full compatibility with PostgreSQL wire protocol.

## Security and Compliance
CloudDB Titan implements AES-256 encryption at rest, TLS 1.3 in transit, and complies with SOC-2 Type II standards.
"""
    import_resp = client.post(
        f"/api/v1/content/import?project_id={project_id}",
        json={
            "text": doc_markdown,
            "format": "markdown",
            "filename": "clouddb_overview.md",
        },
    )
    assert import_resp.status_code == 200
    import_data = import_resp.json()
    assert "content_version_id" in import_data
    content_version_id = import_data["content_version_id"]
    summary = import_data["document_summary"]
    assert summary["word_count"] > 30
    assert summary["headings"] >= 2

    # 5. Trigger Audit
    audit_req = {
        "project_id": project_id,
        "content_version_id": content_version_id,
        "page_type": "saas_b2b",
        "depth": "standard",
        "deterministic_only": True,
    }
    audit_create_resp = client.post("/api/v1/audits", json=audit_req)
    assert audit_create_resp.status_code == 202
    audit_data = audit_create_resp.json()
    audit_id = audit_data["audit_id"]
    assert bool(audit_id)

    # 6. Poll for audit completion (background thread executes)
    max_wait_seconds = 10
    start_time = time.time()
    final_status = None
    audit_detail = None

    while time.time() - start_time < max_wait_seconds:
        status_resp = client.get(f"/api/v1/audits/{audit_id}")
        assert status_resp.status_code == 200
        audit_detail = status_resp.json()
        final_status = audit_detail["status"]
        if final_status in ("succeeded", "failed"):
            break
        time.sleep(0.3)

    assert final_status == "succeeded", f"Audit did not succeed: {audit_detail}"
    assert audit_detail["composite"] is not None
    assert audit_detail["gate_status"] in ("pass", "pass_with_fixes", "not_configured")
    assert audit_detail["report"] is not None

    # 7. Check specific sub-resource endpoints
    entities_resp = client.get(f"/api/v1/audits/{audit_id}/entities")
    assert entities_resp.status_code == 200
    entities = entities_resp.json()
    assert len(entities) > 0
    assert any(e.get("canonical_name") == "CloudDB Titan" for e in entities)

    triples_resp = client.get(f"/api/v1/audits/{audit_id}/triples")
    assert triples_resp.status_code == 200
    assert isinstance(triples_resp.json(), list)

    fanout_resp = client.get(f"/api/v1/audits/{audit_id}/fanout")
    assert fanout_resp.status_code == 200
    assert isinstance(fanout_resp.json(), list)

    scores_resp = client.get(f"/api/v1/audits/{audit_id}/scores")
    assert scores_resp.status_code == 200
    scores = scores_resp.json()
    assert "scores" in scores or "EOS" in scores or "eos" in scores
    assert "avr" in scores or "composite" in scores

    report_resp = client.get(f"/api/v1/audits/{audit_id}/report")
    assert report_resp.status_code == 200
    rep = report_resp.json()
    assert rep["audit_metadata"]["central_entity"] == "CloudDB Titan"

    # 8. Writer handoff
    handoff_resp = client.post(f"/api/v1/audits/{audit_id}/writer-handoff")
    assert handoff_resp.status_code == 200
    handoff = handoff_resp.json()
    assert "brief_markdown" in handoff
    assert "actions" in handoff

    # 9. Report Export (Markdown and JSON)
    md_export_resp = client.post(f"/api/v1/audits/{audit_id}/export", json={"format": "markdown"})
    assert md_export_resp.status_code == 200
    assert "text/markdown" in md_export_resp.headers["content-type"]
    assert b"# EntityGraph Auditor Audit Report" in md_export_resp.content

    json_export_resp = client.post(f"/api/v1/audits/{audit_id}/export", json={"format": "json"})
    assert json_export_resp.status_code == 200
    assert "application/json" in json_export_resp.headers["content-type"]

    # 10. Context packs & MCP tools
    packs_resp = client.get("/api/v1/context-packs")
    assert packs_resp.status_code == 200

    mcp_resp = client.get("/api/v1/mcp/tools")
    assert mcp_resp.status_code == 200
