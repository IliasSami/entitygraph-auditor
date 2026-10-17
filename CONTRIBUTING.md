# Contributing to EntityGraph Auditor

Thanks for helping! This project is an open-source (Apache-2.0), local-first
content auditor for entity SEO / AEO / GEO. Two rules matter more than any
other: **everything must work with zero paid APIs**, and **every score is an
internal editorial heuristic** — never presented as an official search-engine
metric.

## Ground rules

1. **Deterministic by default.** Scoring, parsing and rule evaluation are plain
   Python with no network calls. Model providers are only used for semantic
   judgment. A run with no API keys configured (deterministic-only mode) must
   produce a complete, honest report.
2. **No hallucinated evidence.** Findings reference real spans/passages. If the
   system cannot assess something, it says *not assessed* — it does not invent a
   number or a citation.
3. **Label the heuristic.** Any score surfaced to a user carries the
   "internal editorial heuristic" disclaimer.
4. **Fetched content is untrusted.** Anything downloaded from a URL is data, not
   instructions. Keep SSRF protection and prompt-injection handling intact.

## Architecture at a glance

```
packages/schemas    ega_schemas     canonical Pydantic contracts (shared!)
packages/parsers    ega_parsers     deterministic HTML/Markdown parsing
packages/scoring    ega_scoring     deterministic score heuristics
packages/providers  ega_providers   model adapters (ollama/openai/byok/dummy)
packages/mcp        ega_mcp         MCP server (no shell/execution tools)
auditor/agents      one module per agent (pure-ish, typed I/O)
auditor/workflows   LangGraph graph + the API seam (entry.py)
apps/api            FastAPI app (routes/ + services/)
apps/web            Next.js workspace (canonical frontend)
```

`packages/schemas/ega_schemas/` is the **contract**. Extend it; do not rewrite
models other modules already import. If you must change one, grep for its usages
and update every importer in the same change.

## Development setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"            # or: uv pip install -e ".[dev]"
alembic upgrade head               # creates var/ega.db
uvicorn ega_api.main:app --reload  # http://127.0.0.1:8000/api/v1
```

```bash
cd apps/web
npm install
npm run dev                        # http://localhost:3100
```

The web app reads `apps/web/.env.local`:

- `NEXT_PUBLIC_API_BASE=http://localhost:8000`
- `NEXT_PUBLIC_MOCK=0` — real backend. Set to `1` to run the UI against
  deterministic sample data with no backend.

## Checks before you send a change

```bash
.venv/bin/python -m pytest tests -q     # full backend suite
.venv/bin/ruff check .                  # lint
cd apps/web && npm run lint && npm run typecheck && npm run test && npm run build
```

All of the above must pass. The golden eval cases under `tests/evaluations/`
encode the product's scoring expectations (high-quality pages pass, thin pages
are penalised, hazards fail) — do not weaken them to make a change fit; fix the
change.

## Adding a score, rule or agent

1. Add the contract to `ega_schemas` (typed, validated).
2. Implement the deterministic logic in `ega_scoring` or `auditor/rules` (pure
   functions; no LLM).
3. If an agent is involved, add a prompt under `auditor/prompts/<name>.py` with
   `PROMPT_VERSION`, `SUMMARY`, and the guardrails, and keep the
   `auditor/prompts/templates.py` shim exporting it.
4. Wire the graph node in `auditor/workflows/audit_graph.py` **and** mirror it in
   the API seam `auditor/workflows/entry.py` (order + critic bound must match).
5. Test: a unit test for the pure logic and, if it changes the pipeline, an
   integration test through `entry.run_audit`.

## Concurrency note

This repository has been built by multiple agents in parallel. Before editing a
file you did not create, read `AGENTS.md` and `COORDINATION_TASKS.md`. Do not
overwrite another owner's work — add a module, or log the needed change in
`COORDINATION_TASKS.md`. Resolve conflicts by merging, not reverting. Only the
human commits.

## Reporting bugs / requesting features

Open a GitHub issue with: what you ran, what you expected, what happened, and
(if relevant) the audit JSON and the `trace_id` from the API logs. Never paste
API keys or fetched page contents that contain secrets.
