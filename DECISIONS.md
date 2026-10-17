# Architectural Decisions Log (DECISIONS.md)

This log records architecturally significant decisions made during the design and implementation of **EntityGraph Auditor (EGA)**.

---

## ADR-001: Local-First Architecture and Zero-Paid-API Baseline

- **Date:** 2026-10-16
- **Status:** Accepted
- **Context:** The PRD specifies that EntityGraph Auditor must be free and open-source software that can run with local models and local storage without requiring any paid API to execute a baseline audit.
- **Decision:** 
  1. Default to SQLite with SQLAlchemy 2.0 for out-of-the-box local operation, while keeping compatibility with PostgreSQL.
  2. Implement deterministic parsers, extractors, and rule-based heuristic scoring that run 100% locally with zero external network calls.
  3. Provide a `DummyDeterministicProvider` alongside Ollama and OpenAI-compatible adapters, ensuring tests and baseline audits succeed even when no LLM runtime is running.
- **Consequences:** The system is immediately runnable, testable in CI, and preserves user data privacy on localhost.

---

## ADR-002: Bounded Workflow State Graph (LangGraph) vs Autonomous Swarm

- **Date:** 2026-10-16
- **Status:** Accepted
- **Context:** PRD §0 Rule 3 mandates: "Use bounded agents, not an uncontrolled agent swarm. The workflow must be a predictable graph with typed inputs and outputs, timeouts, token limits, retries, trace IDs, cached intermediate results, and a final critic/validation step."
- **Decision:** Build the multi-agent pipeline as a structured LangGraph state graph. The orchestrator and node transitions are deterministic. Each node has strict input/output Pydantic schemas. The Critic node executes a maximum of two repair cycles before returning the report with explicit caveats if discrepancies persist.
- **Consequences:** Eliminates runaway loops, non-deterministic execution paths, and token budget exhaustion while maintaining clear inspectability and debugging.

---

## ADR-003: Deterministic Scoring Separation from Model Inference

- **Date:** 2026-10-16
- **Status:** Accepted
- **Context:** PRD §0 Rule 2 and §9 mandate that scoring calculations must be ordinary code and transparent editorial heuristics, never opaque numbers or platform ranking claims.
- **Decision:** Agent nodes extract structured evidence (entities, EAV rows, triples, passages, claims, gaps). The scoring engine (`ega_scoring`) executes exact mathematical rubrics (EOS, ERS, KGR, FCS, PRS, CWS, HRS, AVR) deterministically from that structured evidence. Models do not calculate the final score.
- **Consequences:** Scoring is 100% reproducible for identical structured inputs. Every point deduction is linked to exact missing elements, vague attributes, or unsupported claims.

---

## ADR-004: Dual MCP Server and LLM Provider Abstraction

- **Date:** 2026-10-16
- **Status:** Accepted
- **Context:** PRD §0 Rule 7 and §12 define MCP as a tool/context protocol, distinct from LLM provider adapters.
- **Decision:** 
  1. `packages/providers/ega_providers`: Unified model provider layer for text generation and structured outputs (Ollama, OpenAI-compatible, Cloud BYOK, Dummy deterministic).
  2. `packages/mcp/ega_mcp`: MCP server implementation using the official `mcp` SDK exposing standard tools (`run_content_audit`, `get_audit_report`, `analyze_entities`, `check_brand_compliance`).
- **Consequences:** Clean separation of concerns. External agent clients (Cursor, Claude Desktop, Antigravity) can call EntityGraph Auditor via MCP without muddying internal model execution.

---

## ADR-005: Security, SSRF Mitigation, and Prompt Injection Defense

- **Date:** 2026-10-16
- **Status:** Accepted
- **Context:** Audited content originates from arbitrary web pages and user inputs. Untrusted text could attempt prompt injection or SSRF when fetching URLs.
- **Decision:**
  1. URL fetching validates hostnames, forbids loopback/private/link-local IPv4/IPv6 addresses, checks content length limits, and respects robots.txt.
  2. Ingested user content is strictly treated as untrusted data. In prompts, user content is isolated in demarcated XML blocks (`<untrusted_content>`) with explicit system instructions prohibiting execution of commands or instructions embedded within the content.
  3. Sensitive API keys and provider tokens are encrypted or loaded via environment variables; never logged or exposed in client responses.
