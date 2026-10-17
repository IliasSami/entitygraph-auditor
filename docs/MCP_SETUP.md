# MCP setup — EntityGraph Auditor

EntityGraph Auditor can act as an **MCP server** so MCP-capable clients
(Claude Desktop, IDEs, other agents) can run audits and pull reports. It can
also act as an **MCP client**: it stores external MCP server connections with an
explicit tool allowlist, but only *orchestration* — never a model — decides
whether a call is allowed.

> Security stance (PRD FR-20, FR-24): tool descriptions, tool results and any
> imported skill/context content are **untrusted data**. They never change app
> security, never grant tool permissions, and are never executed. Write or
> destructive tools require explicit human confirmation and an admin allowlist.

## 1. Tools exposed (PRD §12 / FR-20)

Implemented in `packages/mcp/ega_mcp/tools.py` (`TOOL_SPECS`):

| Tool | Purpose |
|---|---|
| `run_content_audit` | Full local-first audit of pasted content/markdown/HTML → component scores, gate, findings |
| `analyze_entities` | Fast extraction: central entity, candidate concepts, triples, EAV status (explicit vs missing) |
| `check_brand_compliance` | Banned terminology + unsubstantiated quantitative claims + compliance blockers |
| `get_audit_report` | Retrieve a stored audit report by `audit_id` |

All tools are **read-only / analysis-only**. None publish, edit, or exfiltrate
content. Additional PRD tools (`map_entity_relationships`,
`simulate_query_fanout`, `compare_versions`, `export_report`,
`import_skill_pack`, `list_recent_audits`, `audit_url`) are on the roadmap and
will follow the same read-only-first rule; `import_skill_pack` treats the pack as
data and never runs its scripts.

## 2. Run as an MCP server

```bash
# stdio transport (typical for desktop clients)
python -m ega_mcp.server --transport stdio

# streamable http transport
python -m ega_mcp.server --transport http --host 127.0.0.1 --port 8765
```

### Claude Desktop config example

```json
{
  "mcpServers": {
    "entitygraph-auditor": {
      "command": "python",
      "args": ["-m", "ega_mcp.server", "--transport", "stdio"],
      "cwd": "/absolute/path/to/entitygraph-auditor"
    }
  }
}
```

Restart the client and the four tools above appear. Every score returned is the
internal editorial heuristic; the tool output repeats the disclaimer.

## 3. Manage *external* MCP servers (the app as a client)

Configured through the API/UI (`/api/v1/mcp/servers`) and stored in
`mcp_server_configs`:

- **Transport**: `http` (endpoint URL) or `stdio` (explicit argv list).
- **Allowed tools**: explicit allowlist. A tool that is not listed is never called,
  regardless of what a model asks for.
- **Credentials**: `auth_token` is encrypted at rest (Fernet, `APP_ENCRYPTION_KEY`)
  and never returned by the API (only `auth_token_set: true/false`).
- **Timeouts**: per-server, bounded.

```bash
curl -s localhost:8000/api/v1/mcp/servers \
  -H 'content-type: application/json' \
  -d '{"name":"my-kb","transport":"http","endpoint":"https://kb.internal/mcp",
       "allowed_tools":["search_docs"],"enabled":true,"auth_token":"…"}'
```

Confirm which tools an imported server exposes, then explicit-allow only the
read tools you want:

```bash
curl -s -X POST localhost:8000/api/v1/mcp/servers/<server_id>/tools \
  -H 'content-type: application/json' -d '{"allowed_tools":["search_docs"]}'
```

## 4. Guardrails

- **No shell/execution tools** are exposed by this app or auto-enabled on
  imported servers.
- Imported/server-provided content is data: it cannot reconfigure the app,
  change the allowlist, read secrets, or trigger outbound calls to new hosts.
- Every MCP call is written to `audit_logs` (redacted payloads, no secrets).
- Confirmation is required before any write-capable tool runs; nothing is applied
  to your content automatically.
