/**
 * Deterministic in-memory mock of the FastAPI backend (NEXT_PUBLIC_MOCK=1).
 *
 * Everything here is sample data derived from the Northwind Roofing fixture.
 * Every mock-driven view must display the "Sample data — not a real audit"
 * banner; `SAMPLE_BANNER` is the single source of that copy.
 *
 * The mock simulates a *running* audit so the staged-progress timeline and the
 * SSE stream can be demonstrated without a backend: stage states are computed
 * from elapsed time since the run started (no timers are started at import, so
 * this module is safe to import in tests and during SSR).
 */

import { ApiError } from "@/lib/errors";
import type {
  AuditCreateRequest,
  AuditCreateResponse,
  AuditListRow,
  AuditRunDetail,
  AuditRunStatus,
  AuditStageEvent,
  AuditStatusEvent,
  AnalyzeDimension,
  AnalyzeRecommendation,
  AnalyzeRequest,
  AnalyzeResponse,
  BriefGenerateRequest,
  BriefResponse,
  BriefSection,
  BriefSourceItem,
  CompareResponse,
  ContextPackDetail,
  ContextPackSummary,
  ContentBriefPayload,
  ContentBriefResponse,
  ContentImportResponse,
  ExportFormat,
  Finding,
  HealthStatus,
  McpServerConfig,
  ProjectCreate,
  ProjectRead,
  ProviderInfo,
  ReadinessStatus,
  Scorecard,
  StageRecord,
  TestConnectionRequest,
  TestConnectionResponse,
  WorkspaceEntitiesResponse,
  WorkspaceEntity,
  WriterHandoff,
} from "@/lib/types";
import { NORTHWIND_DOCUMENT, NORTHWIND_REPORT } from "./northwind";

export const SAMPLE_BANNER = "Sample data — not a real audit";

/* ------------------------------------------------------------ stage plan */

interface StagePlanItem {
  node: string;
  label: string;
  origin: StageRecord["origin"];
  duration_ms: number;
  detail?: string;
  cached?: boolean;
  retries?: number;
}

const STAGE_PLAN: StagePlanItem[] = [
  { node: "ingest", label: "Parse & normalise content", origin: "deterministic", duration_ms: 900, detail: "Markdown parsed into 5 sections and 7 passages." },
  { node: "classify", label: "Classify page type & intent", origin: "deterministic", duration_ms: 700, detail: "local_service (confidence 0.82)" },
  { node: "context", label: "Load context packs", origin: "deterministic", duration_ms: 500, cached: true, detail: "northwind-brand-book@1.2.0 (cache hit)" },
  { node: "entities", label: "Extract entities", origin: "deterministic", duration_ms: 1200, detail: "8 entities, 1 central" },
  { node: "eav", label: "Build entity–attribute–value rows", origin: "deterministic", duration_ms: 900, detail: "6 rows (1 missing, 1 vague)" },
  { node: "fanout", label: "Simulate query fan-out", origin: "model_generated", duration_ms: 2000, detail: "18 simulated queries — labelled simulated in the report" },
  { node: "coverage", label: "Map coverage to passages", origin: "deterministic", duration_ms: 1100 },
  { node: "triples", label: "Extract semantic triples", origin: "model_generated", duration_ms: 1800, retries: 1, detail: "7 triples (1 unsupported, 1 missing)" },
  { node: "passage_audit", label: "Audit passage retrievability", origin: "deterministic", duration_ms: 1000 },
  { node: "claims", label: "Check claims & evidence", origin: "externally_verified", duration_ms: 900, detail: "WA registration verified against the official lookup" },
  { node: "scores", label: "Compute component scores", origin: "deterministic", duration_ms: 600 },
  { node: "gate", label: "Evaluate publication gate", origin: "deterministic", duration_ms: 400, detail: "pass_with_fixes" },
  { node: "report", label: "Assemble report", origin: "deterministic", duration_ms: 500 },
];

const RUN_DURATION_MS = STAGE_PLAN.reduce((sum, s) => sum + s.duration_ms, 0);

const nowIso = (): string => new Date().toISOString();

/* ------------------------------------------------------------- run store */

interface MockRun {
  audit_id: string;
  project_id: string;
  content_version_id: string | null;
  created_at: string;
  started_at: number;
  page_type: AuditListRow["page_type"];
  language: string;
  central_entity: string | null;
  primary_query: string | null;
  status: AuditRunStatus;
  gate_status: AuditListRow["gate_status"];
  composite: number | null;
  score_profile: string;
  provider_model: string;
  deterministic_only: boolean;
  depth: string;
  report: AuditRunDetail["report"];
  error: { code: string; message: string } | null;
  /** When true the report is intentionally absent (shows the empty state). */
  report_withheld?: boolean;
}

interface MockProject {
  project_id: string;
  name: string;
  slug: string;
  description: string | null;
  brand: string | null;
  base_url: string | null;
  languages: string[];
  country_region: string | null;
  industry: string | null;
  audience_icp: string | null;
  central_entity: string | null;
  target_conversion: string | null;
  model_profile: string;
  context_pack_ids: string[];
  archived: boolean;
  created_at: string;
  updated_at: string;
  audit_count: number;
}

const PROJECTS: MockProject[] = [
  {
    project_id: "proj-northwind",
    name: "Northwind Roofing",
    slug: "northwind-roofing",
    description: "Local roofing contractor, Bellingham WA — service and location pages.",
    brand: "Northwind Roofing",
    base_url: "https://northwindroofing.example",
    languages: ["en"],
    country_region: "US-WA",
    industry: "Home services",
    audience_icp: "Homeowners in Whatcom County, WA, 45–70, researching roof replacement",
    central_entity: "Northwind Roofing",
    target_conversion: "Book a free roof inspection",
    model_profile: "local_default",
    context_pack_ids: ["pack-northwind-brand"],
    archived: false,
    created_at: "2026-01-12T10:00:00Z",
    updated_at: "2026-02-14T09:12:44Z",
    audit_count: 3,
  },
  {
    project_id: "proj-cascade",
    name: "Cascade Dental Group",
    slug: "cascade-dental",
    description: "Multi-location dental practice — about and service pages.",
    brand: "Cascade Dental Group",
    base_url: "https://cascadedental.example",
    languages: ["en"],
    country_region: "US-OR",
    industry: "Healthcare",
    audience_icp: "Families in Portland, OR, comparing local dental providers",
    central_entity: "Cascade Dental Group",
    target_conversion: "Schedule an appointment",
    model_profile: "local_default",
    context_pack_ids: [],
    archived: false,
    created_at: "2026-02-01T09:30:00Z",
    updated_at: "2026-02-13T16:22:00Z",
    audit_count: 2,
  },
];

