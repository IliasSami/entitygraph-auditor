# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — beta hardening

### Added
- **Workspace read-model API** (`/api/v1/workspace/*`): deterministic, provenance-labelled
  endpoints that back screens which previously rendered fabricated samples —
  `GET /workspace/entities` (Entity Hub registry merged from successful audits' `entities` /
  `eav_rows` + context-pack `canonical_facts`, with `pages_used`, cross-source conflict
  detection and per-fact source labels), `POST /workspace/briefs/generate` (brief sources from
  real fan-out queries, findings, claims and pack facts/rules), and `POST /workspace/analyze`
  (readability, headings, entity coverage, banned-term violations, 5 dimension bands and
  recommendations). New shared schema module `ega_schemas/workspace.py`; no model provider is
  required, so all three work in deterministic-only mode. 6 integration tests.
- **Content Optimizer Studio (`/optimizer`)**: Free, open-source alternative to Surfer SEO, NeuronWriter, and Frase for Entity SEO and Machine-Efficient Content Retrieval. Features real-time Flesch-Kincaid readability scoring, heading hierarchy verification, target vs actual entity densities with 1-click insertion, answer-first passage diagnostics, brand compliance detection, and 1-click deep multi-agent audit dispatch.
- **AI Connectors & Knowledge Hub (`/settings`)**:
  - **Claude Pro (Projects & Chat Windows)**: 1-click Project Knowledge generator that bundles brand rules, central entity, ICP, market, canonical facts, and banned terms into an optimized Claude system prompt.
  - **Claude Desktop (MCP)**: Local-first MCP server integration configuration block for `claude_desktop_config.json`.
  - **ChatGPT (Custom GPT Actions)**: 1-click OpenAPI 3.1 schema specification for OpenAI custom actions.
  - **Cursor / Windsurf / Claude Code**: IDE MCP configuration snippets.
- **Database Maintenance & Cleanup**: Added `POST /api/v1/system/maintenance/purge-test-data` and a UI action in Settings to purge test/smoke workspaces and run SQLite `VACUUM` to reclaim disk space.
- **Brand Identity & Streamlined Navigation**: Custom hex-prism entity network logo in `apps/web/src/components/brand/logo.tsx`, emerald/cyan enterprise color palette, streamlined 5-item top navigation, and quick launch hero cards on the dashboard.

### Fixed
- **Optimizer inspector showed fabricated scores.** The 5 dimension bands were hard-coded
  (`68% / 42% / 45% / 62% / 90%`) and only shifted when a canned "Apply" button was pressed,
  and the review banner claimed *"4 pending suggestions from local Ollama run"* although no
  Ollama (or any model provider) is configured. The bands, recommendations and pending count
  now come from `POST /workspace/analyze` (debounced 500ms) and carry the endpoint's
  disclaimer; the copy reports the real recommendation count. The single-banned-term evidence
  score no longer reads "strong".
- **Entity Hub rendered a hard-coded knowledge graph.** `app/context-packs/page.tsx` seeded
  `DEFAULT_ENTITIES` (fabricated Fernhill entities/facts) and never read a backend. It now
  reads `GET /workspace/entities` for the active project with loading/empty states; local draft
  adds are kept as a session overlay and persisted through `POST /context-packs/{id}/entities`
  and `/{id}/facts`.
- **Content brief generator fabricated data sources.** `services/briefs.py` (behind
  `POST /content/brief`, which the Briefs screen calls) labelled query-derived prompts as
  `"Google PAA"` / `"Perplexity"` / `"AI Citation Gap"`, invented "verified" fallback facts
  and a `"Entity Hub"` provenance, and returned no disclaimer. Sources now say what they
  actually are (`"Query pattern · Pricing"`, `"Coverage gap · derived"`,
  `"Context pack · canonical fact"` / `"Unverified placeholder"`), ungrounded section facts
  state *"No verified fact…"* instead of asserting a claim, `lexicon.include` is limited to
  the real query plus pack-derived terms, and the response carries
  `grounded` + a `disclaimer`. 7 tests in `tests/unit/test_content_brief_honesty.py`.
- **Brief Builder presented sample content as real work.** The page seeded `SOURCES` /
  `DEFAULT_SECTIONS` and rendered them before any API call, so fabricated specifics
  (a "$349/mo fact from Entity Hub", "2024 benchmarks") appeared as production content.
  A banner now labels the un-assembled outline a **sample** and is replaced by the
  generator's disclaimer on *Auto-assemble*; the source counter read the static constant
  instead of the live list; and the word target, reading level, intent and Information-Gain
  directives now come from the brief (`recommended_word_count`, `reading_level`, `intent`,
  `lexicon.replace` / `lexicon.avoid`) instead of hard-coded strings, with the read-time
  estimate derived from the word target.