- **Consequences:** Resilient against SSRF and indirect prompt injection attacks.

---

## ADR-006: One Router per Domain (Duplicate-Module Deduplication)

- **Date:** 2026-10-16
- **Status:** Accepted
- **Context:** Two agents produced overlapping routers: `health.py` vs `system.py`,
  `packs.py` vs `context_packs.py`, `models.py` vs `models_api.py`.
- **Decision:** Exactly seven routers are mounted by `create_app()`:
  `health, projects, content, packs, audits, models, mcp`. The unmounted duplicates
  (`routes/system.py`, `routes/context_packs.py`, `routes/models_api.py`) are
  removed once their last unique behaviour is folded into the canonical router.
  No duplicate prefix may be mounted, and `main.py` keeps a single `create_app()`.
- **Consequences:** One endpoint per path; no order-dependent route shadowing.

---

## ADR-007: API Workflow Adapter over the Bounded LangGraph Graph

- **Date:** 2026-10-16
- **Status:** Accepted
- **Context:** The API layer persists a richer `run.AuditRunState` (source meta,
  context-pack versions, prompt versions, stage records) while the agent graph
  uses `audit.AuditRunState`. `auditor/workflows/entry.py` also re-implemented the
  pipeline sequentially, bypassing `build_audit_graph()` and the critic loop.
- **Decision:** Execution goes through the bounded LangGraph graph
  (`execute_audit` → `(state, AuditReport)`), satisfying ADR-002. The API keeps
  `run.AuditRunState` as a *view* and `build_report()` as the API-side adapter;
  `entry.run_audit` is reduced to field mapping (no pipeline logic) or retired.
  No code may sequence agents manually.
- **Consequences:** Exactly one execution path, with the critic's ≤2 repair loops
  and the timeline as the single source of stage truth.

---

## ADR-008: Report Scores Field Accepts Both Scorecard and Mapping

- **Date:** 2026-10-16
- **Status:** Accepted
- **Context:** Reports are stored as an immutable JSON snapshot; a `Scorecard`
  round-trips through JSON as a plain mapping, but the in-memory scoring path
  produces a typed `Scorecard`. Consumers (export, compare, API) need both.
- **Decision:** `AuditReport.scores` is typed `Scorecard | dict[str, ComponentScore]`
  with a normalizing validator (a mapping is rehydrated into a `Scorecard` on read).
  Read paths must not assume either shape; write paths pass the `Scorecard`.
- **Consequences:** No serializer warnings, no `AttributeError` on either shape,
  and PRD §22's `report["scores"]["EOS"]` indexing keeps working.

---

## ADR-009: Next.js Workspace Is the Canonical Frontend

- **Date:** 2026-10-16
- **Status:** Accepted
- **Context:** Two UIs appeared: the Next.js workspace under `apps/web` (routes
  for projects, audits, wizard, context packs, settings; vitest + playwright) and
  a single-file dashboard at `apps/api/app/static/index.html` served by the API.
  The PRD specifies a Next.js + TypeScript frontend.
- **Decision:** `apps/web` is the canonical frontend and the feature target. The
  static `index.html` is retained **only** as an optional no-build fallback for a
  quick zero-install demo; new features go to `apps/web` only. Both talk to the
  same documented API (`docs/API.md`).
- **Consequences:** One feature target, no split-brain UI work; the API still
  boots with a usable page even without Node installed.

---

## ADR-010: `AuditReport.scores` Is a `Scorecard` That Serializes to the Flat PRD §22 Map

