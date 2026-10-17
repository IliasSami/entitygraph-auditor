"""Unit tests for the EntityGraph Auditor MCP server and tools."""

from ega_mcp import (
    TOOL_SPECS,
    create_mcp_server,
    tool_analyze_entities,
    tool_check_brand_compliance,
    tool_get_audit_report,
    tool_run_content_audit,
)
from ega_mcp.tools import _issue_text


def test_tool_specs():
    assert len(TOOL_SPECS) >= 4
    tool_names = [t["name"] for t in TOOL_SPECS]
    assert "run_content_audit" in tool_names
    assert "analyze_entities" in tool_names
    assert "check_brand_compliance" in tool_names
    assert "get_audit_report" in tool_names


def test_mcp_server_instantiation():
    server = create_mcp_server()
    assert server.name == "entitygraph-auditor"


def test_mcp_brand_compliance_tool():
    # Compliant content
    res_pass = tool_check_brand_compliance("High performance transactional database engine.")
    assert res_pass["status"] == "pass"
    assert res_pass["publishable"] is True
    assert len(res_pass["violations"]) == 0

    # Non-compliant content with banned term
    res_fail = tool_check_brand_compliance("Guaranteed #1 ranking on Google in 48 hours.")
    assert res_fail["status"] == "fail"
    assert res_fail["publishable"] is False
    assert len(res_fail["violations"]) > 0


def test_mcp_analyze_entities_tool():
    content = """# HyperScale Cloud
HyperScale Cloud delivers geo-distributed container orchestration with Kubernetes support.
"""
    res = tool_analyze_entities(content)
    assert res["central_entity"] == "HyperScale Cloud"
    assert len(res["entities"]) > 0
    assert len(res["eav_rows"]) > 0
    assert len(res["triples"]) > 0


def test_mcp_run_content_audit_tool():
    content = """# DataLake Enterprise
DataLake Enterprise is a petabyte-scale analytics engine with sub-second query latency.
## Core Capabilities
- Parquet and Iceberg columnar storage
- Automated data partitioning
"""
    res = tool_run_content_audit(content, page_type="saas_b2b")
    assert res["central_entity"] == "DataLake Enterprise"
    assert res["page_type"] == "saas_b2b"
    assert "scores" in res
    assert len(res["scores"]) >= 6
    assert "EOS" in res["scores"]
    assert "swot" in res
    assert "recommendations" in res
    assert "disclaimer" in res


def test_mcp_gate_issue_text_is_readable():
    """Gate issues may be plain strings or structured GateIssue objects."""
    from ega_schemas.scores import GateIssue

    assert _issue_text("Banned term detected") == "Banned term detected"
    assert _issue_text(GateIssue(message="Prohibited term: 'guaranteed #1'")) == (
        "Prohibited term: 'guaranteed #1'"
    )
    # A title takes precedence over the message.
    assert _issue_text(GateIssue(title="Off-brand language", message="ignore me")) == (
        "Off-brand language"
    )


def test_mcp_run_content_audit_persists_and_resolves():
    """Verify MCP audits are persisted into AuditRun table and resolve via tool_get_audit_report."""
    from ega_api.db import get_sessionmaker
    from ega_api.models import AuditRun

    content = """# Apex Database
Apex Database delivers distributed transactions and low-latency replication.
"""
    res = tool_run_content_audit(content, page_type="saas_b2b", primary_query="distributed sql database")
    run_id = res["run_id"]
    assert run_id.startswith("run_")

    # 1. Resolves via tool_get_audit_report
    fetched = tool_get_audit_report(run_id)
    assert fetched["status"] == "succeeded"
    assert fetched["audit_id"] == run_id
    assert fetched["report"] is not None
    assert fetched["composite"] is not None

    # 2. Exists as an AuditRun database row
    session = get_sessionmaker()()
    try:
        db_run = session.get(AuditRun, run_id)
        assert db_run is not None
        assert db_run.audit_id == run_id
        assert db_run.central_entity == "Apex Database"
        assert db_run.primary_query == "distributed sql database"
        assert db_run.status == "succeeded"
    finally:
        session.close()