- **Entity Hub status chrome showed fake counters.** `app/context-packs/page.tsx` hard-coded
  `1 active conflict across site`, `● synchronized`, `schema_version: 2026.09-rc2`,
  `1 active conflict across 7 pages` and a `v2.4.1 schema` badge. They now derive from the
  loaded registry (real conflict count, `source_audits` / `source_packs` provenance, live
  sync state) and the entity definition says *"No canonical definition recorded"* rather than
  implying an inferred one — keeping the "nothing is model-generated" disclaimer truthful.
- **Optimizer chrome claimed an unconfigured local model.** Hard-coded copy —
  `Self-hosted Agent Engine`, `Rev 18 · Qwen-2.5 14b / Local active`, `7 inc · 3 exc`,
  `ChatGPT & Perplexity snapshot`, `Service + FAQPage synced`, `JSON-LD injected`,
  `Saved locally · Ollama ready` — asserted tooling the product does not run (`GET /models/configs`
  returns `[]`). Replaced with the live analysis state (`5 dimensions · N suggestions`),
  tracked-entity count, `Deterministic analysis — no external SERP feed configured`,
  `generated on audit export / preview only — not injected`, and `Draft in editor · not persisted`.
- **Mock mode left two screens unbacked and one score dishonest.** `generateContentBrief` was
  the only API method with no mock, so *Auto-assemble* failed without a backend despite the
  documented "every method is served by the deterministic in-memory mock" contract. Added
  `ContentBriefPayload` / `ContentBriefResponse` types and a deterministic mock; the mock's
  evidence score now matches the API (`max(15, 100 − 40·violations)` — a single banned term
  reads "fair", not "strong") and its analyze disclaimer carries the required
  **internal editorial heuristic** label. 4 new e2e tests in `e2e/screens.spec.ts`.
- **Report scores shape (PRD §22).** `AuditReport.scores` is now a `Scorecard` in
  memory that serializes to the flat `{EOS: {...}, …, AVR: {...}}` map, matching
  the PRD and the web client. Removed the `PydanticSerializationUnexpectedValue`
  warning that printed on every report dump; flat maps and full dumps both
  rehydrate on read (`validate_assignment` keeps post-init assignment working —
  see DECISIONS ADR-010).
- **Brand / context packs now affect the gate.** `entry.run_audit` forwards
  `brand_rules`, `banned_terms`, `canonical_facts`, `approved_claims`, internal
  links and topical-map rows into the scoring gate. A pack's banned term now adds
  a `Prohibited term detected` critical issue and can flip the gate to `fail`
  (FR-16), verified end-to-end over HTTP.
- **Critic stage actually runs on the API path.** `entry.run_audit` runs the
  bounded critic (≤ 2 repair loops) and records `critic` stage records,
  `critic_loops` and `critic_notes`; a provider failure skips the stage instead of
  crashing the audit.
- **Coverage / passage findings were dropped.** `entry.run_audit` copies
  `coverage_rows` and `passage_findings` back onto the run state; `build_report`
  passes them through and sets `composite_avr`.
- **Dummy provider dispatched on the wrong agent.** `DummyDeterministicProvider`
  matched loose keywords in order, so the Coverage prompt (which mentions
  "fan-out queries") was served the fan-out payload. It now dispatches on the
  unique `Agent N` header first.
- **Uncited coverage could inflate FCS.** The coverage agent now discards
  `covered`/`partial` rows that cite no `matched_passage_ids` (the prompt requires
  a covered claim to name its passage). In deterministic-only mode FCS is
  therefore honestly reported as *not assessed* (PRD §9.4), not zero.
- **Duplicate routers removed** (`routes/system.py`, `routes/context_packs.py`,
  `routes/models_api.py`) — one router per domain (ADR-006).
- **Report page crashed on real data.** The API returns
  `gate.critical_issues` as structured `GateIssue` objects (`{category, severity,
  message, …}`), but the web typed them as `string[]` and rendered them directly
  → *"Objects are not valid as a React child"* plus duplicate `[object Object]`
  keys. The client now accepts `string | GateIssue` and renders readable text
  (ADR-012).
