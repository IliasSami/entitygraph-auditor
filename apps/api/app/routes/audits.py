"""Audit endpoints: create, list, status, SSE progress, report views, compare,
writer handoff, export (PRD §11, FR-17, FR-18)."""

from __future__ import annotations

import asyncio
import json

from ega_api.db import get_db
from ega_api.errors import ApiError
from ega_api.models import AuditLog, AuditRun, ReportExport
from ega_api.services.audits import bus, create_audit, start_audit_job
from ega_schemas.report import AuditReport
from ega_schemas.run import AuditCreateRequest
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

router = APIRouter(prefix="/audits", tags=["audits"])


# ------------------------------------------------------------- create ---


@router.post("", status_code=202)
def create_audit_run(payload: AuditCreateRequest, session: Session = Depends(get_db)) -> dict:
    from ega_api.models import Project  # noqa: PLC0415

    if payload.project_id and session.get(Project, payload.project_id) is None:
        raise ApiError("PROJECT_NOT_FOUND", f"Project {payload.project_id} not found", 404)
    if not payload.content_version_id and not payload.content_text:
        raise ApiError(
            "MISSING_CONTENT",
            "Provide content_version_id (from /content/import) or content_text",
            422,
        )
    if payload.content_text and not payload.content_version_id:
        raise ApiError(
            "MISSING_CONTENT",
            "Import content first via POST /content/import, then reference content_version_id",
            422,
        )
    try:
        run = create_audit(session, payload)
    except ValueError as exc:
        raise ApiError("INVALID_REQUEST", str(exc), 422) from exc

    session.add(AuditLog(action="audit.create", target=run.audit_id))
    session.commit()
    start_audit_job(run.audit_id)
    return {"audit_id": run.audit_id, "status": run.status, "trace_id": None}


# --------------------------------------------------------------- list ---


@router.get("")
def list_audits(
    project_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_db),
) -> list[dict]:
    q = session.query(AuditRun)
    if project_id:
        q = q.filter(AuditRun.project_id == project_id)
    if status:
        q = q.filter(AuditRun.status == status)
    rows = q.order_by(AuditRun.created_at.desc()).limit(limit).all()
    return [
        {
            "audit_id": r.audit_id,
            "project_id": r.project_id,
            "content_version_id": r.content_version_id,
            "created_at": r.created_at.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "page_type": r.page_type,
            "language": r.language,
            "central_entity": r.central_entity,
            "primary_query": r.primary_query,
            "status": r.status,
            "gate_status": r.gate_status,
            "composite": r.composite,
            "score_profile": r.score_profile,
            "provider_model": r.provider_model,
            "deterministic_only": r.deterministic_only,
            "depth": r.depth,
            "error": r.error,
        }
        for r in rows
    ]


def _get_run(session: Session, audit_id: str) -> AuditRun:
    run = session.get(AuditRun, audit_id)
    if run is None:
        raise ApiError("AUDIT_NOT_FOUND", f"Audit {audit_id} not found", 404)
    return run


@router.get("/{audit_id}")
def get_audit(audit_id: str, session: Session = Depends(get_db)) -> dict:
    run = _get_run(session, audit_id)
    stages = run.stages or []
    return {
        "audit_id": run.audit_id,
        "status": run.status,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_ms": run.duration_ms,
        "page_type": run.page_type,
        "gate_status": run.gate_status,
        "composite": run.composite,
        "provider_model": run.provider_model,
        "deterministic_only": run.deterministic_only,
        "error": run.error,
        "progress": {
            "stages": stages,
            "completed": sum(1 for s in stages if s.get("status") in ("succeeded", "skipped", "cached")),
            "total": len(stages),
        },
        "report": AuditReport.model_validate(run.report) if run.report else None,
    }


