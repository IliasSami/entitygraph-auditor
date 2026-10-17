"""HTTP-level FR-16 test: a context pack imported over the API changes the gate.

This is the end-to-end regression for the P0 gap where packs were loaded but never
reached the gate on the API path. It drives the real REST surface:

1. import a brand pack (multipart ZIP) via ``POST /api/v1/context-packs/import``
2. audit the same content **without** the pack → gate ``not_configured``
3. audit it **with** ``context_pack_ids=[pack_id]`` → gate ``fail`` because the
   pack's critical banned term appears in the copy, and the report is marked
   ``publishable: false`` with a readable critical issue.
"""

from __future__ import annotations

import io
import json
import time
import zipfile

import pytest
from ega_api.main import create_app
from fastapi.testclient import TestClient

BANNED_TERM = "revolutionary"

CONTENT = """# Acme Analytics Engine
Acme Analytics Engine is a real-time analytics platform for data teams.

## Why teams choose Acme
Acme combines streaming ingestion with sub-second queries and managed storage.

## Our ${term} approach
Our ${term} engine removes pipeline latency without adding operational overhead.
""".replace("${term}", BANNED_TERM)


@pytest.fixture(scope="module")
def client():
    app = create_app(init_database=True)
    with TestClient(app) as test_client:
        yield test_client


def _brand_pack_zip() -> bytes:
    brand = {
        "name": "Acme",
        "voice": "direct",
        # A LIST entry keeps ``severity`` (a mapping would drop it).
        "banned_terms": [
            {"term": BANNED_TERM, "severity": "critical", "reason": "unsubstantiated superlative"}
        ],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("brand.json", json.dumps(brand))
        archive.writestr("facts.json", json.dumps({"founded": "1999", "hq": "Oslo"}))
    return buffer.getvalue()


def _wait_for(client: TestClient, audit_id: str, timeout_s: float = 20.0) -> dict:
    deadline = time.time() + timeout_s
    detail: dict = {}
    while time.time() < deadline:
        detail = client.get(f"/api/v1/audits/{audit_id}").json()
        if detail.get("status") in ("succeeded", "failed"):
            return detail
        time.sleep(0.2)
    return detail


def _import_content(client: TestClient, project_id: str, filename: str) -> str:
    resp = client.post(
        f"/api/v1/content/import?project_id={project_id}",
        json={"text": CONTENT, "format": "markdown", "filename": filename},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["content_version_id"]


def test_imported_pack_flips_the_gate_over_http(client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects",
        json={"name": "Pack Gate HTTP", "primary_domain": "acme.example.com"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["project_id"]

    # 1. Import the brand pack (multipart, ZIP, classified by filename stem).
    imported = client.post(
        "/api/v1/context-packs/import",
        files={"file": ("acme_brand_pack.zip", _brand_pack_zip(), "application/zip")},
    )
    assert imported.status_code == 201, imported.text
    pack = imported.json()
    assert pack["rule_count"] >= 1
    pack_id = pack["pack_id"]

    # 2. Baseline: same content, no pack → not configured (no brand rules).
    baseline_cv = _import_content(client, project_id, "acme_baseline.md")
    baseline = client.post(
        "/api/v1/audits",
        json={
            "project_id": project_id,
            "content_version_id": baseline_cv,
            "deterministic_only": True,
        },
    )
    assert baseline.status_code == 202, baseline.text
    baseline_detail = _wait_for(client, baseline.json()["audit_id"])
    assert baseline_detail["status"] == "succeeded", baseline_detail
    assert baseline_detail["gate_status"] == "not_configured"

    # 3. With the pack: the banned term is now critical → gate fail.
    packed_cv = _import_content(client, project_id, "acme_packed.md")
    packed = client.post(
        "/api/v1/audits",
        json={
            "project_id": project_id,
            "content_version_id": packed_cv,
            "deterministic_only": True,
            "context_pack_ids": [pack_id],
        },
    )
    assert packed.status_code == 202, packed.text
    packed_detail = _wait_for(client, packed.json()["audit_id"])
    assert packed_detail["status"] == "succeeded", packed_detail
    assert packed_detail["gate_status"] == "fail"

    report = client.get(f"/api/v1/audits/{packed_detail['audit_id']}/report").json()
    assert report["gate"]["status"] == "fail"
    assert report["gate"]["publishable"] is False

    # The critical issues carry the pack's banned term in readable form (str or GateIssue).
    rendered = " ".join(
        issue if isinstance(issue, str) else str(issue.get("message") or issue.get("title") or issue)
        for issue in report["gate"]["critical_issues"]
    ).lower()
    assert BANNED_TERM in rendered
    assert "prohibited term" in rendered