- **`AVR` no longer renders as a broken component card.** The flat PRD §22 `scores`
  map includes `AVR: {value, profile, warning}` (no `score_key`/`weight`); the
  component grid now treats AVR as the composite (shown in the gate summary) and
  skips it (ADR-012).
- **Lint:** removed pre-existing `no-explicit-any` errors in the compare, settings
  and types modules (`npm run lint` back to 0 errors).
- **MCP tool output** rendered gate issues with `str(issue)`, which produced a
  Pydantic repr for structured `GateIssue` objects; it now emits readable text
  (title → message → detail), matching the web client.
- **API Docker image could not boot.** `requirements.lock` (the only dependency
  source in `Dockerfile.api`, which installs with `--no-deps`) was missing
  `pydantic-settings`, so `uvicorn ega_api.main:app` died at import with
  `ModuleNotFoundError: No module named 'pydantic_settings'`. Added
  `pydantic-settings==2.16.0`; the image now starts and serves
  `GET /api/v1/health`.
- **API Docker image missed its subpackages.** The setuptools `packages` list
  declared `ega_api` but not `ega_api.routes` / `ega_api.services`; editable
  installs resolve them through the parent package, so this only surfaced in the
  non-editable Docker build (`ModuleNotFoundError: No module named
  'ega_api.routes'`). Both subpackages are now declared.
- **Screens claimed success for actions that never happened.** Eight
  `alert(...)` calls in the optimizer's Entity Hub (`/context-packs`), AI
  Visibility (`/compare`) and Brief Builder (`/briefs`) asserted fabricated
  outcomes ("All 8 grounded facts synchronized with sqlite knowledge graph",
  "Prompt added to monitoring queue", "Auto-assembled 5 outline sections…").
  They now (a) perform a real action where one exists (clipboard write on copy;
  react-query `refetch()` on reload, reporting the real row count), (b) add to
  local component state clearly badged `local draft · session only`, or (c) state
  honestly that the action needs a configured provider and ran nothing. The
  `/api/visibility` POST stub no longer claims a crawl was dispatched.
- **Audit comparison UI was lost in the redesign.** The `/compare` rewrite
  replaced the audit diff with a stub that never called the backend, so
  `POST /api/v1/audits/compare` had no UI even though the endpoint and its tests
  remained. The "Audit Run Diff" tab now issues the real request and renders
  score movement, entity changes, coverage/FCS delta, resolved/new findings and
  warnings (with the heuristic disclaimer); both selects got proper
  `htmlFor`/`id` labels.
- **`ruff check .` failed** on `prism-geo/`, an unrelated nested repository that
  happens to live in the working copy; added it to `[tool.ruff] extend-exclude`.
- **The web image ignored its `NEXT_PUBLIC_API_BASE` build arg.** `Dockerfile.web`
  and `docker-compose.yml` both plumb the arg, but `apps/web/.env.local`
  (copied into the build context) also sets it, and Next.js gives `.env.local`
  priority over the shell environment, so the arg was silently overridden. Local
  env files are now excluded from the image.
- **The AI Visibility screen did not work in the container.** `/api/visibility`
  reads `prism-geo/data/prismgeo.db`, which `.dockerignore` excluded and
  `Dockerfile.web` never copied, so `/compare` fell back to the empty state. The
  read-only sample dataset is now shipped into the image. Removed a hard-coded
  developer absolute path from the PrismGEO database resolver.
- **Deterministic baseline produced malformed entity names.** The candidate-entity
  regex in the zero-cost baseline provider used `\s+` between capitalized words,
  which also matches newlines, so adjacent headings/lines were glued into single
  names (`"Our Beans\nSingle"`, duplicated multi-line brand names). It now uses
  `[ \t]+`, yielding clean entities.
- **Baseline results were not disclosed.** The shared heuristic disclaimer now
  states that when no model provider is configured, semantic sections come from
  the built-in deterministic baseline and are illustrative placeholders, not
  observed evidence (see the open P1 in `COORDINATION_TASKS.md`).
- **Frontend lint regressions** (5 errors: `no-require-imports`,
  `set-state-in-effect` ×3, `react/no-unescaped-entities`). The effect-driven
  URL/localStorage/default-project initialisers were replaced with derived state
  or lazy initialisers, and the dev-only redirector script is now ignored by
  ESLint. `npm run lint` is back to 0 errors.