@router.get("/{audit_id}/events")
async def audit_events(audit_id: str, session: Session = Depends(get_db)) -> StreamingResponse:
    """SSE stream: replay history first, then live events until terminal status."""
    _get_run(session, audit_id)  # 404 early

    async def gen():
        seen: set[str] = set()
        for ev in bus.history(audit_id):
            seen.add(json.dumps(ev, sort_keys=True))
            yield _sse(ev)
        queue = bus.subscribe(audit_id)
        try:
            terminal = False
            while not terminal:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    # resync status from DB (handles restarts / external jobs)
                    s = session
                    run = s.get(AuditRun, audit_id)
                    if run is None:
                        break
                    if run.status in ("succeeded", "failed"):
                        yield _sse(
                            {"type": "status", "status": run.status, "gate": run.gate_status}
                        )
                        break
                    continue
                key = json.dumps(ev, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                yield _sse(ev)
                if ev.get("type") == "status" and ev.get("status") in (
                    "succeeded",
                    "failed",
                ):
                    terminal = True
        finally:
            bus.unsubscribe(audit_id, queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# --------------------------------------------------------- report views ---


def _report(session: Session, audit_id: str) -> AuditReport:
    run = _get_run(session, audit_id)
    if not run.report:
        raise ApiError(
            "REPORT_NOT_READY",
            f"Audit {audit_id} has no report yet (status: {run.status})",
            409,
        )
    return AuditReport.model_validate(run.report)


@router.get("/{audit_id}/entities")
def audit_entities(audit_id: str, session: Session = Depends(get_db)) -> list[dict]:
    return [e.model_dump(mode="json") for e in _report(session, audit_id).entities]


@router.get("/{audit_id}/triples")
def audit_triples(audit_id: str, session: Session = Depends(get_db)) -> list[dict]:
    return [t.model_dump(mode="json") for t in _report(session, audit_id).triples]


@router.get("/{audit_id}/fanout")
def audit_fanout(audit_id: str, session: Session = Depends(get_db)) -> list[dict]:
    return [q.model_dump(mode="json") for q in _report(session, audit_id).fanout]


@router.get("/{audit_id}/findings")
def audit_findings(audit_id: str, session: Session = Depends(get_db)) -> list[dict]:
    return [f.model_dump(mode="json") for f in _report(session, audit_id).findings]


@router.get("/{audit_id}/scores")
def audit_scores(audit_id: str, session: Session = Depends(get_db)) -> dict:
    scores = _report(session, audit_id).scores
    if hasattr(scores, "model_dump"):
        return scores.model_dump(mode="json")
    return {
        k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
        for k, v in scores.items()
    }


@router.get("/{audit_id}/report")
def audit_report(audit_id: str, session: Session = Depends(get_db)) -> dict:
    return _report(session, audit_id).model_dump(mode="json")


# ------------------------------------------------------------- compare ---


@router.post("/compare")
def compare_audits(payload: dict, session: Session = Depends(get_db)):
    base_id = payload.get("baseline_id") or payload.get("base_id")
    cand_id = payload.get("candidate_id")
    if not base_id or not cand_id:
        raise ApiError("MISSING_IDS", "Provide 'baseline_id' and 'candidate_id'", 422)
    base = _report(session, base_id)
    cand = _report(session, cand_id)
    from ega_api.services.compare import compare_reports  # noqa: PLC0415

    # FastAPI's jsonable_encoder serializes the dataclass (and nested pydantic models).
    return compare_reports(base, cand)


# -------------------------------------------------------- writer handoff ---


@router.post("/{audit_id}/writer-handoff")
def writer_handoff(audit_id: str, session: Session = Depends(get_db)) -> dict:
    report = _report(session, audit_id)
    if report.writer_handoff:
        return report.writer_handoff
    # Deterministic fallback built from findings (no LLM needed).
    from ega_api.services.audits import build_writer_handoff  # noqa: PLC0415

    handoff = build_writer_handoff(report)
    return handoff


# -------------------------------------------------------------- export ---


@router.post("/{audit_id}/export")
def export_report(audit_id: str, payload: dict | None = None, session: Session = Depends(get_db)) -> Response:
    fmt = (payload or {}).get("format", "markdown").lower()
    report = _report(session, audit_id)
    from ega_api.services.export import render  # noqa: PLC0415

    try:
        data, media_type, filename = render(report, fmt)
    except ValueError as exc:
        raise ApiError("UNSUPPORTED_FORMAT", str(exc), 422) from exc

    session.add(
        ReportExport(
            audit_id=audit_id, fmt=fmt, filename=filename, size_bytes=len(data)
        )
    )
    session.add(AuditLog(action="export", target=audit_id, detail={"format": fmt, "bytes": len(data)}))
    session.commit()
    safe_name = filename.replace('"', "")
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


# ------------------------------------------------------------ deletion ---


@router.delete("/{audit_id}", status_code=204)
def delete_audit(audit_id: str, session: Session = Depends(get_db)) -> None:
    run = _get_run(session, audit_id)
    session.delete(run)
    session.add(AuditLog(action="audit.delete", target=audit_id))
    session.commit()
