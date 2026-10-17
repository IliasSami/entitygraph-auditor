"""EntityGraph Auditor MCP package."""

from typing import Any

from ega_mcp.tools import (
    TOOL_SPECS,
    tool_analyze_entities,
    tool_check_brand_compliance,
    tool_get_audit_report,
    tool_run_content_audit,
)

__all__ = [
    "TOOL_SPECS",
    "create_mcp_server",
    "tool_analyze_entities",
    "tool_check_brand_compliance",
    "tool_get_audit_report",
    "tool_run_content_audit",
]


def __getattr__(name: str) -> Any:
    if name == "create_mcp_server":
        from ega_mcp.server import create_mcp_server

        return create_mcp_server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