function seedRuns(): MockRun[] {
  const t = Date.now();
  const iso = (ms: number) => new Date(ms).toISOString();
  return [
    {
      audit_id: "aud-nw-live",
      project_id: "proj-northwind",
      content_version_id: "cv-northwind-001",
      created_at: iso(t),
      started_at: t,
      page_type: "local_service",
      language: "en",
      central_entity: "Northwind Roofing",
      primary_query: "roof replacement bellingham",
      status: "running",
      gate_status: null,
      composite: null,
      score_profile: "commercial_default@1.4",
      provider_model: "ollama / llama3.1:8b (local)",
      deterministic_only: false,
      depth: "standard",
      report: null,
      error: null,
    },
    {
      audit_id: "aud-nw-main",
      project_id: "proj-northwind",
      content_version_id: "cv-northwind-001",
      created_at: "2026-02-14T09:12:44Z",
      started_at: t - RUN_DURATION_MS,
      page_type: "local_service",
      language: "en",
      central_entity: "Northwind Roofing",
      primary_query: "roof replacement bellingham",
      status: "succeeded",
      gate_status: NORTHWIND_REPORT.gate.status,
      composite: NORTHWIND_REPORT.composite_avr ?? null,
      score_profile: "commercial_default@1.4",
      provider_model: "ollama / llama3.1:8b (local)",
      deterministic_only: false,
      depth: "standard",
      report: NORTHWIND_REPORT,
      error: null,
    },
    {
      audit_id: "aud-nw-baseline",
      project_id: "proj-northwind",
      content_version_id: "cv-northwind-000",
      created_at: "2026-01-20T11:03:10Z",
      started_at: t - RUN_DURATION_MS,
      page_type: "local_service",
      language: "en",
      central_entity: "Northwind Roofing",
      primary_query: "roof replacement bellingham",
      status: "succeeded",
      gate_status: "fail",
      composite: 6.3,
      score_profile: "commercial_default@1.3",
      provider_model: "dummy / deterministic",
      deterministic_only: true,
      depth: "standard",
      report: buildBaselineReport(),
      error: null,
    },
    {
      audit_id: "aud-cascade-01",
      project_id: "proj-cascade",
      content_version_id: null,
      created_at: "2026-02-13T16:22:00Z",
      started_at: t - RUN_DURATION_MS,
      page_type: "about",
      language: "en",
      central_entity: "Cascade Dental Group",
      primary_query: "dentist in portland or",
      status: "failed",
      gate_status: null,
      composite: null,
      score_profile: "commercial_default@1.4",
      provider_model: "openai / gpt-4o-mini",
      deterministic_only: false,
      depth: "deep",
      report: null,
      error: { code: "MODEL_TIMEOUT", message: "Provider timed out after 60 s while extracting triples. Re-run with a local model or a longer timeout." },
    },
    {
      audit_id: "aud-cascade-02",
      project_id: "proj-cascade",
      content_version_id: null,
      created_at: "2026-02-12T14:40:00Z",
      started_at: t - RUN_DURATION_MS,
      page_type: "saas_b2b",
      language: "en",
      central_entity: "Cascade Dental Group",
      primary_query: "dental practice software",
      status: "succeeded",
      gate_status: "pass",
      composite: 8.1,
      score_profile: "commercial_default@1.4",
      provider_model: "ollama / llama3.1:8b (local)",
      deterministic_only: false,
      depth: "standard",
      report: null,
      report_withheld: true,
      error: null,
    },
  ];
}

const RUNS: MockRun[] = seedRuns();

/* ------------------------------------------------------ baseline compare */

function buildBaselineReport() {
  const baseline = structuredClone(NORTHWIND_REPORT) as typeof NORTHWIND_REPORT;
  baseline.audit_metadata = {
    ...baseline.audit_metadata,
    run_id: "run-northwind-2026-01-20",
    created_at: "2026-01-20T11:03:10Z",
    score_profile_version: "1.3",
    provider_model: "dummy / deterministic",
    context_pack_versions: [],
    content_hash: "sha256:2b7e151628aed2a6abf7158809cf4f3c762af732ecfe9dc7593949d09daf8fdb",
  };
  baseline.gate = {
    status: "fail",
    critical_issues: [
      "Unsourced numeric claim (\u201cup to 40%\u201d) on a high-traffic commercial page.",
    ],
    noncritical_issues: [
      "Required contact_phone attribute is missing.",
      "Tenure claim is vague.",
      "No cost signal.",
    ],
  };
  const values: Record<string, number> = {
    EOS: 6.8,
    ERS: 6.2,
    KGR: 6.5,
    FCS: 5.4,
    PRS: 7.2,
    CWS: 4.9,
    HRS: 8.0,
  };
  for (const [key, value] of Object.entries(values)) {
    const component = baseline.scores[key];
    if (component) component.value = value;
  }
  baseline.composite_avr = 6.3;
  // The warranty and county entities were added between the two runs.
  baseline.entities = baseline.entities.filter(
    (entity) => entity.entity_id !== "ent-warranty" && entity.entity_id !== "ent-whatcom",
  );
  baseline.entities = baseline.entities.map((entity) =>
    entity.entity_id === "ent-northwind" ? { ...entity, salience: 0.9 } : entity,
  );
  // Baseline contained an extra finding that has since been resolved.
  const resolved: Finding = {
    finding_id: "fnd-gmb",
    category: "local_presence",
    severity: "medium",
    title: "No Google Business Profile link on the service page",
    what: "The page does not link to the business's Google Business Profile, weakening local entity verification.",
    where: { section_id: "sec-cta", passage_id: "p-cta-1", start_offset: null, end_offset: null, excerpt: "Call us or send the form below…" },
    why: { layer: "retrieval", entity: "Northwind Roofing", rule_id: "local.gbp.unlinked" },
    how: {
      suggested_rewrite: "See [our Google Business Profile](https://maps.example.com) for verified hours and reviews.",
      verification_condition: "The linked profile resolves and matches the NAP details on the page.",
      implementation_steps: ["Add a GBP link in the contact block"],
    },
    evidence: ["No outbound profile link found in the parsed document"],
    confidence: "medium",
    impact: 3,
    confidence_numeric: 3,
    effort: 1,
    priority_score: 9,
    status: "done",
  };
  baseline.recommendations = [...baseline.recommendations.filter((f) => f.finding_id !== "fnd-answer-first"), resolved];
  return baseline;
}

/* -------------------------------------------------------- context packs */

const CONTEXT_PACKS: Array<ContextPackDetail> = [
  {
    pack_id: "pack-northwind-brand",
    name: "Northwind brand book",
    version: "1.2.0",
    version_hash: "b1946ac92492d234",
    description: "Brand voice rules, canonical facts, banned terms and the service-area topical map for Northwind Roofing.",
    created_at: "2026-01-12T10:05:00Z",
    files: [
      { path: "manifest.json", size_bytes: 1240, role: "manifest" },
      { path: "brand_rules.md", size_bytes: 4820, role: "rules" },
      { path: "canonical_facts.json", size_bytes: 2210, role: "facts" },
      { path: "banned_terms.csv", size_bytes: 410, role: "terms" },
      { path: "topical_map.csv", size_bytes: 1980, role: "map" },
    ],
    warnings: [
      "brand_rules.md uses two different spellings of \u201cLabor & Industries\u201d; the canonical fact value was used.",
      "canonical_facts.json has no verification source for the founding-year fact.",
    ],
    conflicts: [
      "canonical_facts.json says founding year 2008; brand_rules.md says \u201csince 2006\u201d. Audits use the canonical fact (2008) and flag the page copy if it disagrees.",
      "banned_terms.csv forbids the phrase \u201cbest roofer\u201d, but topical_map.csv targets the topic \u201cbest roofer in Bellingham\u201d.",
    ],
    counts: {
      brand_rules: 6,
      canonical_facts: 5,
      approved_claims: 3,
      banned_terms: 4,
      topical_map: 9,
      internal_links: 7,
    },
    brand_rules: [
      { rule_id: "br-1", rule_type: "brand_voice", statement: "Use plain, factual language. Never claim to be the \u201cbest\u201d; state verifiable proof instead.", severity: "high" },
      { rule_id: "br-2", rule_type: "naming", statement: "First mention on a page must use the full name \u201cNorthwind Roofing\u201d.", severity: "medium" },
      { rule_id: "br-3", rule_type: "compliance", statement: "Never publish warranty or licensing statements without the identifier from canonical facts.", severity: "critical" },
    ],
    canonical_facts: [
      { fact_id: "cf-1", entity: "Northwind Roofing", attribute: "founding_year", canonical_value: "2008", verification_source: "WA business registration" },
      { fact_id: "cf-2", entity: "Northwind Roofing", attribute: "phone", canonical_value: "(360) 555-0142", verification_source: "GBP listing" },
      { fact_id: "cf-3", entity: "Northwind Roofing", attribute: "licence", canonical_value: "WA L&I registration on file", verification_source: "L&I lookup" },
    ],
    approved_claims: [
      { claim_id: "ac-1", approved_statement: "Family-owned since 2008.", required_citations: ["cf-1"] },
      { claim_id: "ac-2", approved_statement: "Two-year workmanship warranty on every installation.", required_citations: [] },
    ],
    banned_terms: [
      { term: "best roofer", reason: "Unverifiable superlative", suggested_replacement: "roofing contractor serving Whatcom County" },
      { term: "guaranteed no leaks", reason: "Absolute warranty claim", suggested_replacement: "warranty-backed workmanship" },
    ],
    topical_map: [
      { topic: "Roof replacement", primary_entity: "Northwind Roofing", intent: "commercial", target_url: "/services/replacement" },
      { topic: "Roof repair", primary_entity: "Northwind Roofing", intent: "transactional", target_url: "/services/repair" },
    ],
    internal_links: [
      { anchor_phrase: "roof financing options", target_url: "/services/financing", entity: "Northwind Roofing" },
    ],
  },
];

