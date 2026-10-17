# HTTP API — EntityGraph Auditor

Base URL: `http://127.0.0.1:8000/api/v1` (loopback by default).

Every response carries a trace id in the `X-Trace-Id` header; log lines and error
envelopes repeat it. Errors share one envelope:

```json
{ "error": { "code": "not_found", "message": "…", "trace_id": "…" } }
```

Audits are **asynchronous**: `POST /audits` returns `202` with an `audit_id`, then
you poll `GET /audits/{id}` (or stream `GET /audits/{id}/events`).

---

## System

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | liveness; `{"status":"ok"}` |
| GET | `/readiness` | dependency checks + active mode; `status` ∈ `ok`/`degraded` |
| GET | `/health/ready` | alias of readiness |

`/readiness` reports whether a model provider is configured; in deterministic-only
mode it says so explicitly.

## Projects

| Method | Path | Notes |
|---|---|---|
| POST | `/projects` | create → `201` |
| GET | `/projects` | list |
| GET | `/projects/{project_id}` | read |
| PATCH | `/projects/{project_id}` | partial update |
| POST | `/projects/{project_id}/archive` | archive (soft) |
| DELETE | `/projects/{project_id}` | delete → `204` |

## Content

| Method | Path | Notes |
|---|---|---|
| POST | `/content/import` | paste text or upload a file (md/html/txt/docx/pdf). Returns `content_version_id` + a structural summary (word count, headings, language, page-type guess). |
| POST | `/content/fetch-url` | SSRF-guarded single fetch; refuses private/loopback targets and non-http(s) schemes unless explicitly allowed. |

## Workspace (deterministic read-models)

Derived from stored audits and context packs — **no model provider required**, so
these work in zero-API / deterministic-only mode. Every response carries an
explicit `disclaimer` ("internal editorial heuristic"); nothing is model-generated
or inferred, and each fact cites its source (`audit:<id>`, `pack:<id>@<version>`).

| Method | Path | Notes |
|---|---|---|
| GET | `/workspace/entities?project_id=` | Entity Hub registry: merged from every successful audit's `entities` + `eav_rows` and the project's context-pack `canonical_facts`. Computes `pages_used`, cross-source conflict detection, provenance, JSON-LD `@id` + `schema_type`. `404` `PROJECT_NOT_FOUND` when the project is unknown. |
| POST | `/workspace/briefs/generate` | Brief Builder: sources from real fan-out queries, coverage findings, claims, pack facts / banned terms / brand rules, plus the assembled H2 sections. Empty projects return empty lists and say so in the disclaimer. |
| POST | `/workspace/analyze` | Optimizer inspector: readability metrics, headings, entity coverage, banned-term violations, the 5 dimension bands (`entities`/`answers`/`evidence`/`passages`/`originality`) and ranked recommendations. |

> **Two brief generators exist:** `POST /content/briefs/generate` (brief-page
> specific) and `POST /workspace/briefs/generate`. Both are deterministic and
> provenance-labelled; see `COORDINATION_TASKS.md` item 68 for the canonical choice.

## Context / skill packs

| Method | Path | Notes |
|---|---|---|
| POST | `/context-packs/import` | import a pack (archive or JSON) → `201`; stored as data, its scripts are never run |
| GET | `/context-packs` | list summaries |
| GET | `/context-packs/{pack_id}` | read one (includes the stored payload) |
| POST | `/context-packs/{pack_id}/facts` | append a canonical fact → `201` |
| POST | `/context-packs/{pack_id}/entities` | register an entity → `201` |
| GET | `/context-packs/{pack_id}/schema-jsonld` | `schema.org` JSON-LD for the pack |
| DELETE | `/context-packs/{pack_id}` | `204` |

## Audits

| Method | Path | Notes |
|---|---|---|
| POST | `/audits` | create + start → `202` `{audit_id, status}` |
| GET | `/audits` | list (filter by project/status) |
| GET | `/audits/{audit_id}` | status/progress; when done includes `composite`, `gate_status` |
| GET | `/audits/{audit_id}/events` | SSE progress stream |
| GET | `/audits/{audit_id}/entities` | entities |
| GET | `/audits/{audit_id}/triples` | semantic triples |
| GET | `/audits/{audit_id}/fanout` | fan-out queries |
| GET | `/audits/{audit_id}/findings` | findings (What·Where·Why·How·Verification·Priority) |
| GET | `/audits/{audit_id}/scores` | component scores + gate + composite |
| GET | `/audits/{audit_id}/report` | full immutable report snapshot |
| POST | `/audits/compare` | compare two audits (like-for-like checks, gate delta, resolved/new/still-open findings) |
| POST | `/audits/{audit_id}/writer-handoff` | build the writer handoff (suggest-only; never publishes) |
| POST | `/audits/{audit_id}/export` | render `markdown`/`html`/`json`/`csv` (csv = zip) |
| DELETE | `/audits/{audit_id}` | `204` |

Scores are **internal editorial heuristics**; the report repeats the disclaimer.
Gate is reported separately and never averaged into the composite.

## Models & providers

| Method | Path | Notes |
|---|---|---|
| GET | `/models/providers` | catalog (local + cloud); never returns secrets |
| POST | `/models/test-connection` | probe a provider config (bounded timeout) |
| GET | `/models/configs` | list saved configs |
| POST | `/models/configs` | save a config; API keys encrypted at rest (Fernet) → `201` |
| DELETE | `/models/configs/{config_id}` | `204` |

Provider credentials are only stored when `APP_ENCRYPTION_KEY` is set; the API
returns `*_set: true/false` flags, never the secret.

## MCP

| Method | Path | Notes |
|---|---|---|
| GET | `/mcp/servers` | configured external MCP servers |
| POST | `/mcp/servers` | add server (http or stdio) → `201`; auth token encrypted |
| POST | `/mcp/servers/{server_id}/tools` | set the explicit tool **allowlist** |
| DELETE | `/mcp/servers/{server_id}` | `204` |
| GET | `/mcp/tools` | tools this app exposes as an MCP server (read-only analysis) |

See [MCP_SETUP.md](MCP_SETUP.md) for the stdio/HTTP server run commands.

---

## Route inventory

The mounted routers are canonical and deduplicated:
- `health` (`/health`, `/readiness`, `/system/maintenance/purge-test-data`)
- `projects` (`/projects`)
- `content` (`/content/import`, `/content/fetch-url`, `/content/brief`)
- `workspace` (`/workspace/entities`, `/workspace/briefs/generate`, `/workspace/analyze`)
- `packs` (`/context-packs`)
- `audits` (`/audits`)
- `models` (`/models`)
- `mcp` (`/mcp`)
All duplicates (`system.py`, `context_packs.py`, `models_api.py`) have been removed.
