"""Shared FastAPI dependencies: DB session, settings, auth gate, trace IDs."""

from __future__ import annotations

import contextvars
import uuid

from ega_api.config import Settings, get_settings
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


def get_trace_id(request: Request) -> str:
    tid = getattr(request.state, "trace_id", "") or trace_id_var.get()
    return tid


def get_app_settings() -> Settings:
    return get_settings()


def require_auth(
    request: Request,
    settings: Settings = Depends(get_app_settings),
    authorization: str | None = Header(default=None),
) -> None:
    """Optional single-user gate (FR-24): active only when EGA_AUTH_TOKEN is set."""
    expected = settings.auth_token
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="Invalid token")


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


DbSession = Session  # type alias for readability