/* -------------------------------------------------------------- catalog */

const PROVIDERS: ProviderInfo[] = [
  {
    id: "dummy",
    type: "dummy",
    label: "Deterministic baseline (offline)",
    requires_api_key: false,
    local: true,
    structured_output: true,
    sends_data_off_device: false,
    description:
      "Rule-based, deterministic analysis with zero external dependencies. Semantic stages that require a model are skipped and recorded as skipped.",
    cost_warning: null,
  },
  {
    id: "ollama",
    type: "ollama",
    label: "Ollama (self-hosted)",
    requires_api_key: false,
    local: true,
    structured_output: true,
    sends_data_off_device: false,
    description:
      "Local open-weights models (Llama 3, Mistral, Qwen, DeepSeek) via a local Ollama server. Content never leaves this machine.",
    cost_warning: null,
  },
  {
    id: "openai",
    type: "openai",
    label: "OpenAI / OpenAI-compatible (BYOK)",
    requires_api_key: true,
    local: false,
    structured_output: true,
    sends_data_off_device: true,
    description:
      "GPT-4o and any OpenAI-compatible endpoint (vLLM, LocalAI, LM Studio, Groq, Together). Bring your own key.",
    cost_warning:
      "Cloud provider: audited page text is sent to this provider and usage is billed to your account.",
  },
  {
    id: "anthropic",
    type: "anthropic",
    label: "Anthropic",
    requires_api_key: true,
    local: false,
    structured_output: true,
    sends_data_off_device: true,
    description: "Claude models for semantic extraction, fan-out simulation and claim checking.",
    cost_warning:
      "Cloud provider: audited page text is sent to Anthropic and usage is billed to your account.",
  },
  {
    id: "gemini",
    type: "gemini",
    label: "Google Gemini",
    requires_api_key: true,
    local: false,
    structured_output: true,
    sends_data_off_device: true,
    description: "Gemini models for semantic extraction, fan-out simulation and claim checking.",
    cost_warning:
      "Cloud provider: audited page text is sent to Google and usage is billed to your account.",
  },
];

/* ------------------------------------------------------------- helpers */

const findRun = (auditId: string): MockRun => {
  const run = RUNS.find((r) => r.audit_id === auditId);
  if (!run) throw new ApiError("AUDIT_NOT_FOUND", `Audit ${auditId} not found.`, 404);
  return run;
};

/** Stage states for a running audit, computed from elapsed wall time. */
function liveStages(run: MockRun, now: number): StageRecord[] {
  const elapsed = now - run.started_at;
  let cursor = 0;
  return STAGE_PLAN.map((plan) => {
    const start = cursor;
    const end = start + plan.duration_ms;
    cursor = end;
    const base: StageRecord = {
      node: plan.node,
      label: plan.label,
      status: "pending",
      origin: plan.origin,
      retries: plan.retries ?? 0,
      cached: plan.cached ?? false,
      detail: plan.detail ?? null,
      started_at: null,
      finished_at: null,
      duration_ms: null,
      error: null,
      attempts: 0,
      tokens_estimated: null,
    };
    if (elapsed < start) return { ...base, status: "pending" };
    if (elapsed < end) {
      return {
        ...base,
        status: "running",
        started_at: new Date(run.started_at + start).toISOString(),
        attempts: 1 + (plan.retries ?? 0),
      };
    }
    const duration = plan.duration_ms + (plan.retries ?? 0) * 420;
    return {
      ...base,
      status: plan.cached ? "cached" : "succeeded",
      duration_ms: duration,
      started_at: new Date(run.started_at + start).toISOString(),
      finished_at: new Date(run.started_at + start + duration).toISOString(),
      attempts: 1 + (plan.retries ?? 0),
      tokens_estimated: plan.origin === "model_generated" ? duration * 3 : null,
    };
  });
}

function staticStages(run: MockRun): StageRecord[] {
  if (run.status === "succeeded") {
    return STAGE_PLAN.map((plan) => ({
      node: plan.node,
      label: plan.label,
      status: plan.cached ? "cached" : "succeeded",
      origin: plan.origin,
      retries: plan.retries ?? 0,
      cached: plan.cached ?? false,
      detail: plan.detail ?? null,
      duration_ms: plan.duration_ms,
      started_at: null,
      finished_at: null,
      error: null,
      attempts: 1 + (plan.retries ?? 0),
      tokens_estimated: null,
    }));
  }
  if (run.status === "failed") {
    return STAGE_PLAN.map((plan, index) => {
      const failed = plan.node === "triples";
      const done = index < STAGE_PLAN.findIndex((p) => p.node === "triples");
      return {
        node: plan.node,
        label: plan.label,
        status: failed ? "failed" : done ? "succeeded" : "pending",
        origin: plan.origin,
        retries: failed ? 2 : 0,
        cached: false,
        detail: failed ? "Provider timed out after 60 s" : plan.detail ?? null,
        duration_ms: done ? plan.duration_ms : null,
        started_at: null,
        finished_at: null,
        error: failed ? "MODEL_TIMEOUT" : null,
        attempts: failed ? 3 : done ? 1 : 0,
        tokens_estimated: null,
      } satisfies StageRecord;
    });
  }
  return [];
}

function runDetail(run: MockRun): AuditRunDetail {
  const now = Date.now();
  const inFlight = run.status === "queued" || run.status === "running";
  const stages = inFlight ? liveStages(run, now) : staticStages(run);
  const completedStages = stages.filter((s) =>
    ["succeeded", "skipped", "cached"].includes(s.status),
  ).length;
  const elapsed = now - run.started_at;
  const status: AuditRunStatus = inFlight
    ? elapsed <= 200
      ? "queued"
      : elapsed >= RUN_DURATION_MS
        ? "succeeded"
        : "running"
    : run.status;
  const finished = !inFlight || elapsed >= RUN_DURATION_MS;
  return {
    audit_id: run.audit_id,
    status,
    created_at: run.created_at,
    completed_at: finished ? new Date(run.started_at + RUN_DURATION_MS).toISOString() : null,
    duration_ms: finished ? RUN_DURATION_MS : null,
    page_type: run.page_type,
    gate_status: finished ? (run.gate_status ?? run.report?.gate.status ?? null) : null,
    composite: finished ? (run.composite ?? run.report?.composite_avr ?? null) : null,
    provider_model: run.provider_model,
    deterministic_only: run.deterministic_only,
    error: run.error,
    progress: { stages, completed: completedStages, total: stages.length },
    report: finished && !run.report_withheld ? run.report : null,
  };
}

/* ------------------------------------------------------- mock handlers */

