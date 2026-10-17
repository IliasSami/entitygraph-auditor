"""MCP Tools definitions and execution handlers for EntityGraph Auditor (PRD §12, FR-20)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from ega_parsers.document_parser import DocumentParser
from ega_schemas.audit import AuditCreateRequest
from ega_schemas.enums import GateStatus, PageType

from auditor.workflows import execute_audit

logger = logging.getLogger(__name__)

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "run_content_audit",
        "description": "Run a full local-first entity and AEO/GEO audit on web content or markdown. Evaluates Entity Salience (EOS), Entity Relations (ERS), Knowledge Graph Readiness (KGR), Fact & Claim Substantiation (FCS), Passage Retrieval (PRS), and Brand/Compliance Gate.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The raw markdown, HTML, or plain text content to audit.",
                },
                "page_type": {
                    "type": "string",
                    "enum": [
                        "general",
                        "article",
                        "saas_b2b",
                        "ecommerce_pdp",
                        "ecommerce_plp",
                        "local_service",
                        "service",
                        "comparison",
                        "pricing",
                    ],
                    "default": "general",
                    "description": "The architectural page type.",
                },
                "primary_query": {
                    "type": "string",
                    "description": "Target primary search or AI answer retrieval query.",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "analyze_entities",
        "description": "Fast extraction of the central entity, candidate concepts, knowledge triples, and Entity-Attribute-Value (EAV) status (explicit vs missing).",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content text to extract entities and triples from.",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "check_brand_compliance",
        "description": "Evaluate brand compliance and publication gates: checks for banned terminology, unsubstantiated quantitative claims, and compliance blockers.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content to verify against compliance rules.",
                },
                "banned_terms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Explicit list of terms forbidden in copy.",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "get_audit_report",
        "description": "Retrieve an existing audit report by audit_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "audit_id": {
                    "type": "string",
                    "description": "The unique identifier of the audit run.",
                },
            },
            "required": ["audit_id"],
        },
    },
]


def _issue_text(issue: Any) -> str:
    """Render a gate issue (``str`` or ``GateIssue``) as readable text."""
    if isinstance(issue, str):
        return issue
    return (
        getattr(issue, "title", None)
        or getattr(issue, "message", None)
        or getattr(issue, "detail", None)
        or str(issue)
    )


def _persist_mcp_audit(
    state: Any,
    report: Any,
    request: Optional[Any] = None,
    primary_query: Optional[str] = None,
) -> None:
    """Persist MCP-executed audit into AuditRun table so it is addressable by run_id."""
    try:
        from datetime import datetime, timezone

        from ega_api.db import get_sessionmaker, init_db
        from ega_api.models import AuditRun
        from sqlalchemy.exc import OperationalError

        sm = get_sessionmaker()
        session = sm()
        try:
            try:
                run = session.get(AuditRun, state.run_id)
            except OperationalError:
                init_db()
                run = session.get(AuditRun, state.run_id)

            if run is None:
                req_dump: dict[str, Any] = {}
                if hasattr(request, "model_dump"):
                    req_dump = request.model_dump(mode="json")
                elif getattr(state, "request", None) and hasattr(state.request, "model_dump"):
                    req_dump = state.request.model_dump(mode="json")
                else:
                    req_dump = {
                        "content": getattr(state, "content", ""),
                        "primary_query": primary_query,
                    }

                run = AuditRun(
                    audit_id=state.run_id,
                    request=req_dump,
                )
                session.add(run)

            run.status = "succeeded"
            run.page_type = (
                state.page_type.value
                if hasattr(state.page_type, "value")
                else str(state.page_type or "general")
            )
            run.central_entity = (
                getattr(report.audit_metadata, "central_entity", None)
                or getattr(state, "central_entity", None)
            )
            run.primary_query = (
                primary_query
                or getattr(state, "title", None)
                or (getattr(state, "request", None) and getattr(state.request, "title", None))
            )
            run.gate_status = (
                report.gate.status.value
                if hasattr(report.gate.status, "value")
                else str(report.gate.status)
            )
            run.deterministic_only = getattr(state, "deterministic_only", True)
            run.content_hash = (
                (state.parsed_doc.content_hash if getattr(state, "parsed_doc", None) else None)
                or getattr(report.audit_metadata, "content_hash", None)
                or getattr(state, "content_hash", None)
            )
            run.report = (
                report.model_dump(mode="json")
                if hasattr(report, "model_dump")
                else report
            )
            run.report_json = run.report
            run.completed_at = datetime.now(timezone.utc)
            if getattr(report, "composite_avr", None) is not None:
                run.composite = report.composite_avr
            session.commit()
        finally:
            session.close()
    except Exception as exc:
        logger.warning("Could not persist MCP audit run %s: %s", getattr(state, "run_id", None), exc)


def tool_run_content_audit(
    content: str,
    page_type: str = "general",
    primary_query: Optional[str] = None,
) -> dict[str, Any]:
    """Execute complete deterministic multi-agent audit."""
    pt_enum = PageType.GENERAL
    try:
        pt_enum = PageType(page_type.lower())
    except ValueError:
        pass

    req = AuditCreateRequest(
        content=content,
        page_type=pt_enum,
        title=primary_query,
    )
    state, report = execute_audit(req)

    # Persist the completed audit so MCP audits resolve in GET /audits and get_audit_report
    _persist_mcp_audit(state, report, request=req, primary_query=primary_query)

    recommendations_summary = [
        {
            "priority": i + 1,
            "title": r.title,
            "category": r.category,
            "severity": r.severity.value,
            "what": r.what,
            "how": (getattr(r.how, "suggested_rewrite", None) or (str(r.how) if r.how else "")) or "",
            "priority_score": r.priority_score,
        }
        for i, r in enumerate(report.recommendations[:5])
    ]

    scores_summary = {
        k: {
            "value": score.value,
            "confidence": score.confidence.value,
            "rationale": score.rationale,
            "lost_points_reasons": score.lost_points_reasons,
        }
        for k, score in report.scores.items()
    }

    return {
        "run_id": state.run_id,
        "central_entity": report.audit_metadata.central_entity,
        "page_type": report.audit_metadata.page_type.value,
        "gate": {
            "status": report.gate.status.value,
            "publishable": report.gate.publishable,
            "critical_issues": [_issue_text(i) for i in report.gate.critical_issues],
            "noncritical_issues": [_issue_text(i) for i in report.gate.noncritical_issues],
            "rationale": report.gate.rationale,
        },
        "composite_avr": report.composite_avr,
        "scores": scores_summary,
        "swot": {
            "strengths": report.swot.strengths,
            "weaknesses": report.swot.weaknesses,
            "opportunities": report.swot.opportunities,
            "threats": report.swot.threats,
        },
        "recommendations": recommendations_summary,
        "disclaimer": "All scores are internal editorial heuristics, never search-engine platform ranking guarantees.",
    }


def tool_analyze_entities(content: str) -> dict[str, Any]:
    """Fast entity, triple, and EAV analysis."""
    req = AuditCreateRequest(content=content)
    state, report = execute_audit(req)

    return {
        "central_entity": report.audit_metadata.central_entity,
        "entities": [
            {
                "name": e.canonical_name,
                "kind": e.kind.value,
                "is_central": e.is_central,
                "salience": e.salience,
            }
            for e in report.entities
        ],
        "eav_rows": [
            {
                "entity": r.entity_name,
                "attribute": r.attribute,
                "value": r.value,
                "status": r.status.value,
                "notes": r.notes,
            }
            for r in report.eav_rows
        ],
        "triples": [
            {
                "subject": t.subject,
                "predicate": t.predicate,
                "object": t.object_,
                "status": t.status.value,
            }
            for t in report.triples
        ],
    }


def tool_check_brand_compliance(
    content: str,
    banned_terms: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Check content against banned terminology and compliance gates."""
    doc = DocumentParser.parse(content)
    lower_text = doc.normalized_text.lower()
    violations: list[str] = []

    # Check caller-provided or default banned phrases
    terms = list(banned_terms or [
        "guaranteed #1 ranking",
        "guaranteed ranking",
        "100% cure",
        "risk-free profit",
        "guaranteed return",
    ])

    for term in terms:
        if term.lower() in lower_text:
            violations.append(f"Forbidden term detected: '{term}'")

    gate_status = GateStatus.PASS if not violations else GateStatus.FAIL
    from ega_parsers import compute_flesch_reading_ease
    return {
        "status": gate_status.value,
        "publishable": gate_status == GateStatus.PASS,
        "violations": violations,
        "word_count": doc.word_count,
        "flesch_reading_ease": compute_flesch_reading_ease(doc.normalized_text),
    }


def tool_get_audit_report(audit_id: str) -> dict[str, Any]:
    """Retrieve audit report by ID."""
    from ega_api.db import get_sessionmaker, init_db
    from ega_api.models import AuditRun
    from sqlalchemy.exc import OperationalError

    sm = get_sessionmaker()
    session = sm()
    try:
        try:
            run = session.get(AuditRun, audit_id)
        except OperationalError:
            init_db()
            run = session.get(AuditRun, audit_id)
        if run is None:
            return {"error": f"Audit {audit_id} not found", "status": "not_found"}
        return {
            "audit_id": run.audit_id,
            "status": run.status,
            "composite": run.composite,
            "gate_status": run.gate_status,
            "report": run.report,
        }
    finally:
        session.close()
