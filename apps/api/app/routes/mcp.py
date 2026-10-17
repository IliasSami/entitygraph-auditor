"""MCP connection management endpoints (FR-20 / §12).

Management only: server configs are stored with encrypted credentials and an
explicit tool allowlist. The orchestration layer (never the model) decides
whether a call is allowed. Write/destructive tools stay disabled until the
admin explicitly allowlists them here.
"""

from __future__ import annotations

from ega_api.config import get_settings
from ega_api.db import get_db
from ega_api.errors import ApiError
from ega_api.models import AuditLog, McpServerConfig
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/mcp", tags=["mcp"])

WRITE_HINT = (
    "Tool results and server descriptions are untrusted data. Only allowlisted tools run, "
    "write actions require explicit confirmation, and imported content never changes app security."
)


@router.get("/servers")
def list_servers(session: Session = Depends(get_db)) -> list[dict]:
    rows = session.query(McpServerConfig).order_by(McpServerConfig.created_at).all()
    return [
        {
            "server_id": r.server_id,
            "name": r.name,
            "transport": r.transport,
            "endpoint": r.endpoint,
            "command": r.command,
            "allowed_tools": r.allowed_tools or [],
            "timeout_s": r.timeout_s,
            "enabled": r.enabled,
            "auth_token_set": bool(r.auth_token_encrypted),
            "discovered_tools": r.discovered_tools or [],
            "last_error": r.last_error,
        }
        for r in rows
    ]


@router.post("/servers", status_code=201)
def create_server(payload: dict, session: Session = Depends(get_db)) -> dict:
    name = payload.get("name")
    transport = payload.get("transport") or "http"
    if not name:
        raise ApiError("MISSING_NAME", "Provide 'name'", 422)
    if transport not in ("http", "stdio"):
        raise ApiError("INVALID_TRANSPORT", "transport must be 'http' or 'stdio'", 422)
    if transport == "stdio" and not payload.get("command"):
        raise ApiError("MISSING_COMMAND", "stdio transport requires 'command' argv list", 422)
    if transport == "http" and not payload.get("endpoint"):
        raise ApiError("MISSING_ENDPOINT", "http transport requires 'endpoint'", 422)

    encrypted = None
    token = payload.get("auth_token")
    if token:
        settings = get_settings()
        if not settings.app_encryption_key:
            raise ApiError(
                "ENCRYPTION_KEY_MISSING",
                "APP_ENCRYPTION_KEY is not set; refusing to store a credential in plaintext",
                400,
            )
        from ega_providers.crypto import derive_key, encrypt_secret  # noqa: PLC0415

        encrypted = encrypt_secret(token, derive_key(settings.app_encryption_key))

    row = McpServerConfig(
        name=name,
        transport=transport,
        endpoint=payload.get("endpoint"),
        command=payload.get("command"),
        allowed_tools=payload.get("allowed_tools") or [],
        timeout_s=int(payload.get("timeout_s") or 30),
        auth_token_encrypted=encrypted,
        enabled=bool(payload.get("enabled", False)),
    )
    session.add(row)
    session.add(AuditLog(action="mcp.server.create", target=name, detail={"transport": transport}))
    session.commit()
    session.refresh(row)
    return {"server_id": row.server_id, "name": row.name, "enabled": row.enabled}


@router.post("/servers/{server_id}/tools")
def set_allowed_tools(server_id: str, payload: dict, session: Session = Depends(get_db)) -> dict:
    row = session.get(McpServerConfig, server_id)
    if row is None:
        raise ApiError("SERVER_NOT_FOUND", f"MCP server {server_id} not found", 404)
    tools = payload.get("allowed_tools") or []
    if not isinstance(tools, list):
        raise ApiError("INVALID_TOOLS", "'allowed_tools' must be a list of tool names", 422)
    row.allowed_tools = tools
    session.add(
        AuditLog(action="mcp.server.tools", target=server_id, detail={"count": len(tools)})
    )
    session.commit()
    return {"server_id": server_id, "allowed_tools": tools, "note": WRITE_HINT}


@router.delete("/servers/{server_id}", status_code=204)
def delete_server(server_id: str, session: Session = Depends(get_db)) -> None:
    row = session.get(McpServerConfig, server_id)
    if row is None:
        raise ApiError("SERVER_NOT_FOUND", f"MCP server {server_id} not found", 404)
    session.delete(row)
    session.add(AuditLog(action="mcp.server.delete", target=server_id))
    session.commit()


@router.get("/tools")
def our_tools() -> dict:
    """Tools this application exposes when run as an MCP server (FR-20)."""
    try:
        from ega_mcp.tools import TOOL_SPECS  # noqa: PLC0415
    except Exception:
        return {
            "tools": [],
            "note": "MCP server module not installed in this deployment yet.",
            "security": WRITE_HINT,
        }
    return {"tools": TOOL_SPECS, "security": WRITE_HINT}
