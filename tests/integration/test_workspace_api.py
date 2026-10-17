"""Workspace read-model API tests: Entity Hub, Brief Builder, content analysis.

These verify the deterministic, provenance-labelled endpoints that back the
Aentio UI screens. A stub workflow runner seeds a realistic audit report so the
read-models have real material to derive from.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

MARKDOWN = """# Acme Roof Inspections

Acme Roof Inspections checks residential roofs in Austin, Texas. We inspect
shingles, flashing, and gutters, then send a written report within 24 hours.

## What an inspection includes

A full inspection covers the roof surface, attic ventilation, and drainage.
The cost is $149 per visit. Call (512) 555-0100 to book an inspection.
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EGA_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("EGA_APP_ENCRYPTION_KEY", "")
    from ega_api.config import get_settings

    get_settings.cache_clear()
    from ega_api import db as dbmod

    dbmod.reset_engine()
    from ega_api.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
    from ega_api.services.audits import bus

    bus.clear()
    dbmod.reset_engine()
    get_settings.cache_clear()


@pytest.fixture()
def rich_runner(monkeypatch):
    """Stub runner that populates entities, EAV rows, fan-out, findings, claims."""
    from ega_api.services import audits as audits_svc
    from ega_schemas.claims import Claim
    from ega_schemas.entities import EAVRow, Entity
    from ega_schemas.enums import (
        Confidence,
        EAVStatus,
        EntityKind,
        GateStatus,
        IntentClass,
        PageType,
        Severity,
        StageStatus,
    )
    from ega_schemas.fanout import FanoutQuery
    from ega_schemas.findings import Finding
    from ega_schemas.report import Scorecard, ScoreComponent
    from ega_schemas.run import AuditRunState, StageRecord

    async def runner(state: AuditRunState, progress=None) -> AuditRunState:
        state.page_type = PageType.SERVICE
        state.central_entity = "Acme Roof Inspections"
        state.primary_intent = IntentClass.COMMERCIAL
        state.language = "en"
        state.gate_status = GateStatus.PASS
        state.entities = [
            Entity(
                entity_id="e1",
                canonical_name="Acme Roof Inspections",
                kind=EntityKind.ORGANIZATION,
                aliases=["Acme Roofing"],
                is_central=True,
            ),
            Entity(entity_id="e2", canonical_name="Roof inspection", kind=EntityKind.PRODUCT_SERVICE),
            Entity(entity_id="e3", canonical_name="Austin", kind=EntityKind.LOCATION),
        ]
        state.eav_rows = [
            EAVRow(
                eav_id="a1",
                entity_name="Acme Roof Inspections",
                attribute="price",
                value="$149 per visit",
                status=EAVStatus.EXPLICIT,
            ),
            EAVRow(
                eav_id="a2",
                entity_name="Acme Roof Inspections",
                attribute="location",
                value="Austin, Texas",
                status=EAVStatus.EXPLICIT,
            ),
        ]
        state.fanout = [
            FanoutQuery(query_id="q1", query_text="how much does a roof inspection cost", importance=3),
            FanoutQuery(query_id="q2", query_text="what does a roof inspection include", importance=2),
        ]
        state.findings = [
            Finding(
                finding_id="f1",
                category="entity_gap",
                severity=Severity.HIGH,
                title="Missing warranty coverage entity",
                what="No warranty information present.",
            )
        ]
        state.claims = [
            Claim(claim_id="c1", statement="Written report delivered within 24 hours")
        ]
        state.scorecard = Scorecard(
            components={
                k: ScoreComponent(value=7.0, key=k, label=k, confidence=Confidence.MEDIUM)
                for k in ("EOS", "ERS", "KGR", "FCS", "PRS", "CWS", "HRS")
            },
            profile="commercial_default",
        )
        state.stages.append(
            StageRecord(node="stub", label="Stub", status=StageStatus.SUCCEEDED, origin="deterministic")
        )
        if progress:
            progress(state.stages[-1])
        return state

    monkeypatch.setattr(audits_svc, "default_workflow_runner", runner)
    return runner


