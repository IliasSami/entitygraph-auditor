"""Official MCP Server for EntityGraph Auditor (PRD §12, FR-20)."""

from __future__ import annotations

import sys
from typing import Any, Optional

from mcp.server.mcpserver import MCPServer

from ega_mcp.tools import (
    tool_analyze_entities,
    tool_check_brand_compliance,
    tool_get_audit_report,
    tool_run_content_audit,
)


def create_mcp_server() -> MCPServer:
    """Create and configure the EntityGraph Auditor MCPServer instance."""
    server = MCPServer(
        name="entitygraph-auditor",
        version="0.1.0",
        description=(
            "EntityGraph Auditor: local-first Entity SEO, AEO, and AI-search retrieval content auditor. "
            "Scores are internal editorial heuristics."
        ),
    )

    @server.tool(
        name="run_content_audit",
        description="Run a full local-first entity and AEO/GEO audit on web content or markdown.",
    )
    def run_content_audit(
        content: str,
        page_type: str = "general",
        primary_query: Optional[str] = None,
    ) -> dict[str, Any]:
        return tool_run_content_audit(content, page_type, primary_query)

    @server.tool(
        name="analyze_entities",
        description="Extract central entity, candidate concepts, knowledge triples, and EAV attributes.",
    )
    def analyze_entities(content: str) -> dict[str, Any]:
        return tool_analyze_entities(content)

    @server.tool(
        name="check_brand_compliance",
        description="Evaluate brand compliance, detecting banned terms and unsubstantiated claims.",
    )
    def check_brand_compliance(
        content: str,
        banned_terms: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        return tool_check_brand_compliance(content, banned_terms)

    @server.tool(
        name="get_audit_report",
        description="Retrieve an existing audit report by audit_id.",
    )
    def get_audit_report(audit_id: str) -> dict[str, Any]:
        return tool_get_audit_report(audit_id)

    return server


def main():
    """CLI entrypoint for running the MCP server over stdio or sse."""
    server = create_mcp_server()
    transport = "stdio"
    if "--sse" in sys.argv:
        transport = "sse"
    server.run(transport=transport)


if __name__ == "__main__":
    main()