- **Date:** 2026-10-16
- **Status:** Accepted (supersedes ADR-008)
- **Context:** ADR-008's `Scorecard | dict[str, ComponentScore]` union worked but
  (a) emitted a `PydanticSerializationUnexpectedValue` warning on **every** report
  dump, and (b) serialized to a *nested* Scorecard dump, whereas PRD §22 and the
  frontend (`AuditReport.scores: Record<string, ComponentScore>`) both specify a
  **flat** map `{EOS: {...}, …, AVR: {value, profile, warning}}`.
- **Decision:** `AuditReport.scores` is typed `Scorecard` only. A
  `field_serializer` emits the flat PRD §22 map; a `field_validator(mode="before")`
  rehydrates a flat map, a full Scorecard dump, or a Scorecard; the `AVR` entry is
  carried only when a composite exists. `model_config = ConfigDict(
  validate_assignment=True)` so post-init `report.scores = {...}` still coerces.
- **Consequences:** Report JSON matches PRD §22 exactly; the warning is gone; the
  in-memory object stays a `Scorecard` so `export`/`compare`/`writer-handoff`
  (`.items()`, `.get()`, `.avr`, `.disclaimer`) keep working. The `/audits/{id}/scores`
  endpoint still returns the nested `Scorecard`, which is what the web `Scorecard`
  type expects.

---

## ADR-011: Coverage Claims Must Cite a Passage, and the Dummy Dispatches by Agent Number

- **Date:** 2026-10-16
- **Status:** Accepted
- **Context:** `DummyDeterministicProvider.call` dispatched on ordered substring
  keywords, so the Coverage prompt (which mentions "fan-out queries") matched the
  *fanout* branch and returned `fanout_queries`; the coverage agent then always saw
  zero rows. Separately, the dummy's canned coverage reported `covered` without
  naming a matched passage, which would credit any page — including thin pages.
- **Decision:** (1) The dummy dispatches on the unique `Agent N` header in each
  prompt, falling back to keywords only when no number is present. (2) The coverage
  agent discards `covered`/`partial` rows that cite no `matched_passage_ids`, because
  the coverage prompt requires a covered claim to name its passage ("you do not
  credit a page for answering a question it never addresses").
- **Consequences:** Agent 8 receives coverage data, not fan-out data; fabricated or
  uncited coverage cannot inflate FCS. In deterministic-only mode this means FCS is
  honestly *not assessed* (PRD §9.4: zero rows is not-assessed, not zero), which is
  the behaviour the golden eval cases are calibrated against.

---

## ADR-012: The Web Client is Tolerant of `str | GateIssue` and Treats `AVR` as a Composite

- **Date:** 2026-10-16
- **Status:** Accepted
- **Context:** Driving the real UI against the live API (not the mock) surfaced two
  contract mismatches. (1) `AuditReport.gate.critical_issues` is typed
  `list[str | GateIssue]` in `ega_schemas.scores.GateResult`, and `build_report`
  fills it with rich `GateIssue` objects, but the web declared `string[]` and
  rendered each item as a React child — throwing *"Objects are not valid as a
  React child"* and producing duplicate (`[object Object]`) keys. (2) The flat
  PRD §22 `scores` map includes an `AVR` entry shaped `{value, profile, warning}`
  (ADR-010) with no `score_key`/`weight`/`confidence`; the component grid fed it
  to `ScoreCard`, yielding an undefined key and an "undefined% weight" card.
- **Decision:** (1) Keep the `str | GateIssue` union on the wire (PRD §22 shows only
  empty arrays, so the element shape is unconstrained) and make the **client**
  tolerant: widen `GateResult.critical_issues`/`noncritical_issues` to
  `Array<string | GateIssue>` and render via a `gateIssueText()` helper with
  index-stable keys. (2) `AVR` is the weighted **composite**, not a component, so
  it is excluded from the component-score grid (it is already surfaced in the gate
  summary as "Composite X (AVR)"); the grid also falls back to the map key when an
  entry lacks a `score_key`.
- **Consequences:** The report page renders real API data with no crash, no
  duplicate-key warning and no missing-key warning; both gate-issue forms are
  covered by `apps/web/src/components/report/gate-summary.test.tsx`. Any future
  consumer iterating `report.scores` must ignore or specially handle `AVR`.

