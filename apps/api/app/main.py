"""FastAPI application factory (PRD §11).

Single canonical app factory for both agents: import `create_app` (preferred,
used by tests) or the module-level `app` (used by uvicorn).

Router note (see AGENTS.md / ADR-006): exactly one router per domain is mounted —
`health`, `projects`, `content`, `packs`, `audits`, `models`, `mcp`. The duplicate
routers written by the parallel agent (`routes/system.py`,
`routes/context_packs.py`, `routes/models_api.py`) were removed in the
integration pass: they exposed the same PRD §11 endpoints as `health.py`,
`packs.py` and `models.py`.
"""

from __future__ import annotations

import logging
import time

from ega_api.config import get_settings
from ega_api.errors import register_error_handlers
from ega_api.routes import audits, content, health, mcp, models, packs, projects, workspace
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("ega.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

API_PREFIX = "/api/v1"


def create_app(*, init_database: bool = True) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=(
            "Local-first entity / AEO / GEO content auditor. All scores are internal "
            "editorial heuristics, not search-engine metrics."
        ),
        docs_url=f"{API_PREFIX}/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if settings.docs_enabled else None,
    )

    # Loopback-first CORS (local-first default). Wildcard + credentials is never used.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        from ega_api.deps import new_trace_id, trace_id_var  # noqa: PLC0415

        tid = request.headers.get("x-trace-id") or new_trace_id()
        request.state.trace_id = tid
        trace_id_var.set(tid)
        started = time.monotonic()
        response = await call_next(request)
        response.headers["X-Trace-Id"] = tid
        duration_ms = int((time.monotonic() - started) * 1000)
        # Never log raw content or secrets — only method/path/status/duration.
        logger.info(
            "%s %s -> %s (%dms) trace=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            tid,
        )
        return response

    register_error_handlers(app)

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(projects.router, prefix=API_PREFIX)
    app.include_router(content.router, prefix=API_PREFIX)
    app.include_router(packs.router, prefix=API_PREFIX)
    app.include_router(audits.router, prefix=API_PREFIX)
    app.include_router(models.router, prefix=API_PREFIX)
    app.include_router(mcp.router, prefix=API_PREFIX)
    app.include_router(workspace.router, prefix=API_PREFIX)

    # Optional static workspace (frontend build output dropped here by ops).
    from pathlib import Path  # noqa: PLC0415

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and (static_dir / "index.html").exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        @app.get("/app", include_in_schema=False)
        async def _serve_index() -> FileResponse:
            return FileResponse(static_dir / "index.html")

    if init_database:
        from ega_api.db import init_db  # noqa: PLC0415

        try:
            init_db()
        except Exception:  # pragma: no cover - surfaced via /readiness
            logger.exception("Database initialisation failed")

    return app


app = create_app()
