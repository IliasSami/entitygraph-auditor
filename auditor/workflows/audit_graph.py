"""LangGraph multi-agent audit workflow (PRD §8.3 / Milestone 1)."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ega_parsers.document_parser import DocumentParser
from ega_schemas.audit import AuditCreateRequest, AuditRunState
from ega_schemas.enums import PageType, StageStatus
from ega_schemas.report import AuditMetadata, AuditReport
from langgraph.graph import END, START, StateGraph

from auditor.agents.claims_agent import run_claims_agent
from auditor.agents.coverage_agent import run_coverage_agent
from auditor.agents.critic_agent import run_critic_agent
from auditor.agents.editorial_agent import run_editorial_agent
from auditor.agents.entity_eav_agent import run_entity_eav_agent
from auditor.agents.fanout_agent import run_fanout_agent
from auditor.agents.handoff_agent import run_handoff_agent
from auditor.agents.intake_classifier import run_intake_classifier
from auditor.agents.scoring_node import run_scoring_node
from auditor.agents.triples_agent import run_triples_agent


def parse_content_node(state: AuditRunState) -> dict[str, Any]:
    """Deterministic document ingestion and segmentation node."""
    start = time.time()
    doc = DocumentParser.parse(state.content, default_title=state.title)
    elapsed = int((time.time() - start) * 1000)

    timeline_entry = {
        "node": "parse_content",
        "duration_ms": elapsed,
        "word_count": doc.word_count,
        "passage_count": len(doc.passages),
        "heading_count": len(doc.headings),
    }

    current_timeline = list(state.timeline)
    current_timeline.append(timeline_entry)

    return {
        "parsed_doc": doc,
        "title": doc.title or state.title or "Untitled Document",
        "timeline": current_timeline,
    }


def should_critic_loop(state: AuditRunState) -> str:
    """Conditional edge: check if critic requests a repair loop (max 2)."""
    if not state.critic_approved and state.critic_loops < 2:
        return "handoff_agent"
    return END


def build_audit_graph() -> Any:
    """Construct and compile the constrained LangGraph state graph."""
    graph = StateGraph(AuditRunState)

    # Register nodes
    graph.add_node("parse_content", parse_content_node)
    graph.add_node("intake_classifier", run_intake_classifier)
    graph.add_node("fanout_agent", run_fanout_agent)
    graph.add_node("entity_eav_agent", run_entity_eav_agent)
    graph.add_node("triples_agent", run_triples_agent)
    graph.add_node("claims_agent", run_claims_agent)
    graph.add_node("coverage_agent", run_coverage_agent)
    graph.add_node("editorial_agent", run_editorial_agent)
    graph.add_node("scoring_node", run_scoring_node)
    graph.add_node("handoff_agent", run_handoff_agent)
    graph.add_node("critic_agent", run_critic_agent)

    # Wire edges
    graph.add_edge(START, "parse_content")
    graph.add_edge("parse_content", "intake_classifier")
    graph.add_edge("intake_classifier", "fanout_agent")
    graph.add_edge("fanout_agent", "entity_eav_agent")
    graph.add_edge("entity_eav_agent", "triples_agent")
    graph.add_edge("triples_agent", "claims_agent")
    graph.add_edge("claims_agent", "coverage_agent")
    graph.add_edge("coverage_agent", "editorial_agent")
    graph.add_edge("editorial_agent", "scoring_node")
    graph.add_edge("scoring_node", "handoff_agent")
    graph.add_edge("handoff_agent", "critic_agent")

    graph.add_conditional_edges(
        "critic_agent",
        should_critic_loop,
        {
            "handoff_agent": "handoff_agent",
            END: END,
        },
    )

    return graph.compile()


def create_initial_state(request: AuditCreateRequest, run_id: Optional[str] = None) -> AuditRunState:
    """Instantiate initial AuditRunState from incoming request."""
    r_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
    proj_id = request.project_id or "default"

    return AuditRunState(
        run_id=r_id,
        project_id=proj_id,
        content=request.content,
        url=request.url,
        title=request.title,
        page_type=request.page_type or PageType.GENERAL,
        central_entity=request.central_entity or "",
        primary_intent=request.primary_intent or getattr(request, "primary_intent", None) or "informational",
        target_audience=request.target_audience or "General Audience",
        target_action=request.target_action or "Evaluate / Learn",
        locale=request.locale,
        depth=request.depth,
        source_profile=request.source_profile,
        model_provider=request.model_provider or "dummy",
        model_name=request.model_name or "default",
        status=StageStatus.RUNNING,
    )


def assemble_audit_report(final_state: AuditRunState) -> AuditReport:
    """Transform finalized AuditRunState into a formal AuditReport (PRD §22)."""
    content_hash = final_state.parsed_doc.content_hash if final_state.parsed_doc else "unknown"
    created_at = datetime.now(timezone.utc).isoformat()

    metadata = AuditMetadata(
        project_id=final_state.project_id,
        run_id=final_state.run_id,
        page_type=final_state.page_type,
        language=final_state.locale,
        central_entity=final_state.central_entity or "Primary Subject",
        primary_intent=final_state.primary_intent,
        created_at=created_at,
        content_hash=content_hash,
        score_profile_version="1.0",
        provider_model=f"{final_state.model_provider}/{final_state.model_name}",
        context_pack_versions=[],
        assumptions=["Baseline heuristic audit; not an official search engine ranking metric."],
        warnings=final_state.critic_notes,
    )

    return AuditReport(
        audit_metadata=metadata,
        gate=final_state.gate_result,
        scores=final_state.component_scores,
        composite_avr=final_state.composite_avr,
        entities=final_state.entities,
        eav_rows=final_state.eav_rows,
        triples=final_state.triples,
        fanout=final_state.fanout_queries,
        coverage_rows=final_state.coverage_rows,
        passage_findings=final_state.passage_findings,
        claims=final_state.claims,
        recommendations=final_state.recommendations,
        swot=final_state.swot,
        measurement_plan=final_state.measurement_plan,
        sources=final_state.evidence_sources,
    )


def execute_audit(request: AuditCreateRequest, run_id: Optional[str] = None) -> tuple[AuditRunState, AuditReport]:
    """Execute complete end-to-end multi-agent audit."""
    compiled_app = build_audit_graph()
    initial_state = create_initial_state(request, run_id)
    
    result = compiled_app.invoke(initial_state)
    # Result is a dict or AuditRunState
    if isinstance(result, dict):
        final_state = AuditRunState.model_validate(result)
    else:
        final_state = result

    final_state.status = StageStatus.SUCCEEDED
    report = assemble_audit_report(final_state)
    return final_state, report
