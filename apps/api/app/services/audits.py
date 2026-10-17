"""Audit job orchestration: create → run workflow → persist report.

Long jobs return an audit_id immediately (API principle §11); execution happens
in an asyncio task in the same process (single-process default deployment —
see DECISIONS.md; a Redis/ARQ worker can replace `start_audit_job` later).

The workflow itself is injected/loaded lazily so the API is testable while the
graph is under construction and so tests can substitute a stub runner.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from ega_api.config import get_settings
from ega_api.models import AuditRun, CacheEntry, ContentVersion, ContextPack, ContextPackVersion
from ega_schemas.report import AuditReport
from ega_schemas.run import AuditCreateRequest, AuditRunState, StageRecord
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger("ega.audits")

ProgressCallback = Callable[[StageRecord], None]
WorkflowRunner = Callable[[AuditRunState, ProgressCallback | None], Awaitable[AuditRunState]]


# ------------------------------------------------------------ event bus ---


class EventBus:
    """In-process pub/sub for SSE progress. Replayable per audit."""

    def __init__(self) -> None:
        self._history: dict[str, list[dict]] = defaultdict(list)
        self._subs: dict[str, list[asyncio.Queue[dict]]] = defaultdict(list)
        self._max_history = 500

    def publish(self, audit_id: str, event: dict) -> None:
        hist = self._history[audit_id]
        hist.append(event)
        if len(hist) > self._max_history:
            del hist[: len(hist) - self._max_history]
        for q in list(self._subs.get(audit_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # pragma: no cover - defensive
                pass

    def history(self, audit_id: str) -> list[dict]:
        return list(self._history.get(audit_id, []))

    def subscribe(self, audit_id: str) -> asyncio.Queue[dict]:
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=self._max_history)
        self._subs[audit_id].append(q)
        return q

    def unsubscribe(self, audit_id: str, q: asyncio.Queue[dict]) -> None:
        try:
            self._subs[audit_id].remove(q)
        except (KeyError, ValueError):  # pragma: no cover
            pass

    def clear(self) -> None:
        self._history.clear()
        self._subs.clear()


bus = EventBus()


# ------------------------------------------------------------- helpers ---


def compute_cache_key(
    *,
    content_hash: str,
    page_type: str,
    pack_versions: dict[str, str],
    provider: str | None,
    model: str | None,
    prompt_versions: dict[str, str],
    node: str,
) -> str:
    raw = "|".join(
        [
            content_hash,
            page_type,
            ";".join(f"{k}={v}" for k, v in sorted(pack_versions.items())),
            f"{provider or '-'}",
            f"{model or '-'}",
            ";".join(f"{k}={v}" for k, v in sorted(prompt_versions.items())),
            node,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached(session: Session, project_id: str, key: str) -> dict | None:
    row = (
        session.query(CacheEntry)
        .filter(CacheEntry.project_id == project_id, CacheEntry.cache_key == key)
        .one_or_none()
    )
    if row is None:
        return None
    row.hits += 1
    session.commit()
    return dict(row.payload)


def put_cached(session: Session, project_id: str, key: str, node: str, payload: dict) -> None:
    existing = (
        session.query(CacheEntry)
        .filter(CacheEntry.project_id == project_id, CacheEntry.cache_key == key)
        .one_or_none()
    )
    if existing:
        existing.payload = payload
    else:
        session.add(
            CacheEntry(project_id=project_id, cache_key=key, node=node, payload=payload)
        )
    session.commit()


def load_pack_payloads(session: Session, pack_ids: list[str]) -> tuple[dict[str, str], list[dict]]:
    """Latest version payload per requested pack → (versions map, merged payloads)."""
    versions: dict[str, str] = {}
    payloads: list[dict] = []
    for pid in pack_ids:
        pack = session.get(ContextPack, pid)
        if pack is not None:
            versions[pack.name] = pack.version_hash or pack.version
            latest = (
                session.query(ContextPackVersion)
                .filter(ContextPackVersion.pack_id == pid)
                .order_by(ContextPackVersion.id.desc())
                .first()
            )
            if latest is not None:
                payloads.append(dict(latest.payload))
        else:
            from auditor.context_packs import get_builtin_pack  # noqa: PLC0415

            builtin = get_builtin_pack(pid)
            if builtin is not None:
                versions[builtin.get("name", pid)] = builtin.get("version", "1.0.0")
                payloads.append(builtin)
    return versions, payloads


# ----------------------------------------------------------- create/run ---


def create_audit(session: Session, request: AuditCreateRequest) -> AuditRun:
    content_version_id = request.content_version_id
    if not content_version_id and request.content_text:
        raise ValueError("content_text requires content import first (use /content/import)")
    run = AuditRun(
        project_id=request.project_id,
        content_version_id=content_version_id,
        status="queued",
        request=request.model_dump(mode="json"),
        page_type=request.page_type.value if request.page_type else None,
        primary_query=request.primary_query,
        depth=request.depth.value,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


async def default_workflow_runner(
    state: AuditRunState, progress: ProgressCallback | None
) -> AuditRunState:
    """Lazy import keeps API import cheap and allows test substitution."""
    from auditor.workflows.entry import run_audit  # noqa: PLC0415

    return await run_audit(state, progress=progress)


def build_initial_state(
    session: Session, run: AuditRunState
) -> AuditRunState:  # pragma: no cover - exercised via workflow tests
    return run


async def execute_audit(
    audit_id: str,
    session_factory: sessionmaker,
    runner: WorkflowRunner | None = None,
) -> None:
    """Background job body: load run → build state → run graph → persist."""
    settings = get_settings()
    runner = runner or default_workflow_runner
    started = time.monotonic()
    bus.publish(audit_id, {"type": "status", "status": "running", "at": _iso()})

    session: Session = session_factory()
    try:
        run = session.get(AuditRun, audit_id)
        if run is None:
            logger.error("audit %s not found", audit_id)
            return
        run.status = "running"
        session.commit()

        request = AuditCreateRequest.model_validate(run.request)
        cv = session.get(ContentVersion, run.content_version_id) if run.content_version_id else None
        if cv is None:
            run.status = "failed"
            run.error = {"code": "CONTENT_MISSING", "message": "Content version not found"}
            session.commit()
            bus.publish(audit_id, {"type": "status", "status": "failed", "at": _iso()})
            return

        pack_versions, payloads = load_pack_payloads(session, request.context_pack_ids or [])

        from ega_schemas.content import ContentSourceMeta  # noqa: PLC0415

        state = AuditRunState(
            run_id=audit_id,
            project_id=run.project_id or "",
            request=request,
            content_version_id=cv.content_version_id,
            content_hash=cv.content_hash,
            source_meta=ContentSourceMeta(
                kind="upload",
                original_format=cv.original_format,
                parser="stored",
            ),
            context_pack_ids=list(request.context_pack_ids or []),
            context_pack_versions=pack_versions,
            deterministic_only=settings.deterministic_only or settings.default_provider == "null",
            depth=request.depth,
            created_at=_iso(),
        )
        # stored ParsedDocument snapshot (parsed at import time)
        if cv.document:
            from ega_schemas.content import ParsedDocument  # noqa: PLC0415

            try:
                state.document = ParsedDocument.model_validate(cv.document)
            except Exception as exc:  # corrupted snapshot → workflow will re-parse
                state.warnings.append(f"Stored parse snapshot invalid; re-parsing ({exc})")

        for p in payloads:
            _merge_pack_payload(state, p)

        def progress(record: StageRecord) -> None:
            bus.publish(
                audit_id,
                {
                    "type": "stage",
                    "node": record.node,
                    "label": record.label,
                    "status": record.status.value,
                    "origin": record.origin.value,
                    "detail": record.detail,
                    "duration_ms": record.duration_ms,
                    "retries": record.retries,
                    "cached": record.cached,
                    "at": _iso(),
                },
            )
            # persist stage snapshot for reconnecting clients
            s = session_factory()
            try:
                r = s.get(AuditRun, audit_id)
                if r is not None:
                    existing = {st.get("node"): st for st in (r.stages or [])}
                    existing[record.node] = record.model_dump(mode="json")
                    r.stages = list(existing.values())
                    s.commit()
            finally:
                s.close()

        state = await runner(state, progress)
        _persist(session, run, state, started)
        bus.publish(
            audit_id,
            {"type": "status", "status": run.status, "at": _iso(), "gate": run.gate_status},
        )
    except asyncio.CancelledError:
        _mark_failed(session_factory, audit_id, "CANCELLED", "Audit run was cancelled")
        raise
    except Exception as exc:  # never lose a run silently
        logger.exception("audit %s failed", audit_id)
        msg = str(exc)[:500]
        _mark_failed(session_factory, audit_id, "AUDIT_FAILED", msg)
    finally:
        session.close()


def _merge_pack_payload(state: AuditRunState, payload: dict) -> None:
    state.brand_rules.extend(payload.get("brand_rules") or [])
    state.canonical_facts.extend(payload.get("canonical_facts") or [])
    state.banned_terms.extend(payload.get("banned_terms") or [])
    state.approved_claims.extend(payload.get("approved_claims") or [])
    state.internal_link_targets.extend(payload.get("internal_link_targets") or [])
    state.topical_map_rows.extend(payload.get("topical_map_rows") or [])


def _persist(session: Session, run: AuditRun, state: AuditRunState, started: float) -> None:

    report = build_report(state)
    run.stages = [st.model_dump(mode="json") for st in state.stages]
    run.report = report.model_dump(mode="json")
    run.report_json = run.report
    run.page_type = state.page_type.value
    run.language = state.language
    run.central_entity = state.central_entity
    run.primary_query = state.request.primary_query
    run.gate_status = state.gate_status.value
    run.content_hash = state.content_hash
    run.deterministic_only = state.deterministic_only
    run.provider_model = (
        f"{state.model_provider}/{state.model_id}" if state.model_id else state.model_provider
    )
    run.context_pack_versions = state.context_pack_versions
    if state.scorecard:
        comp_val = getattr(getattr(state.scorecard, "composite", None), "value", None)
        if comp_val is not None:
            run.composite = comp_val
        elif getattr(state.scorecard, "avr", None) is not None:
            run.composite = state.scorecard.avr
        run.score_profile = getattr(state.scorecard, "profile", None) or getattr(state.scorecard, "profile_name", "default")
        run.score_profile_version = getattr(state.scorecard, "profile_version", "1.0")

    run.status = "succeeded"
    run.completed_at = datetime.now(timezone.utc)
    run.duration_ms = int((time.monotonic() - started) * 1000)
    session.commit()


def build_report(state: AuditRunState) -> AuditReport:
    """Assemble the AuditReport contract from the finished run state (PRD §22)."""
    from ega_schemas.enums import GateStatus, IntentClass  # noqa: PLC0415
    from ega_schemas.report import (  # noqa: PLC0415
        AuditMetadata,
        AuditReport,
        GateResult,
        SourceCitation,
    )

    gate = GateResult(
        status=state.gate_status,
        critical_issues=state.gate_issues,
        noncritical_issues=state.noncritical_gate_issues,
        publishable=state.gate_status in (GateStatus.PASS, GateStatus.PASS_WITH_FIXES, GateStatus.NOT_CONFIGURED),
        rationale=_gate_rationale(state),
    )
    metadata = AuditMetadata(
        project_id=state.project_id,
        run_id=state.run_id,
        page_type=state.page_type,
        page_type_source=state.page_type_source,
        language=state.language,
        central_entity=state.central_entity,
        primary_intent=state.primary_intent or IntentClass.INFORMATIONAL,
        created_at=state.created_at or _iso(),
        completed_at=state.completed_at,
        content_hash=state.content_hash,
        score_profile_version=(
            state.scorecard.profile_version if state.scorecard else "1.0"
        ),
        provider_model=(
            f"{state.model_provider}/{state.model_id}" if state.model_id else (state.model_provider or "deterministic-baseline")
        ),
        context_pack_versions=[f"{k}:{v}" for k, v in state.context_pack_versions.items()],
        prompt_versions=state.prompt_versions,
        assumptions=state.assumptions,
        warnings=state.warnings,
        skipped_stages=state.skipped_stages,
        deterministic_only=state.deterministic_only,
        depth=state.depth.value,
    )
    from ega_schemas.report import Scorecard  # noqa: PLC0415

    return AuditReport(
        audit_metadata=metadata,
        gate=gate,
        scores=state.scorecard or Scorecard(),
        composite_avr=(
            state.scorecard.composite.value
            if state.scorecard is not None and state.scorecard.composite is not None
            else None
        ),
        entities=state.entities,
        entity_missing_groups=_missing_entity_groups(state),
        eav_rows=state.eav_rows,
        triples=state.triples,
        fanout=state.fanout,
        coverage_rows=state.coverage_rows,
        passage_findings=state.passage_findings,
        claims=state.claims,
        findings=state.findings,
        recommendations=state.recommendations,
        swot=state.swot,
        writer_handoff=state.writer_handoff,
        measurement_plan=state.measurement_plan,
        sources=[
            SourceCitation(
                source_id=s.source_id,
                url=s.url,
                title=s.title,
                access_date=s.access_date,
                verification_state=s.verification_state,
            )
            for s in state.evidence_sources
        ],
        evidence_sources=state.evidence_sources,
        technical_flags=state.technical_flags,
        limitations=state.limitations,
        not_assessed=state.skipped_stages,
        stage_records=[st.model_dump(mode="json") for st in state.stages],
    )


def _gate_rationale(state: AuditRunState) -> str:
    from ega_schemas.enums import GateStatus  # noqa: PLC0415

    if state.gate_status == GateStatus.FAIL:
        n = len(state.gate_issues)
        return f"Critical publication gate failure: {n} issue(s). Not publishable as-is."
    if state.gate_status == GateStatus.PASS_WITH_FIXES:
        return f"{len(state.noncritical_gate_issues)} non-critical issue(s) must be fixed."
    if state.gate_status == GateStatus.PASS:
        return "No brand/claim/compliance blockers detected."
    return "No brand pack configured — gate not evaluated (fabrication checks still apply)."


def _missing_entity_groups(state: AuditRunState) -> list[str]:
    groups: list[str] = []
    if not state.central_entity:
        groups.append("central entity could not be determined")
    if state.request.location_target and not any(
        e.kind.value == "location" for e in state.entities
    ):
        groups.append("target location entity not found in content")
    return groups


def _mark_failed(session_factory: sessionmaker, audit_id: str, code: str, message: str) -> None:
    session = session_factory()
    try:
        run = session.get(AuditRun, audit_id)
        if run is not None:
            run.status = "failed"
            run.error = {"code": code, "message": message}
            session.commit()
        bus.publish(audit_id, {"type": "status", "status": "failed", "at": _iso(), "error": code})
    finally:
        session.close()


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_audit_job(audit_id: str, runner: WorkflowRunner | None = None) -> Any:
    from ega_api.db import get_sessionmaker  # noqa: PLC0415

    try:
        loop = asyncio.get_running_loop()
        return loop.create_task(execute_audit(audit_id, get_sessionmaker(), runner))
    except RuntimeError:
        import threading
        t = threading.Thread(
            target=lambda: asyncio.run(execute_audit(audit_id, get_sessionmaker(), runner)),
            daemon=True,
        )
        t.start()
        return t



# ---------------------------------------------------- writer handoff (deterministic) ---


def _measurement_line(entry: Any) -> str:
    """Render one measurement-plan entry as markdown (PRD §18.16).

    Entries are structured (``{kpi, baseline, target, cadence, …}``) — never
    render a raw dict repr into a writer-facing brief.
    """
    if not isinstance(entry, dict):
        return f"- {entry}"
    kpi = entry.get("kpi") or entry.get("metric") or entry.get("name") or "measure"
    baseline = entry.get("baseline")
    target = entry.get("target")
    cadence = entry.get("cadence") or entry.get("frequency")
    line = f"- **{kpi}**"
    if baseline is not None and target is not None:
        line += f": {baseline} → {target}"
    elif target is not None:
        line += f": target {target}"
    elif baseline is not None:
        line += f": baseline {baseline}"
    if cadence:
        line += f" (check {cadence})"
    extra = entry.get("notes") or entry.get("note")
    if extra:
        line += f" — {extra}"
    return line


def build_writer_handoff(report: "AuditReport") -> dict:
    """PRD FR-18: writer-ready brief built from the stored report — no LLM needed.

    Every action keeps what/where/why/how/verification; the lexicon is derived
    from evidence-backed findings only (never invented terms).
    """
    gate_line = {
        "pass": "Publishable from a brand/compliance perspective (editorial fixes may remain).",
        "pass_with_fixes": "Publish only after the listed non-critical fixes are applied.",
        "fail": "NOT PUBLISHABLE AS-IS — resolve critical gate issues first.",
        "not_configured": "No brand pack configured — gate not evaluated.",
        "not_assessed": "Gate not assessed.",
    }.get(report.gate.status.value, report.gate.status.value)

    actions = [
        {
            "rank": i + 1,
            "finding_id": r.finding_id,
            "severity": r.severity.value,
            "what": r.what,
            "where": getattr(r.where, "excerpt", None) or (str(r.where) if r.where else ""),
            "why": getattr(r.why, "intent_or_query", None) or (str(r.why) if r.why else ""),
            "how": getattr(r.how, "suggested_rewrite", None) or (str(r.how) if r.how else ""),
            "verification_condition": getattr(r.how, "verification_condition", None) or getattr(r, "verification_condition", "") or "",
            "priority_score": r.priority_score,
        }
        for i, r in enumerate(report.recommendations)
    ]

    include: list[str] = []
    replace: list[str] = []
    avoid: list[str] = []
    for f in report.findings:
        suggestion = getattr(f.how, "suggested_rewrite", "") or (f.how if isinstance(f.how, str) else "")
        if f.category in ("term_suggestion", "lexicon_include") and suggestion:
            include.append(suggestion)
        elif f.category in ("term_replace", "lexicon_replace") and suggestion:
            replace.append(suggestion)
        if f.category in ("banned_term", "forbidden_claim"):
            avoid.append(f.title)

    lexicon = {"include": include, "replace": replace, "avoid": avoid}

    assumption_lines = [f"- {a}" for a in report.audit_metadata.assumptions] or [
        "- none recorded"
    ]
    measurement_lines = [_measurement_line(m) for m in report.measurement_plan] or [
        "- re-run this audit profile after edits and compare"
    ]
    sections = [
        "# Writer handoff",
        "",
        f"**Page:** {report.audit_metadata.central_entity or 'unset'} — "
        f"{report.audit_metadata.page_type.value} ({report.audit_metadata.language})",
        f"**Gate:** {report.gate.status.value} — {gate_line}",
        f"**Primary query/topic:** {report.audit_metadata.primary_query or 'not provided'}",
        "",
        "## Assumptions",
        *assumption_lines,
        "",
        "## Do first (highest priority)",
    ]
    for a in actions[:5]:
        sections += [
            "",
            f"### {a['rank']}. {a['what']}  [{a['severity']}, priority {a['priority_score']}]",
            f"- Where: {a['where']}",
            f"- Why: {a['why']}",
            f"- How: {a['how']}",
            f"- Verify: {a['verification_condition']}",
        ]
    if lexicon["include"] or lexicon["replace"] or lexicon["avoid"]:
        sections += ["", "## Lexicon"]
        if lexicon["include"]:
            sections.append("- Include (with context): " + "; ".join(lexicon["include"])[:800])
        if lexicon["replace"]:
            sections.append("- Replace: " + "; ".join(lexicon["replace"])[:800])
        if lexicon["avoid"]:
            sections.append("- Avoid: " + "; ".join(lexicon["avoid"])[:800])
    sections += [
        "",
        "## Validation plan",
        *measurement_lines,
        "",
        f"> {report.scores.disclaimer}",
    ]

    return {
        "brief_markdown": "\n".join(sections),
        "actions": actions,
        "lexicon": lexicon,
        "gate": report.gate.status.value,
        "note": (
            "Suggestions are examples for review — nothing is applied to your content automatically."
        ),
    }

