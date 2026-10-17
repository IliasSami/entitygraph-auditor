"""EntityGraph Auditor MCP package."""

from ega_mcp.server import create_mcp_server
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
