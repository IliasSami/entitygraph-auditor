"""Workflow execution entrypoint for async audit jobs (PRD §8.3 / §13.2)."""

from __future__ import annotations

import time
from typing import Callable, Optional

from ega_parsers.document_parser import DocumentParser
from ega_schemas.enums import StageStatus
from ega_schemas.findings import Recommendation, Swot
from ega_schemas.report import GateIssue
from ega_schemas.run import AuditRunState, StageRecord
from ega_scoring.engine import ScoringEngine

from auditor.agents.claims_agent import run_claims_agent
from auditor.agents.coverage_agent import run_coverage_agent
from auditor.agents.critic_agent import run_critic_agent
from auditor.agents.editorial_agent import run_editorial_agent
from auditor.agents.entity_eav_agent import run_entity_eav_agent
from auditor.agents.fanout_agent import run_fanout_agent
from auditor.agents.handoff_agent import run_handoff_agent
from auditor.agents.intake_classifier import run_intake_classifier
from auditor.workflows.audit_graph import create_initial_state

ProgressCallback = Callable[[StageRecord], None]


async def run_audit(state: AuditRunState, progress: Optional[ProgressCallback] = None) -> AuditRunState:
    """Execute the multi-agent workflow over the given AuditRunState, reporting progress."""
    raw_content = ""
    if state.document:
        raw_content = getattr(state.document, "raw_text", "") or getattr(state.document, "original_text", "") or state.document.normalized_text
    elif state.request and state.request.content_text:
        raw_content = state.request.content_text
        state.document = DocumentParser.parse(raw_content)

    # 1. Parsing stage
    t0 = time.monotonic()
    if progress:
        progress(StageRecord(node="parse", label="Parse Content", status=StageStatus.RUNNING))
    if not state.document:
        state.document = DocumentParser.parse(raw_content)
    p_duration = int((time.monotonic() - t0) * 1000)
    rec_parse = StageRecord(node="parse", label="Parse Content", status=StageStatus.SUCCEEDED, duration_ms=p_duration)
    state.stages.append(rec_parse)
    if progress:
        progress(rec_parse)

    # Convert to legacy workflow state
    from ega_schemas.audit import AuditCreateRequest as LegacyReq
    leg_req = LegacyReq(
        content=raw_content,
        project_id=state.project_id,
        page_type=state.request.page_type if state.request else None,
        central_entity=state.central_entity or None,
    )
    wf_state = create_initial_state(leg_req, state.run_id)
    wf_state.parsed_doc = state.document

    # Forward imported context/skill pack payloads (FR-16). The API merges them
    # into the run state; without this the scoring gate never sees brand rules
    # and always reports NOT_CONFIGURED even when a brand pack is loaded.
    if state.brand_rules or state.banned_terms or state.canonical_facts:
        wf_state.context_packs = [
            *list(wf_state.context_packs or []),
            {
                "brand_rules": list(state.brand_rules),
                "banned_terms": list(state.banned_terms),
                "canonical_facts": list(state.canonical_facts),
                "approved_claims": list(state.approved_claims),
                "internal_link_targets": list(state.internal_link_targets),
                "topical_map_rows": list(state.topical_map_rows),
            },
        ]

    # 2. Classifier
    t0 = time.monotonic()
    if progress:
        progress(StageRecord(node="classify", label="Page Classification", status=StageStatus.RUNNING))
    up = run_intake_classifier(wf_state)
    wf_state.page_type = up.get("page_type", wf_state.page_type)
    wf_state.central_entity = up.get("central_entity", wf_state.central_entity)
    state.page_type = wf_state.page_type
    state.central_entity = wf_state.central_entity
    c_duration = int((time.monotonic() - t0) * 1000)
    rec_class = StageRecord(node="classify", label="Page Classification", status=StageStatus.SUCCEEDED, duration_ms=c_duration)
    state.stages.append(rec_class)
    if progress:
        progress(rec_class)

    # 3. Fanout
    t0 = time.monotonic()
    if progress:
        progress(StageRecord(node="fanout", label="Query Fan-Out Simulator", status=StageStatus.RUNNING))
    up_fo = run_fanout_agent(wf_state)
    wf_state.fanout_queries = up_fo.get("fanout_queries", [])
    state.fanout = wf_state.fanout_queries
    fo_duration = int((time.monotonic() - t0) * 1000)
    rec_fo = StageRecord(node="fanout", label="Query Fan-Out Simulator", status=StageStatus.SUCCEEDED, duration_ms=fo_duration)
    state.stages.append(rec_fo)
    if progress:
        progress(rec_fo)

    # 4. Entities & EAV
    t0 = time.monotonic()
    if progress:
        progress(StageRecord(node="entities", label="Entity & EAV Extraction", status=StageStatus.RUNNING))
    up_ent = run_entity_eav_agent(wf_state)
    wf_state.entities = up_ent.get("entities", [])
    wf_state.eav_rows = up_ent.get("eav_rows", [])
    state.entities = wf_state.entities
    state.eav_rows = wf_state.eav_rows
    ent_duration = int((time.monotonic() - t0) * 1000)
    rec_ent = StageRecord(node="entities", label="Entity & EAV Extraction", status=StageStatus.SUCCEEDED, duration_ms=ent_duration)
    state.stages.append(rec_ent)
    if progress:
        progress(rec_ent)

    # 5. Triples
    t0 = time.monotonic()
    if progress:
        progress(StageRecord(node="triples", label="Knowledge Triples Analysis", status=StageStatus.RUNNING))
    from auditor.agents.triples_agent import run_triples_agent
    up_tr = run_triples_agent(wf_state)
    wf_state.triples = up_tr.get("triples", [])
    state.triples = wf_state.triples
    tr_duration = int((time.monotonic() - t0) * 1000)
    rec_tr = StageRecord(node="triples", label="Knowledge Triples Analysis", status=StageStatus.SUCCEEDED, duration_ms=tr_duration)
    state.stages.append(rec_tr)
    if progress:
        progress(rec_tr)

    # 6. Claims & Verification
    t0 = time.monotonic()
    if progress:
        progress(StageRecord(node="claims", label="Evidence & Claim Ledger", status=StageStatus.RUNNING))
    up_cl = run_claims_agent(wf_state)
    wf_state.claims = up_cl.get("claims", [])
    state.claims = wf_state.claims
    cl_duration = int((time.monotonic() - t0) * 1000)
    rec_cl = StageRecord(node="claims", label="Evidence & Claim Ledger", status=StageStatus.SUCCEEDED, duration_ms=cl_duration)
    state.stages.append(rec_cl)
    if progress:
        progress(rec_cl)

    # 7. Coverage
    up_cov = run_coverage_agent(wf_state)
    wf_state.coverage_rows = up_cov.get("coverage_rows", [])
    state.coverage_rows = list(wf_state.coverage_rows)

    # 8. Editorial & Passage analysis
    up_ed = run_editorial_agent(wf_state)
    wf_state.passage_findings = up_ed.get("passage_findings", [])
    state.passage_findings = list(wf_state.passage_findings)

    # 9. Scoring Engine
    t0 = time.monotonic()
    if progress:
        progress(StageRecord(node="scoring", label="Deterministic Rubric Scoring", status=StageStatus.RUNNING))
    scorecard = ScoringEngine.evaluate(
        entities=wf_state.entities,
        eav_rows=wf_state.eav_rows,
        triples=wf_state.triples,
        fanout_queries=wf_state.fanout_queries,
        coverage_rows=wf_state.coverage_rows,
        claims=wf_state.claims,
        parsed_doc=wf_state.parsed_doc,
        page_type=wf_state.page_type,
        context_packs=wf_state.context_packs,
    )
    swot_data = ScoringEngine.generate_swot(scorecard)
    state.scorecard = scorecard
    state.gate_status = scorecard.gate.status
    state.gate_issues = [GateIssue(message=m) for m in scorecard.gate.critical_issues]
    state.noncritical_gate_issues = [GateIssue(message=m, severity="medium") for m in scorecard.gate.noncritical_issues]
    state.swot = Swot(
        strengths=swot_data.strengths,
        weaknesses=swot_data.weaknesses,
        opportunities=swot_data.opportunities,
        threats=swot_data.threats,
    )
    sc_duration = int((time.monotonic() - t0) * 1000)
    rec_sc = StageRecord(node="scoring", label="Deterministic Rubric Scoring", status=StageStatus.SUCCEEDED, duration_ms=sc_duration)
    state.stages.append(rec_sc)
    if progress:
        progress(rec_sc)

    # 10. Handoff & Prioritization
    t0 = time.monotonic()
    if progress:
        progress(StageRecord(node="handoff", label="Writer Handoff & Prioritization", status=StageStatus.RUNNING))
    wf_state.swot = swot_data
    wf_state.component_scores = scorecard.scores
    wf_state.gate_result = scorecard.gate
    wf_state.composite_avr = (
        scorecard.composite.value if getattr(scorecard, "composite", None) else None
    )
    up_ho = run_handoff_agent(wf_state)
    recs = up_ho.get("recommendations", [])
    state.recommendations = [Recommendation.model_validate(r.model_dump()) for r in recs]
    state.findings = list(recs)
    state.measurement_plan = [dict(m) for m in (up_ho.get("measurement_plan") or [])]
    # The critic node reviews the agent-facing state, so mirror our results back.
    wf_state.recommendations = list(recs)
    wf_state.measurement_plan = list(state.measurement_plan)
    ho_duration = int((time.monotonic() - t0) * 1000)
    rec_ho = StageRecord(node="handoff", label="Writer Handoff & Prioritization", status=StageStatus.SUCCEEDED, duration_ms=ho_duration)
    state.stages.append(rec_ho)
    if progress:
        progress(rec_ho)

    # 11. Critic / QA validation — bounded to at most 2 loops (PRD §8.2 / §8.3).
    for attempt in (1, 2):
        t0 = time.monotonic()
        if progress:
            progress(StageRecord(node="critic", label="Critic / QA Validation", status=StageStatus.RUNNING))
        try:
            up_cr = run_critic_agent(wf_state)
        except Exception as exc:  # provider unavailable → record the skip, never crash
            state.critic_loops = attempt
            state.skip_stage("critic", f"Critic validation skipped: {type(exc).__name__}: {exc}")
            rec_cr = StageRecord(
                node="critic",
                label="Critic / QA Validation",
                status=StageStatus.SKIPPED,
                duration_ms=int((time.monotonic() - t0) * 1000),
                detail=str(exc),
            )
            state.stages.append(rec_cr)
            if progress:
                progress(rec_cr)
            break

        wf_state.critic_loops = int(up_cr.get("critic_loops", attempt))
        wf_state.critic_approved = bool(up_cr.get("critic_approved", False))
        wf_state.critic_notes = list(up_cr.get("critic_notes", wf_state.critic_notes))
        state.critic_loops = wf_state.critic_loops
        state.critic_notes = list(wf_state.critic_notes)
        approved = wf_state.critic_approved

        rec_cr = StageRecord(
            node="critic",
            label="Critic / QA Validation",
            status=StageStatus.SUCCEEDED,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail="approved" if approved else "repair requested",
        )
        state.stages.append(rec_cr)
        if progress:
            progress(rec_cr)

        if approved or attempt >= 2:
            break

        # Bounded repair cycle: handoff re-prioritises, critic re-reviews.
        up_rep = run_handoff_agent(wf_state)
        rep_recs = up_rep.get("recommendations", [])
        state.recommendations = [Recommendation.model_validate(r.model_dump()) for r in rep_recs]
        state.findings = list(rep_recs)
        state.measurement_plan = [dict(m) for m in (up_rep.get("measurement_plan") or [])]
        wf_state.recommendations = list(rep_recs)
        wf_state.measurement_plan = list(state.measurement_plan)
        state.stages.append(
            StageRecord(
                node="handoff_repair",
                label="Repair Cycle (Handoff)",
                status=StageStatus.SUCCEEDED,
                duration_ms=0,
                detail=f"critic loop {attempt}",
            )
        )

    return state
