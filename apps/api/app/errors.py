"""HTTP error model: stable machine-readable codes + human messages + trace id."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("ega.api.errors")


class ApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, *, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "trace_id": getattr(request.state, "trace_id", None),
                "details": exc.details or None,
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals (or secrets) to the client, but log with trace_id.
        tid = getattr(request.state, "trace_id", None)
        logger.exception("Unhandled server exception (trace_id=%s): %s", tid, exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Check server logs with the trace id.",
                "trace_id": tid,
                "details": None,
            },
        )

