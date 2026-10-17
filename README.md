# EntityGraph Auditor

**A free, open-source, local-first content auditor for entity SEO / AEO / GEO and
AI-retrieval readiness.**

Paste or upload content, pick (or auto-detect) a page type, and get an
evidence-backed audit: entity coverage, relationships, knowledge-graph readiness,
fan-out coverage, passage retrievability, content weight, readability, a
publish/blocking **gate**, and a prioritised list of fixes you can hand to a
human writer. Runs fully offline in deterministic mode; every score is an
**internal editorial heuristic**, not a search-engine or AI-platform metric.

## Why it is different

- **Evidence or it doesn't count.** Every finding points at evidence spans and is
  written as *What · Where · Why · How · Verification · Priority*. Nothing is
  asserted without a span or an explicit `not_assessed` / `unknown` label.
- **Scores are code, not vibes.** All arithmetic runs in Python
  (`packages/scoring`). LLMs only make semantic judgements; they never compute a
  number and never invent evidence.
- **Gate ≠ score.** Fabrication / brand-conflict / regulated-claim blockers are
  reported separately and are **never averaged into** the composite.
- **Local-first, zero-paid-API.** Default is deterministic-only (no model, no
  network). Optionally point it at Ollama (still zero API cost) or a BYOK cloud
  provider.
- **Suggest-only.** Nothing is published or edited for you.
- **MCP is separate from providers.** Audits are callable over MCP; model
  adapters are a distinct layer. Fetched/imported content is untrusted data.

## Architecture (short)

```
apps/web         Next.js + TypeScript UI
apps/api         FastAPI: routes / services / SQLAlchemy / Alembic
auditor/         LangGraph workflow (bounded graph, ≤2 critic loops) + agents
packages/schemas   canonical Pydantic contract (ega_schemas)
packages/parsers   deterministic parsing & structure (ega_parsers)
packages/scoring   deterministic scoring engine & rules (ega_scoring)
packages/providers model adapters: null / Ollama / OpenAI-compatible / cloud (ega_providers)
packages/mcp       MCP server + client config (ega_mcp)
```

Everything imports the one contract in `packages/schemas/ega_schemas/`.
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start (local)

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # or: uv venv && uv pip install -e .
.venv/bin/alembic upgrade head           # SQLite by default
.venv/bin/uvicorn ega_api.main:app --host 127.0.0.1 --port 8000
```

Then check readiness (it will report *deterministic-only mode*):

```bash
curl -s localhost:8000/api/v1/readiness | python -m json.tool
```

Frontend (dev):

```bash
cd apps/web && npm install && npm run dev   # http://localhost:3000
```

### Docker Compose

```bash
docker compose up --build                   # api + web (SQLite)
docker compose --profile postgres up        # optional PostgreSQL
docker compose --profile ollama up          # optional local model (then pull a model)
```

Ports bind to `127.0.0.1` by default. Set `EGA_AUTH_TOKEN` before exposing them
anywhere else.

## Documentation

| Doc | Contents |
|---|---|
| [docs/PRD.md](docs/PRD.md) | the full product specification (source of truth) |
| [docs/HANDOVER.md](docs/HANDOVER.md) | senior developer handover & production operations guide |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | modules, data flow, boundaries |
| [docs/API.md](docs/API.md) | every HTTP endpoint |
| [docs/SCORING.md](docs/SCORING.md) | component scores, formulas, gate, priority |
| [docs/LOCAL_MODE.md](docs/LOCAL_MODE.md) | offline / air-gapped operation |
| [docs/MCP_SETUP.md](docs/MCP_SETUP.md) | run as an MCP server / add MCP servers |
| [SECURITY.md](SECURITY.md) · [THREAT_MODEL.md](THREAT_MODEL.md) | SSRF, injection, secrets |
| [EVALUATION.md](EVALUATION.md) | golden cases & evaluation harness |
| [DECISIONS.md](DECISIONS.md) · [CHANGELOG.md](CHANGELOG.md) | ADRs & history |
| [AGENTS.md](AGENTS.md) · [COORDINATION_TASKS.md](COORDINATION_TASKS.md) | multi-agent build protocol |

## Development

```bash
.venv/bin/python -m pytest tests -q     # full suite
.venv/bin/ruff check .                  # lint
```

## Status

Implemented vertical slice: paste → page type → audit → evidence-backed findings
→ export (Markdown / HTML / JSON / CSV). See [CHANGELOG.md](CHANGELOG.md) for the
current state and [COORDINATION_TASKS.md](COORDINATION_TASKS.md) for in-flight work.

## License

Apache-2.0.