- **Two stale Playwright specs** (Home no longer renders the sample-banner
  testid; the audit-comparison view moved behind the "Audit Run Diff" tab) were
  updated to the new UI. Suite is 9/9.
- **The deterministic baseline fabricated evidence.** In zero-API mode
  `DummyDeterministicProvider` (the default provider, and load-bearing because the
  `null` provider raises) returned outputs that were not derived from the audited
  text: a canned claim *"Engineered for high-concurrency transactional workloads."*
  marked **verified** with a fake `src-doc` evidence id; content-independent triples
  (*"provides → high performance"*, *"complies_with → security standards"*); canned
  `category=Service` / `protocol=Standard` / `encryption=TLS` EAV rows; fabricated
  coverage rows; the boilerplate recommendation *"Clarify core architectural
  trade-offs"* (`excerpt: "Core Architecture"`) and a hard-coded measurement plan;
  and a fixed `approved/9.0` critic verdict. The provider is now strictly
  content-derived — claims are always `unverified` with empty evidence ids, triples
  come only from real sentences, EAV rows are emitted only when the text states the
  value, recommendations are derived from the run's real weaknesses/gaps, and the
  critic admits that no semantic QA ran. Extraction was also improved honestly
  (markdown-aware sentence splitting; named standards surfaced as trust entities;
  triples typed by predicate semantics). This is what a golden-case API e2e had been
  masking: its `composite ≥ 5.0` threshold was met only because the fake *verified*
  claim injected a bogus evidence source. 7 regression tests in
  `tests/unit/test_dummy_provider_honesty.py`.
- **Publish tab reported an unevaluated gate as a failure.** `publish-tab.tsx`
  rendered every non-pass gate as *"unresolved gate issues"* in rose, so
  `not_configured` (no brand pack → the gate is not evaluated) read as a blocker.
  It now shows a neutral state with *"No brand pack configured — the gate was not
  evaluated. Fabrication checks still apply."* and only `fail` reads as unresolved.
- **Brief generator defaults were still invented.** `services/briefs.py` recovery
  copy used a phantom brand/location; defaults are now `"Your brand"` / `"your
  market"`, the ungrounded pricing source says *"No verified pricing fact in the
  active context pack"*, and the last "retainer" leftovers were replaced with neutral
  wording. 8 tests in `tests/unit/test_content_brief_honesty.py`.

### Changed
- **CORS** allows `http://localhost:3100` / `127.0.0.1:3100` by default so the web
  app can call the API in real mode.
- **`apps/web/.env.local`** defaults to `NEXT_PUBLIC_MOCK=0` (real backend);
  Playwright still forces mock mode in its own config.

### Added
- `tests/integration/test_entry_workflow.py` — real entry-path coverage: full
  pipeline + bounded critic, brand pack → gate `fail`, baseline → `not_configured`.
- `CONTRIBUTING.md`.

## [0.1.0] - 2026-10-16

### Added
- **Core Schemas (`ega_schemas`)**: Full Pydantic v2 domain models for entities, EAV rows, triples, fan-out queries, claims, findings, scoring, and audit reports.
- **Deterministic Parsers (`ega_parsers`)**: Clean HTML/Markdown parsing, section/passage segmentation, link categorization, and readability heuristics.
- **Deterministic Scoring Engine (`ega_scoring`)**: Transparent 0-10 heuristics for EOS, ERS, KGR, FCS, PRS, CWS, HRS, and composite AVR with gate overrides.
- **Model Providers Layer (`ega_providers`)**: Unified provider abstraction supporting Ollama, OpenAI-compatible APIs, Cloud BYOK, and local deterministic fallback.
- **Multi-Agent Audit Workflow (`auditor`)**: LangGraph 14-agent constrained graph with intake classification, entity/EAV extraction, triple analysis, query fan-out, claim verification, human utility review, compliance gate, scoring, priority handoff, and critic/QA loop.
- **FastAPI REST API (`apps/api`)**: Complete PRD §11 endpoints for projects, content, context packs, audits, findings, compare, export, and health checks.
- **Interactive Web Workspace (`apps/api/app/static`)**: Modern web dashboard for running audits, inspecting entities and triples, reviewing recommendations, and exporting briefs.
- **MCP Server (`ega_mcp`)**: Official Model Context Protocol tools for external AI agents (Claude Desktop, Cursor, Antigravity).
- **Evaluation Suite (`tests/evaluations`)**: Golden audit cases for benchmarking reproducibility, calibration, and anti-hallucination gates.
