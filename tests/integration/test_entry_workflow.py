"""End-to-end tests for the REAL API workflow entry point (PRD §8 / FR-11 / FR-16).

``tests/integration/test_audit_workflow.py`` covers the LangGraph graph path and
``tests/integration/test_api_core.py`` drives the API with a stub runner. Neither
exercises ``auditor.workflows.entry.run_audit``, which is what the running API
actually calls — so the PRD's bounded critic loop, stage telemetry and brand-pack
gate behaviour are asserted here directly.
"""

from __future__ import annotations

import asyncio

from ega_schemas.enums import GateStatus, StageStatus
from ega_schemas.run import AuditCreateRequest, AuditRunState

from auditor.workflows.entry import run_audit

# Exercises heading hierarchy, lists, entity names and (in the banned-term test)
# a claim the brand pack is configured to forbid.
NEUTRAL_CONTENT = """# Northwind Analytics Platform

Northwind Analytics Platform helps operations teams move warehouse data into
dashboards without writing pipeline code.

## Core capabilities
- Incremental sync jobs
- Column-level lineage
- Scheduled reconciliation

## Who uses it
Data teams at mid-market retailers use Northwind for weekly reporting.
"""

BANNED_CLAIM_CONTENT = NEUTRAL_CONTENT + """
## Results
Teams see guaranteed 10x ROI within the first quarter of adoption.
"""


def _state(content: str = NEUTRAL_CONTENT) -> AuditRunState:
    request = AuditCreateRequest(project_id="proj_test", content_text=content)
    return AuditRunState(
        run_id="run_entry_test",
        project_id="proj_test",
        request=request,
    )


def test_real_workflow_runs_full_pipeline_with_bounded_critic() -> None:
    state = asyncio.run(run_audit(_state()))

    nodes = [record.node for record in state.stages]
    for expected in ("parse", "classify", "fanout", "entities", "triples", "claims", "scoring", "handoff", "critic"):
        assert expected in nodes, f"missing stage {expected!r}; ran {nodes}"

    # Every stage must settle — nothing left running, nothing failed.
    assert all(record.status is StageStatus.SUCCEEDED for record in state.stages)

    # PRD §8.2: a final critic runs, bounded to at most 2 repair loops.
    assert state.critic_loops in (1, 2)
    assert state.critic_notes, "critic must record its notes"

    # Evidence-bearing outputs the report depends on.
    assert state.scorecard is not None
    assert state.entities, "entity extraction produced nothing"
    assert state.recommendations, "no recommendations produced"
    # FR-18: a measurement plan must be carried through to the report.
    assert state.measurement_plan, "measurement plan not captured from handoff"


def test_brand_pack_payload_reaches_the_gate() -> None:
    state = _state(BANNED_CLAIM_CONTENT)
    state.banned_terms = [
        {"term": "guaranteed 10x ROI", "reason": "unsubstantiated performance claim", "severity": "critical"}
    ]

    asyncio.run(run_audit(state))

    # Without the pack payload this used to report NOT_CONFIGURED regardless.
    assert state.gate_status is GateStatus.FAIL, state.gate_issues
    assert any("guaranteed 10x ROI" in issue.message for issue in state.gate_issues)

    gate_issue = state.scorecard.gate
    assert gate_issue.publishable is False, "a gate FAIL must block 'ready to publish'"
    assert gate_issue.status is GateStatus.FAIL


def test_without_a_brand_pack_gate_reports_not_configured() -> None:
    state = _state(NEUTRAL_CONTENT)
    asyncio.run(run_audit(state))

    assert not state.banned_terms and not state.brand_rules
    assert state.gate_status is GateStatus.NOT_CONFIGURED
    assert state.scorecard.gate.publishable is True