def _seed_audit(client: TestClient) -> tuple[str, str]:
    project = client.post(
        "/api/v1/projects",
        json={"name": "Acme", "central_entity": "Acme Roof Inspections", "base_url": "https://acme.test"},
    ).json()
    pid = project["project_id"]
    imported = client.post(
        "/api/v1/content/import",
        json={"text": MARKDOWN, "format": "markdown"},
        params={"project_id": pid},
    ).json()
    created = client.post(
        "/api/v1/audits",
        json={
            "project_id": pid,
            "content_version_id": imported["content_version_id"],
            "primary_query": "roof inspection austin",
        },
    )
    assert created.status_code == 202, created.text
    audit_id = created.json()["audit_id"]
    deadline = time.time() + 15
    while time.time() < deadline:
        body = client.get(f"/api/v1/audits/{audit_id}").json()
        if body.get("status") in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert body["status"] == "succeeded", body.get("error")
    return pid, audit_id


def test_entity_registry_from_audit(client: TestClient, rich_runner):
    pid, _ = _seed_audit(client)
    resp = client.get("/api/v1/workspace/entities", params={"project_id": pid})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_audits"] == 1
    names = {e["name"] for e in body["entities"]}
    assert "Acme Roof Inspections" in names
    central = next(e for e in body["entities"] if e["name"] == "Acme Roof Inspections")
    assert central["pages_used"] == 1
    assert central["facts_count"] >= 2
    assert any(f["property"] == "price" and f["value"] == "$149 per visit" for f in central["facts"])
    assert central["kind"] == "Organization"
    assert central["at_id"].startswith("https://acme.test")
    assert "heuristic" in body["disclaimer"].lower()


def test_entity_registry_unknown_project_is_404(client: TestClient):
    resp = client.get("/api/v1/workspace/entities", params={"project_id": "nope"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "PROJECT_NOT_FOUND"


def test_brief_generation_from_real_audit(client: TestClient, rich_runner):
    pid, audit_id = _seed_audit(client)
    resp = client.post(
        "/api/v1/workspace/briefs/generate",
        json={"project_id": pid, "target_query": "roof inspection austin"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["basis"]["audit_id"] == audit_id
    kinds = {s["kind"] for s in body["sources"]}
    assert "question" in kinds  # fan-out queries
    assert "gap" in kinds  # entity_gap finding
    assert "fact" in kinds  # claim
    assert len(body["sections"]) >= 2
    first = body["sections"][0]
    assert first["h2_number"] == 1
    assert first["title"]
    assert body["target_query"] == "roof inspection austin"
    assert "deterministic" in body["disclaimer"].lower()


def test_brief_empty_project_is_honest(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": "Empty Co"}).json()
    resp = client.post(
        "/api/v1/workspace/briefs/generate", json={"project_id": project["project_id"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sources"] == []
    assert body["basis"]["audit_id"] is None
    assert "nothing here is model-generated" in body["disclaimer"].lower()


def test_analyze_content_deterministic(client: TestClient):
    resp = client.post(
        "/api/v1/workspace/analyze",
        json={
            "text": "# Is this a question?\n\nBody copy. " + "word " * 120 + "guaranteed results now.",
            "primary_query": "test",
            "target_entities": ["Acme Roof Inspections", "roof inspection"],
            "banned_terms": ["guaranteed results"],
            "word_target": 200,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metrics"]["word_count"] > 100
    assert body["metrics"]["flesch_kincaid_grade"] != 0
    assert any(h["is_question"] for h in body["headings"])
    assert body["violations"] and body["violations"][0]["term"] == "guaranteed results"
    missing = [e for e in body["entities"] if e["name"] == "Acme Roof Inspections"]
    assert missing and missing[0]["status"] == "missing"
    assert 0 <= body["overall_score"] <= 100
    assert len(body["dimensions"]) == 5
    assert any(r["id"].startswith("banned_") for r in body["recommendations"])
    assert "deterministic" in body["disclaimer"].lower()


def test_analyze_empty_text_is_safe(client: TestClient):
    resp = client.post("/api/v1/workspace/analyze", json={"text": ""})
    assert resp.status_code == 200
    body = resp.json()
    assert body["metrics"]["word_count"] == 0
    assert body["overall_score"] >= 0
