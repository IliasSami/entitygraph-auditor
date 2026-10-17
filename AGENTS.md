# AGENTS.md — Multi-agent coordination (READ BEFORE EDITING)

This repository is being built **concurrently by two agents** (an AI coding agent
working in this harness, and "Antigravity"). To avoid clobbering shared files,
follow these rules.

## Golden rules

1. **`packages/schemas/ega_schemas/` is the canonical contract.** Extend it; do
   not rewrite models other modules already import. Before changing a model,
   grep for its usages.
2. **Never overwrite a file you do not own.** Add a new module instead, or
   record the needed change in `COORDINATION_TASKS.md` for the other agent.
3. **Run the test suite before you finish a unit of work:**
   `cd "<repo>" && .venv/bin/python -m pytest tests -q`.
   If a failure is in a file you do not own, do not "fix" it by reverting —
   note it in `COORDINATION_TASKS.md`.
4. **Everything must work with zero paid APIs** (deterministic-only mode), and
   every score is labelled an internal editorial heuristic.
5. `git` commits: only the human should commit, unless both agents agree
   otherwise in `COORDINATION_TASKS.md`.

## File ownership map (append/amend as work starts)

| Area | Owner | Notes |
|---|---|---|
| `packages/schemas/ega_schemas/` | shared — contract | change via coordination only |
| `packages/parsers/ega_parsers/` | parser worker | deterministic parsing only |
| `packages/scoring/ega_scoring/`, `auditor/rules/` | scoring worker | pure functions, no LLM |
| `packages/providers/ega_providers/`, `auditor/prompts/` | provider worker | no secrets in logs |
| `auditor/agents/`, `auditor/workflows/` | workflow worker | bounded graph, ≤2 critic loops |
| `apps/api/app/` | API owner | routes/ + services/ |
| `apps/web/` | frontend worker | Next.js |
| `packages/mcp/ega_mcp/` | MCP worker | no shell/execution tools |
| `apps/api/app/services/fetcher.py`, `packs.py` | security services worker | SSRF + safe extraction |
| `apps/api/app/services/export.py`, `compare.py` | export worker | |
| `docs/`, `DECISIONS.md`, `SECURITY.md`, `THREAT_MODEL.md`, `EVALUATION.md`, `CHANGELOG.md` | docs | keep current |

## Live work log

- 13:30 API owner wrote: `config.py`, `db.py`, `deps.py`, `errors.py`,
  `models.py`, `routes/{health,projects,content,packs,audits,mcp,models}.py`,
  `services/audits.py`, `alembic.ini`, `migrations/`.
- Parsers, scoring/rules, providers/prompts, frontend, fetcher/packs,
  export/compare workers are running in the background.

## Known conflict areas (fix by merging, not reverting)

- `packages/schemas/ega_schemas/content.py` — two versions existed (one with
  `HeadingNode/TextStats/ContentSourceMeta`, one with `TextSpan/Heading/Link`).
  **Resolve into ONE model set and update all importers.**
- `apps/api/app/main.py` — two app factories existed. Keep a single
  `create_app()`; do not duplicate routers.
- `apps/api/app/routes/` — `packs.py` vs `context_packs.py`, `models.py` vs
  `models_api.py` — keep one router per domain, remove duplicates in the
  integration pass.
