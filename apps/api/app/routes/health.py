"""Health and readiness endpoints."""

from __future__ import annotations

from ega_api.config import Settings, get_settings
from ega_api.db import get_db
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(tags=["system"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "version": settings.version, "app": settings.app_name}


@router.get("/readiness")
@router.get("/health/ready")
def readiness(
    session: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict:
    checks: dict[str, dict] = {}

    try:
        session.execute(text("SELECT 1"))
        checks["database"] = {"ok": True, "detail": settings.database_url.split("://")[0]}
    except Exception as exc:  # pragma: no cover
        checks["database"] = {"ok": False, "detail": str(exc)[:200]}

    try:
        from ega_parsers import parse_content  # noqa: F401,PLC0415

        checks["parser"] = {"ok": True, "detail": "deterministic parser available"}
    except Exception as exc:  # pragma: no cover
        checks["parser"] = {"ok": False, "detail": f"parser unavailable: {exc}"[:200]}

    provider_ok = not settings.deterministic_only and settings.default_provider != "null"
    checks["model_provider"] = {
        "ok": True,
        "detail": (
            f"configured default provider: {settings.default_provider}"
            if provider_ok
            else "deterministic-only mode (no model provider configured) — semantic stages will be skipped"
        ),
    }
    checks["encryption_key"] = {
        "ok": bool(settings.app_encryption_key),
        "detail": (
            "APP_ENCRYPTION_KEY set"
            if settings.app_encryption_key
            else "APP_ENCRYPTION_KEY not set — provider secret storage disabled"
        ),
    }
    overall = "ok" if all(c["ok"] for c in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}


@router.post("/system/maintenance/purge-test-data")
def purge_test_data(
    session: Session = Depends(get_db),
) -> dict:
    """Purge smoke/test/sample garbage projects and vacuum database storage."""
    from ega_api.models import AuditLog, AuditRun, ContentVersion, Project

    projects = session.query(Project).all()
    deleted_count = 0
    test_prefixes = ("smoke-", "test-", "demo-", "fixture-", "sample-", "tmp-")
    test_markers = ("eval suite", "clouddb auditing", "pack gate http", "test", "northwind")

    for p in projects:
        name_lower = (p.name or "").lower()
        id_lower = (p.project_id or "").lower()
        if (
            any(name_lower.startswith(pref) or id_lower.startswith(pref) for pref in test_prefixes)
            or any(m in name_lower for m in test_markers)
        ):
            session.query(AuditRun).filter(AuditRun.project_id == p.project_id).delete(synchronize_session=False)
            session.query(ContentVersion).filter(ContentVersion.project_id == p.project_id).delete(synchronize_session=False)
            session.delete(p)
            deleted_count += 1

    session.add(AuditLog(action="system.maintenance.purge", target="projects", detail={"deleted_count": deleted_count}))
    session.commit()

    # If all projects were purged, create one clean default project
    remaining = session.query(Project).count()
    if remaining == 0:
        default_proj = Project(
            project_id="prod-workspace-1",
            name="Primary Workspace",
            brand="Acme",
            base_url="https://example.com",
            central_entity="Acme",
            context_pack_ids=["acme_brand_pack"],
            model_profile="deterministic_baseline",
            languages=["en"],
            archived=False,
        )
        session.add(default_proj)
        session.commit()

    try:
        session.execute(text("VACUUM"))
    except Exception:
        pass

    return {
        "ok": True,
        "deleted_count": deleted_count,
        "message": f"Purged {deleted_count} test workspace(s) and vacuumed database.",
    }
