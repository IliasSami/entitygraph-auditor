"""Integration test for the LangGraph audit workflow."""

from ega_schemas import AuditCreateRequest, GateStatus, PageType, ScoreKey

from auditor.workflows import execute_audit


def test_full_audit_workflow_execution():
    content = """# DataVault Enterprise
DataVault Enterprise provides high-throughput relational database replication for cloud workloads.

## Core Architecture
- Zero-loss failover synchronization
- Multi-region active-active clusters
- AES-256 encrypted storage

## Compliance & Security
Our solution is SOC-2 Type II compliant and ISO-27001 certified.
"""
    req = AuditCreateRequest(
        content=content,
        title="DataVault Enterprise",
        page_type=PageType.SAAS_B2B,
    )
    state, report = execute_audit(req)

    assert state.run_id.startswith("run_")
    assert report.audit_metadata.central_entity == "DataVault Enterprise"
    assert report.gate.status in (GateStatus.PASS, GateStatus.PASS_WITH_FIXES, GateStatus.NOT_CONFIGURED)
    assert report.gate.publishable is True
    assert report.scores[ScoreKey.EOS.value].value > 5.0
    assert len(report.recommendations) > 0
    assert report.swot is not None
    assert len(report.swot.strengths) > 0

    # Ensure all pipeline nodes were visited in timeline
    visited_nodes = [t["node"] for t in state.timeline]
    assert "parse_content" in visited_nodes
    assert "intake_classifier" in visited_nodes
    assert "fanout_agent" in visited_nodes
    assert "entity_eav_agent" in visited_nodes
    assert "triples_agent" in visited_nodes
    assert "claims_agent" in visited_nodes
    assert "coverage_agent" in visited_nodes
    assert "scoring_node" in visited_nodes
    assert "handoff_agent" in visited_nodes
    assert "critic_agent" in visited_nodes