export const mock = {
  async health(): Promise<HealthStatus> {
    return { status: "ok", version: "0.1.0 (mock)" };
  },

  async readiness(): Promise<ReadinessStatus> {
    return {
      status: "ready",
      checks: { database: "ok", provider: "mock", context_packs: "ok" },
    };
  },

  /* ---------------------------------------------------------- projects */

  async listProjects(): Promise<ProjectRead[]> {
    return PROJECTS.map((p) => ({ ...p }));
  },

  async getProject(projectId: string): Promise<ProjectRead> {
    const project = PROJECTS.find((p) => p.project_id === projectId);
    if (!project) throw new ApiError("PROJECT_NOT_FOUND", `Project ${projectId} not found.`, 404);
    return { ...project };
  },

  async createProject(payload: ProjectCreate): Promise<ProjectRead> {
    const slug =
      payload.slug ??
      payload.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/(^-|-$)/g, "");
    const created: MockProject = {
      project_id: `proj-${slug}-${PROJECTS.length + 1}`,
      name: payload.name,
      slug,
      description: payload.description ?? null,
      brand: payload.brand ?? payload.site_profile?.brand_entity ?? payload.name,
      base_url:
        payload.base_url ??
        (payload.site_profile ? `https://${payload.site_profile.canonical_domain}` : null),
      languages:
        payload.languages ?? [payload.site_profile?.primary_locale ?? "en"],
      country_region: payload.country_region ?? null,
      industry: payload.industry ?? null,
      audience_icp: payload.audience_icp ?? null,
      central_entity:
        payload.central_entity ?? payload.site_profile?.brand_entity ?? payload.name,
      target_conversion: payload.target_conversion ?? null,
      model_profile: payload.model_profile ?? "local_default",
      context_pack_ids: payload.context_pack_ids ?? [],
      archived: payload.archived ?? false,
      created_at: nowIso(),
      updated_at: nowIso(),
      audit_count: 0,
    };
    PROJECTS.unshift(created);
    return { ...created };
  },

  /* ----------------------------------------------------------- content */

  async importContent(input: {
    text?: string;
    format?: string;
    filename?: string;
    file?: File;
  }): Promise<ContentImportResponse> {
    const text = input.text ?? "";
    if (!text.trim() && !input.file) {
      throw new ApiError("EMPTY_CONTENT", "Provide non-empty text or a file.", 422);
    }
    const headings = (text.match(/^#{1,6}\s+.+$/gm) ?? []).length;
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;
    const warnings: string[] = [];
    if (words < 120) warnings.push("Content is very short; most scores will be low-confidence.");
    if (headings === 0) warnings.push("No headings detected; passage structure may be shallow.");
    return {
      content_version_id: `cv-${Math.random().toString(36).slice(2, 10)}`,
      content_hash: `sha256:${words.toString(16)}${headings.toString(16)}`,
      document_summary: {
        word_count: words,
        headings,
        language_hint: "en",
        warnings,
        extraction_notes: [
          input.file
            ? `Parsed upload "${input.file.name}" with the deterministic parser.`
            : "Parsed pasted text with the deterministic markdown parser.",
          "Tables and code blocks are preserved as atomic passages.",
        ],
        suggested_page_type: words > 400 ? "local_service" : null,
        page_type_confidence: words > 400 ? 0.82 : null,
        page_type_rationale:
          words > 400
            ? "Service vocabulary plus a named locality and a single conversion goal."
            : null,
      },
    };
  },

  async fetchUrl(payload: { url: string }) {
    const url = payload.url.trim();
    if (/localhost|127\.0\.0\.1|10\.|192\.168\.|metadata/i.test(url)) {
      throw new ApiError(
        "FETCH_BLOCKED",
        "The URL resolves to a private or loopback address. Private-network fetches are blocked by default (SSRF protection).",
        400,
      );
    }
    if (/timeout/i.test(url)) {
      throw new ApiError("FETCH_TIMEOUT", "The host did not respond within the fetch timeout.", 400);
    }
    return {
      content_version_id: `cv-${Math.random().toString(36).slice(2, 10)}`,
      url,
      final_url: url,
      http_status: 200,
      content_type: "text/html; charset=utf-8",
      fetched_at: nowIso(),
      canonical_url: url.replace(/\?.*$/, ""),
      robots: "allowed",
      limitations: [
        "JavaScript-rendered content is not executed; DOM text after hydration may be missing.",
        "Only the primary content region is extracted — navigation and footer text are dropped.",
        "Images, PDFs and page speed are not analysed by this fetch.",
      ],
      document_summary: {
        word_count: 0,
        headings: 0,
        language_hint: "en",
        warnings: ["Sample fetch: the mock does not retrieve real page content."],
        extraction_notes: ["Fetched HTML would be parsed deterministically into sections and passages."],
      },
    };
  },

  /* ------------------------------------------------------ context packs */

  async listContextPacks(): Promise<ContextPackSummary[]> {
    return CONTEXT_PACKS.map((pack) => ({
      pack_id: pack.pack_id,
      name: pack.name,
      version: pack.version,
      version_hash: pack.version_hash,
      description: pack.description,
      created_at: pack.created_at,
      files: pack.files,
      warnings: pack.warnings,
      conflicts: pack.conflicts,
      counts: pack.counts,
    }));
  },

  async getContextPack(packId: string): Promise<ContextPackDetail> {
    const pack = CONTEXT_PACKS.find((p) => p.pack_id === packId);
    if (!pack) throw new ApiError("PACK_NOT_FOUND", `Context pack ${packId} not found.`, 404);
    return structuredClone(pack);
  },

  async importContextPack(file: File): Promise<ContextPackSummary> {
    if (!/\.(zip|tar\.gz|tgz)$/i.test(file.name)) {
      throw new ApiError(
        "UNSUPPORTED_ARCHIVE",
        "Context packs must be a .zip or .tar.gz archive.",
        422,
      );
    }
    const pack: ContextPackDetail = {
      pack_id: `pack-${Math.random().toString(36).slice(2, 8)}`,
      name: file.name.replace(/\.(zip|tar\.gz|tgz)$/i, ""),
      version: "1.0.0",
      version_hash: Math.random().toString(16).slice(2, 18),
      description: "Imported archive (sample).",
      created_at: nowIso(),
      files: [{ path: "manifest.json", size_bytes: file.size, role: "manifest" }],
      warnings: ["Imported archive was not fully parsed in sample mode."],
      conflicts: [],
      counts: { brand_rules: 0, canonical_facts: 0, approved_claims: 0, banned_terms: 0, topical_map: 0, internal_links: 0 },
      brand_rules: [],
      canonical_facts: [],
      approved_claims: [],
      banned_terms: [],
      topical_map: [],
      internal_links: [],
    };
    CONTEXT_PACKS.unshift(pack);
    return mock.listContextPacks().then((packs) => packs[0]);
  },

  /* ------------------------------------------------------------ audits */

  async listAudits(filters?: { project_id?: string; status?: string }): Promise<AuditListRow[]> {
    const rows = RUNS.map((run) => {
      const detail = runDetail(run);
      return {
        audit_id: run.audit_id,
        project_id: run.project_id,
        content_version_id: run.content_version_id,
        created_at: run.created_at,
        completed_at: detail.completed_at,
        page_type: run.page_type,
        language: run.language,
        central_entity: run.central_entity,
        primary_query: run.primary_query,
        status: detail.status,
        gate_status: detail.gate_status ?? null,
        composite: detail.composite ?? null,
        score_profile: run.score_profile,
        provider_model: run.provider_model,
        deterministic_only: run.deterministic_only,
        depth: run.depth,
        error: run.error,
      } satisfies AuditListRow;
    });
    return rows
      .filter((row) => (filters?.project_id ? row.project_id === filters.project_id : true))
      .filter((row) => (filters?.status ? row.status === filters.status : true))
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  },

  async getAudit(auditId: string): Promise<AuditRunDetail> {
    return runDetail(findRun(auditId));
  },

  async createAudit(request: AuditCreateRequest): Promise<AuditCreateResponse> {
    const auditId = `aud-${Math.random().toString(36).slice(2, 10)}`;
    const started = Date.now();
    RUNS.unshift({
      audit_id: auditId,
      project_id: request.project_id,
      content_version_id: request.content_version_id ?? null,
      created_at: new Date(started).toISOString(),
      started_at: started,
      page_type: request.page_type ?? "general",
      language: request.language ?? "en",
      central_entity: null,
      primary_query: request.primary_query ?? null,
      status: "running",
      gate_status: null,
      composite: null,
      score_profile: request.score_profile ?? "commercial_default@1.4",
      provider_model: "ollama / llama3.1:8b (local)",
      deterministic_only: request.source_profile === "offline",
      depth: request.depth ?? "standard",
      report: NORTHWIND_REPORT,
      error: null,
    });
    return { audit_id: auditId, status: "queued" };
  },

  /** Simulated SSE stream: emits stage transitions then the terminal status. */
  subscribeAuditEvents(
    auditId: string,
    onStage: (event: AuditStageEvent) => void,
    onStatus: (event: AuditStatusEvent) => void,
    onError?: (error: Error) => void,
  ): () => void {
    let run: MockRun;
    try {
      run = findRun(auditId);
    } catch (error) {
      onError?.(error as Error);
      return () => {};
    }
    const emitted = new Set<string>();
    let lastStatus = "";
    const tick = () => {
      try {
        const detail = runDetail(run);
        detail.progress.stages.forEach((stage) => {
          const key = `${stage.node}:${stage.status}`;
          if (emitted.has(key)) return;
          emitted.add(key);
          onStage({
            type: "stage",
            node: stage.node,
            label: stage.label,
            status: stage.status,
            origin: stage.origin,
            detail: stage.detail,
            at: nowIso(),
          });
        });
        if (detail.status !== lastStatus) {
          lastStatus = detail.status;
          onStatus({ type: "status", status: detail.status, gate: detail.gate_status, at: nowIso() });
        }
        if (detail.status === "succeeded" || detail.status === "failed") {
          clearInterval(interval);
        }
      } catch (error) {
        clearInterval(interval);
        onError?.(error as Error);
      }
    };
    const interval = setInterval(tick, 400);
    tick();
    return () => clearInterval(interval);
  },

  async getAuditEntities(auditId: string) {
    return reportOf(auditId).entities;
  },
  async getAuditTriples(auditId: string) {
    return reportOf(auditId).triples;
  },
  async getAuditFanout(auditId: string) {
    return reportOf(auditId).fanout;
  },
  async getAuditFindings(auditId: string) {
    const report = reportOf(auditId);
    return report.recommendations ?? report.passage_findings ?? [];
  },
  async getAuditScores(auditId: string): Promise<Scorecard> {
    const report = reportOf(auditId);
    return {
      scores: report.scores,
      gate: report.gate,
      avr: report.composite_avr ?? null,
      profile_name: report.audit_metadata.score_profile_version,
      confidence: "medium",
      warning:
        "Internal editorial heuristic — not an official Google, Bing, OpenAI, Anthropic, or Perplexity metric.",
    };
  },

  async compareAudits(baselineId: string, candidateId: string): Promise<CompareResponse> {
    const baseline = reportOf(baselineId);
    const candidate = reportOf(candidateId);

    const keys = Array.from(
      new Set([...Object.keys(baseline.scores), ...Object.keys(candidate.scores)]),
    );
    const score_delta = keys.map((key) => {
      const base = baseline.scores[key]?.value ?? null;
      const cand = candidate.scores[key]?.value ?? null;
      return {
        key,
        baseline: base,
        candidate: cand,
        delta: base !== null && cand !== null ? Math.round((cand - base) * 10) / 10 : null,
      };
    });

    const baseEntities = new Map(baseline.entities.map((e) => [e.canonical_name, e]));
    const candEntities = new Map(candidate.entities.map((e) => [e.canonical_name, e]));
    const added = Array.from(candEntities.keys()).filter((n) => !baseEntities.has(n));
    const removed = Array.from(baseEntities.keys()).filter((n) => !candEntities.has(n));
    const changed = Array.from(candEntities.keys()).filter((n) => {
      const base = baseEntities.get(n);
      const cand = candEntities.get(n);
      return (
        base !== undefined &&
        cand !== undefined &&
        (base.kind !== cand.kind || Math.abs(base.salience - cand.salience) > 0.05)
      );
    });

    const rank: Record<string, number> = {
      missing: 0,
      conflicting: 1,
      unverified: 1.5,
      vague: 2,
      explicit: 3,
    };
    const eavKey = (row: { entity_name: string; attribute: string }) =>
      `${row.entity_name} · ${row.attribute}`;
    const baseEav = new Map(
      baseline.eav_rows
        .filter((r) => r.status !== "not_applicable")
        .map((r) => [eavKey(r), r.status]),
    );
    const eav_improved: string[] = [];
    const eav_regressed: string[] = [];
    for (const row of candidate.eav_rows) {
      if (row.status === "not_applicable") continue;
      const before = baseEav.get(eavKey(row));
      if (before === undefined) continue;
      if (rank[row.status] > rank[before]) eav_improved.push(eavKey(row));
      if (rank[row.status] < rank[before]) eav_regressed.push(eavKey(row));
    }

    const covered = (report: typeof baseline) =>
      report.coverage_rows.filter((r) => r.status === "covered" || r.status === "partial").length;

    const baseFindingIds = new Set(baseline.recommendations.map((f) => f.finding_id));
    const candFindingIds = new Set(candidate.recommendations.map((f) => f.finding_id));

    const warnings: string[] = [];
    if (
      baseline.audit_metadata.score_profile_version !==
      candidate.audit_metadata.score_profile_version
    ) {
      warnings.push(
        `Score profile versions differ (${baseline.audit_metadata.score_profile_version} → ${candidate.audit_metadata.score_profile_version}). Score deltas may reflect changed weights, not changed content.`,
      );
    }
    if (baseline.audit_metadata.provider_model !== candidate.audit_metadata.provider_model) {
      warnings.push(
        `Provider/model changed (${baseline.audit_metadata.provider_model} → ${candidate.audit_metadata.provider_model}). Model-generated stages are not like-for-like.`,
      );
    }
    const basePacks = baseline.audit_metadata.context_pack_versions.join(", ") || "none";
    const candPacks = candidate.audit_metadata.context_pack_versions.join(", ") || "none";
    if (basePacks !== candPacks) {
      warnings.push(
        `Context pack versions differ (${basePacks} → ${candPacks}). Canonical facts and brand rules may have changed.`,
      );
    }
    if (baseline.audit_metadata.content_hash !== candidate.audit_metadata.content_hash) {
      warnings.push("The audited content differs between the two runs (different content hashes).");
    }
    if (!warnings.length) {
      warnings.push("Runs share profile, model and pack versions — deltas are like-for-like.");
    }

    return {
      score_delta,
      entity_changes: { added, removed, changed },
      eav_improved,
      eav_regressed,
      coverage_delta: {
        baseline_covered: covered(baseline),
        candidate_covered: covered(candidate),
        total: candidate.coverage_rows.length,
      },
      new_findings: candidate.recommendations.filter((f) => !baseFindingIds.has(f.finding_id)),
      resolved_findings: baseline.recommendations.filter((f) => !candFindingIds.has(f.finding_id)),
      warnings,
    };
  },

  async writerHandoff(auditId: string): Promise<WriterHandoff> {
    const report = reportOf(auditId);
    const top = [...report.recommendations].sort((a, b) => b.priority_score - a.priority_score);
    const lines = [
      `# Writer brief — ${report.audit_metadata.central_entity || "page"}`,
      "",
      `**Gate:** ${report.gate.status.replace(/_/g, " ")}`,
      `**Primary query:** ${report.audit_metadata.primary_intent} · ${report.audit_metadata.page_type.replace(/_/g, " ")}`,
      `**Composite AVR:** ${report.composite_avr ?? "—"} (heuristic, internal)`,
      "",
      "## Top actions",
      ...top.slice(0, 4).map(
        (f, index) =>
          `${index + 1}. **${f.title}** — ${f.what}${f.how?.suggested_rewrite ? `\n   Suggested rewrite: “${f.how.suggested_rewrite}”` : ""}`,
      ),
      "",
      "## Voice & lexicon",
      "- Use the full legal name on first mention.",
      "- Prefer verifiable proof (dates, identifiers, counts) over superlatives.",
    ];
    return {
      brief_markdown: lines.join("\n"),
      actions: top.map((f) => ({
        finding_id: f.finding_id,
        title: f.title,
        suggested_rewrite: f.how?.suggested_rewrite ?? null,
      })),
      lexicon: {
        include: ["family-owned since 2008", "two-year workmanship warranty", "free roof inspection"],
        replace: ["many years → since 2008", "best roofer → roofing contractor serving Whatcom County"],
        avoid: ["best roofer", "guaranteed no leaks", "#1"],
      },
    };
  },

  async exportAudit(auditId: string, format: ExportFormat): Promise<{ blob: Blob; filename: string }> {
    const report = reportOf(auditId);
    const slug = (report.audit_metadata.central_entity || "audit")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-");
    if (format === "json") {
      return {
        blob: new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
        filename: `${slug}-audit.json`,
      };
    }
    if (format === "html") {
      const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Audit report — ${report.audit_metadata.central_entity}</title></head><body><h1>Audit report — ${report.audit_metadata.central_entity}</h1><p>Gate: ${report.gate.status.replace(/_/g, " ")}</p><p>Composite AVR: ${report.composite_avr ?? "—"}</p></body></html>`;
      return { blob: new Blob([html], { type: "text/html" }), filename: `${slug}-audit.html` };
    }
    if (format === "csv") {
      const rows = [
        ["score_key", "value", "weight", "confidence", "lost_points"],
        ...Object.values(report.scores).map((s) => [
          s.score_key,
          String(s.value),
          String(s.weight),
          s.confidence,
          s.lost_points_reasons.join(" | "),
        ]),
      ];
      const csv = rows
        .map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(","))
        .join("\n");
      return { blob: new Blob([csv], { type: "text/csv" }), filename: `${slug}-scores.csv` };
    }
    const md = [
      `# Audit report — ${report.audit_metadata.central_entity}`,
      "",
      `Gate: ${report.gate.status.replace(/_/g, " ")}`,
      `Composite AVR: ${report.composite_avr ?? "—"} (internal heuristic)`,
      "",
      "## Component scores",
      ...Object.values(report.scores).map(
        (s) => `- **${s.score_key}** ${s.value.toFixed(1)}/10 (${s.weight}% weight, ${s.confidence} confidence): ${s.rationale}`,
      ),
      "",
      "## Gate issues",
      ...report.gate.critical_issues.map((i) => `- CRITICAL: ${i}`),
      ...report.gate.noncritical_issues.map((i) => `- ${i}`),
      "",
      "## Recommendations",
      ...report.recommendations.map((f) => `### ${f.title}\n\n${f.what}\n\n${f.how?.suggested_rewrite ?? ""}`),
    ].join("\n");
    return { blob: new Blob([md], { type: "text/markdown" }), filename: `${slug}-audit.md` };
  },

  /* ---------------------------------------------------------- providers */

  async listProviders(): Promise<{ providers: ProviderInfo[] }> {
    return { providers: PROVIDERS.map((p) => ({ ...p })) };
  },

  async testConnection(payload: TestConnectionRequest): Promise<TestConnectionResponse> {
    await new Promise((resolve) => setTimeout(resolve, 350));
    const isLocal = payload.provider_type === "ollama" || payload.provider_type === "dummy";
    if (!isLocal && !payload.api_key) {
      return {
        ok: false,
        latency_ms: 0,
        status: "error",
        detail: "No API key supplied for this provider.",
      };
    }
    return {
      ok: true,
      latency_ms: isLocal ? 38 : 214,
      status: "connected",
      provider: payload.provider_type,
      model_name: payload.model,
      detail: isLocal
        ? `Local provider responded in ${38} ms.`
        : `Provider authenticated and responded in ${214} ms.`,
    };
  },

  /* ---------------------------------------------------------------- mcp */

  async listMcpServers(): Promise<McpServerConfig[]> {
    return [];
  },

  /* --------------------------------------------------------- deletion */

  async deleteAudit(auditId: string): Promise<{ deleted: boolean }> {
    findRun(auditId);
    const index = RUNS.findIndex((r) => r.audit_id === auditId);
    RUNS.splice(index, 1);
    return { deleted: true };
  },

  /* ---------------------------------------------------------- workspace */

  async listEntities(projectId: string): Promise<WorkspaceEntitiesResponse> {
    const slug = (value: string) =>
      value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    const kindMap: Record<string, string> = {
      organization: "Organization",
      brand: "Organization",
      competitor: "Organization",
      product_service: "Service",
      platform: "Platform",
      tool: "Platform",
      person: "Person",
      location: "Place",
    };
    const runs = RUNS.filter((r) => r.project_id === projectId && r.report);
    const registry = new Map<string, WorkspaceEntity>();
    for (const run of runs) {
      const report = run.report;
      if (!report) continue;
      const short = run.audit_id.slice(0, 8);
      for (const entity of report.entities) {
        const key = entity.canonical_name.toLowerCase();
        const existing = registry.get(key);
        const rec: WorkspaceEntity =
          existing ??
          {
            entity_id: `ent-${slug(entity.canonical_name)}`,
            canonical_id: `#${slug(entity.canonical_name)}`,
            name: entity.canonical_name,
            kind: kindMap[entity.kind] ?? "Concept",
            entity_kind: entity.kind,
            aliases: [],
            pages_used: 0,
            facts_count: 0,
            last_verified: null,
            status: "healthy",
            conflict_detail: null,
            definition:
              report.audit_metadata.central_entity === entity.canonical_name
                ? "Central entity of the audited content."
                : "Candidate entity extracted from audited content.",
            at_id: `#${slug(entity.canonical_name)}`,
            schema_type: "schema.org/Thing",
            facts: [],
            sources: [],
            origins: ["audit"],
          };
        rec.pages_used += 1;
        rec.aliases = Array.from(new Set([...rec.aliases, ...entity.aliases]));
        if (!rec.sources.some((s) => s.title === `Audit ${short}`)) {
          rec.sources.push({ title: `Audit ${short}` });
        }
        registry.set(key, rec);
      }
      for (const row of report.eav_rows) {
        if (!row.value) continue;
        const rec = registry.get(row.entity_name.toLowerCase());
        if (!rec) continue;
        if (!rec.facts.some((f) => f.property === row.attribute && f.value === row.value)) {
          rec.facts.push({
            property: row.attribute,
            value: row.value,
            source: `Audit ${short}`,
            date: null,
            verified: row.status === "explicit",
          });
        }
        rec.facts_count = rec.facts.length;
      }
    }
    const entities = Array.from(registry.values()).sort(
      (a, b) => b.pages_used - a.pages_used || a.name.localeCompare(b.name),
    );
    return {
      project_id: projectId,
      entities,
      generated_at: nowIso(),
      source_audits: runs.length,
      source_packs: CONTEXT_PACKS.length,
      disclaimer: `${SAMPLE_BANNER}. Entity registry derived from the fixture audits.`,
    };
  },

  async generateBrief(payload: BriefGenerateRequest): Promise<BriefResponse> {
    const run =
      (payload.audit_id && RUNS.find((r) => r.audit_id === payload.audit_id)) ||
      RUNS.find((r) => r.project_id === payload.project_id && r.report);
    const report = run?.report ?? null;
    const sources: BriefSourceItem[] = [];
    const packFacts: string[] = [];
    if (report) {
      const short = run?.audit_id.slice(0, 8) ?? "audit";
      for (const q of report.fanout) {
        sources.push({
          id: `q-${q.query_id}`,
          kind: "question",
          title: q.query_text,
          source: "Coverage query (fan-out)",
          tag: q.importance >= 3 ? "Core intent" : "Follow-up",
          provenance: `audit:${short}`,
        });
      }
      for (const f of report.recommendations) {
        sources.push({
          id: `f-${f.finding_id}`,
          kind: "gap",
          title: f.title,
          source: "Audit finding",
          tag: f.category,
          provenance: `audit:${short}`,
        });
      }
      for (const c of report.claims) {
        sources.push({
          id: `c-${c.claim_id}`,
          kind: "fact",
          title: c.statement,
          source: "Audit claim",
          tag: c.risk_tier,
          provenance: `audit:${short}`,
        });
      }
    }
    for (const pack of CONTEXT_PACKS) {
      for (const fact of pack.canonical_facts ?? []) {
        const label = `${fact.attribute}: ${fact.canonical_value}`;
        packFacts.push(label);
        sources.push({
          id: `p-${pack.pack_id}-${fact.fact_id}`,
          kind: "fact",
          title: label,
          source: `Context pack · ${pack.name}`,
          tag: "Verified fact",
          provenance: `pack:${pack.pack_id}@${pack.version}`,
        });
      }
    }
    const questions = sources.filter((s) => s.kind === "question").slice(0, payload.max_sections ?? 6);
    const targetEntities = (report?.entities ?? []).map((e) => ({
      name: e.canonical_name,
      kind: e.kind,
    }));
    const sections: BriefSection[] = questions.map((q, index) => ({
      id: `sec-${index + 1}`,
      h2_number: index + 1,
      title: q.title.charAt(0).toUpperCase() + q.title.slice(1),
      badge: "Answer",
      entities: targetEntities.slice(0, 2),
      facts: packFacts.slice(0, 2),
      directive: `Answer “${q.title}” directly in the first two sentences, then expand with entity-specific evidence.`,
      word_range: "150–250 words",
    }));
    return {
      project_id: payload.project_id,
      target_query:
        payload.target_query ||
        report?.audit_metadata.primary_query ||
        report?.audit_metadata.central_entity ||
        "Untitled brief",
      sources,
      sections,
      constraints: {
        audience: null,
        tone: null,
        reading_level: "Grade 8–10 (Flesch-Kincaid)",
        intent: report?.audit_metadata.primary_intent ?? null,
      },
      information_gain: CONTEXT_PACKS.flatMap((p) =>
        (p.brand_rules ?? []).map((r) => ({ directive: r.statement, polarity: "do" as const })),
      ),
      basis: {
        audit_id: run?.audit_id ?? null,
        audit_created_at: run ? new Date(run.started_at).toISOString() : null,
        context_pack_ids: CONTEXT_PACKS.map((p) => p.pack_id),
        context_pack_versions: CONTEXT_PACKS.map((p) => `${p.pack_id}@${p.version}`),
      },
      generated_at: nowIso(),
      disclaimer: `${SAMPLE_BANNER}. Deterministic brief assembled from the fixture data.`,
    };
  },

  async analyzeContent(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
    const text = payload.text ?? "";
    const body = text.replace(/^#{1,6}\s+.*$/gm, "");
    const words = body.match(/[A-Za-z0-9'’\-]+/g) ?? [];
    const sentences = body.split(/[.!?]+(?:\s|$)/).filter((s) => s.trim());
    const headings = Array.from(
      text.matchAll(/^(#{1,6})\s+(.*\S)\s*$/gm),
    ).map((m) => {
      const title = m[2].trim();
      return {
        level: m[1].length,
        text: title,
        is_question:
          title.endsWith("?") ||
          /^(how|what|why|when|where|who|which|can|does|do|is|are|should)\b/i.test(title),
      };
    });
    const lower = text.toLowerCase();
    const entities = (payload.target_entities ?? []).map((name) => {
      const count = (lower.match(new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi")) ?? []).length;
      return {
        name,
        count,
        expected: true,
        status: (count === 0 ? "missing" : count === 1 ? "thin" : "ok") as "ok" | "thin" | "missing",
      };
    });
    const violations = (payload.banned_terms ?? [])
      .map((term) => ({
        term,
        count: (lower.match(new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi")) ?? []).length,
      }))
      .filter((v) => v.count > 0);
    const syllables = words.reduce((sum, w) => {
      const m = w.toLowerCase().match(/[aeiouy]+/g);
      return sum + Math.max(1, m ? m.length : 1);
    }, 0) || 1;
    const wps = words.length / Math.max(1, sentences.length);
    const spw = syllables / Math.max(1, words.length);
    const readingEase = Math.round((206.835 - 1.015 * wps - 84.6 * spw) * 10) / 10;
    const fk = Math.round((0.39 * wps + 11.8 * spw - 15.59) * 10) / 10;
    const wordTarget = payload.word_target ?? 900;
    const entitiesScore = entities.length
      ? Math.round(
          (100 * (entities.filter((e) => e.status === "ok").length + 0.5 * entities.filter((e) => e.status === "thin").length)) /
            entities.length,
        )
      : 100;
    const questionHeadings = headings.filter((h) => h.is_question).length;
    const answerScore = Math.min(100, 40 + (wps <= 24 ? 20 : 0) + (questionHeadings ? 20 : 0) + (words.length / wordTarget >= 0.6 ? 20 : 0));
    const evidenceScore = violations.length ? Math.max(15, 100 - 40 * violations.length) : 100;
    const h2 = headings.filter((h) => h.level === 2).length;
    const passagesScore = Math.min(100, Math.max(20, Math.round(30 + 40 * Math.min(1, h2 / 4) + (questionHeadings ? 20 : 0))));
    const originalityScore = Math.min(100, Math.max(30, Math.round(60 + 40 * Math.min(1, words.length / wordTarget))));
    const band = (score: number) => (score >= 75 ? "strong" : score >= 50 ? "fair" : "weak") as "weak" | "fair" | "strong";
    const dimensions: AnalyzeDimension[] = [
      { key: "entities", label: "Entities", score: entitiesScore, band: band(entitiesScore), note: `${entities.length} target entity(ies)` },
      { key: "answers", label: "Answers", score: answerScore, band: band(answerScore), note: `${questionHeadings} question heading(s)` },
      { key: "evidence", label: "Evidence", score: evidenceScore, band: band(evidenceScore), note: `${violations.length} banned-term hit(s)` },
      { key: "passages", label: "Passages", score: passagesScore, band: band(passagesScore), note: `${h2} H2 section(s)` },
      { key: "originality", label: "Originality", score: originalityScore, band: band(originalityScore), note: `${words.length} words vs ${wordTarget} target` },
    ];
    const recommendations: AnalyzeRecommendation[] = [];
    if (!questionHeadings) {
      recommendations.push({ id: "add_question_heading", title: "Add a question-shaped heading", detail: "No heading is phrased as a question.", dimension: "answers", impact: "high", action: "Rewrite one H2 as a real audience question." });
    }
    const missing = entities.filter((e) => e.status === "missing").map((e) => e.name);
    if (missing.length) {
      recommendations.push({ id: "add_missing_entities", title: "Cover missing target entities", detail: `Not mentioned: ${missing.join(", ")}`, dimension: "entities", impact: "high", action: "Introduce and define the missing entities." });
    }
    for (const v of violations) {
      recommendations.push({ id: `banned_${v.term}`, title: `Remove banned term “${v.term}”`, detail: `Appears ${v.count}x.`, dimension: "evidence", impact: "high", action: "Replace with an objective statement." });
    }
    return {
      metrics: {
        word_count: words.length,
        sentence_count: Math.max(1, sentences.length),
        paragraph_count: body.split(/\n\s*\n/).filter((p) => p.trim()).length,
        reading_time_minutes: words.length ? Math.max(1, Math.round(words.length / 220)) : 0,
        reading_ease: readingEase,
        flesch_kincaid_grade: fk,
      },
      headings,
      entities,
      violations,
      dimensions,
      recommendations,
      overall_score: Math.round(dimensions.reduce((s, d) => s + d.score, 0) / dimensions.length),
      disclaimer: `${SAMPLE_BANNER}. Internal editorial heuristic — deterministic analysis of the submitted text; not a search-engine ranking.`,
    };
  },

  async generateContentBrief(payload: ContentBriefPayload): Promise<ContentBriefResponse> {
    const query = (payload.target_query || "content opportunity").trim();
    const q = query.toLowerCase();
    const brand = payload.brand_name ?? "Your brand";
    const loc = payload.location ?? "your market";
    const pack = payload.context_pack_id
      ? CONTEXT_PACKS.find((p) => p.pack_id === payload.context_pack_id)
      : CONTEXT_PACKS[0];

    const packFacts = (pack?.canonical_facts ?? []).map(
      (f) => `${f.attribute.replace(/_/g, " ")}: ${f.canonical_value}`,
    );
    const grounded = packFacts.length > 0;
    const factAt = (i: number) =>
      packFacts[i] ??
      "No verified fact in the active context pack — add a canonical fact to ground this source";

    // Sources are query-derived patterns and real pack facts — never a
    // People-Also-Ask / Perplexity / AI-engine lookup, and the labels say so.
    const sources: ContentBriefResponse["sources"] = [
      {
        id: "src-pricing",
        type: "question",
        title: `How much should an organization pay for ${q}?`,
        source: "Query pattern · Pricing",
        tag: "High intent",
        tagColor: "bg-primary-soft text-primary",
      },
      {
        id: "src-fact",
        type: "fact",
        title: packFacts[0] ?? `Standard starting tiers for ${loc}`,
        source: grounded ? "Context pack · canonical fact" : "Unverified placeholder",
        tag: grounded ? "Verified fact" : "Needs grounding",
        tagColor: "bg-emerald-50 text-emerald-800 border border-emerald-200",
      },
      {
        id: "src-gap",
        type: "gap",
        title: `Milestone tracking vs retainer burn mechanics in ${q}`,
        source: "Coverage gap · derived",
        tag: "Coverage gap",
        tagColor: "bg-surface-subtle text-muted-foreground",
      },
      {
        id: "src-diff",
        type: "question",
        title: `What is the difference between general providers and specialized ${q}?`,
        source: "Query pattern · Differentiation",
        tag: "Core intent",
        tagColor: "bg-indigo-50 text-indigo-700",
      },
    ];

    const namedQuery = query.charAt(0).toUpperCase() + query.slice(1);
    const entityRefs = [
      { name: brand, type: "Organization" },
      { name: namedQuery, type: "Service" },
      { name: loc, type: "Place" },
    ];
    const packRules = (pack?.brand_rules ?? []).map((r) => r.statement);
    const ruleFacts = packRules.length
      ? packRules.slice(0, 2)
      : ["No brand-rule fact in the active context pack"];

    const sections: ContentBriefResponse["sections"] = [
      {
        id: "sec-1",
        h2Number: 1,
        title: `Why Modern Organizations Require Dedicated ${namedQuery}`,
        badge: "Answer",
        badgeColor: "bg-emerald-50 text-emerald-800",
        entities: entityRefs,
        facts: [factAt(0)],
        directive: `Open with an answer-first definition: clearly state that ${brand} delivers structured ${q} tailored for operations in ${loc}. Explicitly answer what the service is and who it is for in the first 2 sentences.`,
        wordRange: "120–180 words",
      },
      {
        id: "sec-2",
        h2Number: 2,
        title: `Transparent Pricing & Retainer Structure for ${namedQuery}`,
        badge: "Pricing",
        badgeColor: "bg-amber-50 text-amber-800",
        entities: [entityRefs[2]],
        facts: [factAt(1)],
        directive:
          "State the pricing model and exactly what is included. Use canonical fee facts verbatim and explain billing cadence.",
        wordRange: "150–220 words",
      },
      {
        id: "sec-3",
        h2Number: 3,
        title: "How the Engagement Actually Works: Process & Cadence",
        badge: "Mechanism",
        badgeColor: "bg-indigo-50 text-indigo-700",
        entities: [entityRefs[0]],
        facts: [factAt(2)],
        directive:
          "Walk through the operating process step by step so a buyer can picture the first 30 days.",
        wordRange: "200–280 words",
      },
      {
        id: "sec-4",
        h2Number: 4,
        title: "Proof, Standards & Credentials",
        badge: "Authority",
        badgeColor: "bg-surface-subtle text-foreground",
        entities: [entityRefs[0]],
        facts: ruleFacts,
        directive:
          "Cite verified credentials and approved claims only; every statement needs a canonical source.",
        wordRange: "160–240 words",
      },
    ];

    const intent = /\b(best|top|vs\.?|versus|review|alternatives|compare)\b/.test(q)
      ? "Commercial / Advisory"
      : /\b(price|pricing|cost|hire|quote|buy|per month|service|agency|consultant|near me)\b/.test(q)
        ? "Commercial / Transactional"
        : "Informational / Educational";

    const include = [q];
    for (const f of packFacts) {
      const head = f.split(":")[0].trim().toLowerCase();
      if (head && head.length <= 40 && !include.includes(head)) include.push(head);
    }

    return {
      target_query: query,
      page_type: payload.page_type ?? "service",
      brand_name: brand,
      location: loc,
      intent,
      recommended_word_count: "900–1,400 words",
      reading_level: "Grade 10–12 (Technical/Professional)",
      grounded,
      disclaimer: `${SAMPLE_BANNER}. Internal editorial heuristic. Sections and sources are deterministic templates derived from the target query and the active context pack; no external search or AI-engine lookup was performed.`,
      sources,
      sections,
      lexicon: {
        include: include.slice(0, 6),
        replace: [
          { from: "industry-leading", to: "specialized and verified" },
          { from: "best in class", to: "standard-compliant" },
          { from: "world-class", to: "documented process" },
        ],
        avoid: (pack?.banned_terms ?? []).map((b) => b.term),
      },
    };
  },

  async deleteProject(projectId: string): Promise<{ deleted: boolean }> {
    const index = PROJECTS.findIndex((p) => p.project_id === projectId);
    if (index === -1) throw new ApiError("PROJECT_NOT_FOUND", `Project ${projectId} not found.`, 404);
    PROJECTS.splice(index, 1);
    return { deleted: true };
  },
};

function reportOf(auditId: string) {
  const detail = runDetail(findRun(auditId));
  if (!detail.report) {
    throw new ApiError(
      "REPORT_NOT_READY",
      detail.error?.message ?? "The report is not available for this audit yet.",
      409,
    );
  }
  return detail.report;
}

export { NORTHWIND_DOCUMENT, NORTHWIND_REPORT };
