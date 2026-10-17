/**
 * Hand-written TypeScript mirror of the backend Pydantic contract.
 *
 * Source of truth: `packages/schemas/ega_schemas/*.py` (enums.py, report.py,
 * scores.py, entities.py, triples.py, fanout.py, findings.py, claims.py,
 * project.py, content.py, context_packs.py, run.py, providers.py).
 *
 * Enum members are modelled as string-literal unions plus a `const` array so
 * that both exhaustive typing and runtime iteration (selects, filters, tables)
 * are available. Field names match the JSON wire format exactly.
 */

/* ------------------------------------------------------------------ enums */

export const PAGE_TYPES = [
  "homepage",
  "about",
  "service",
  "local_service",
  "article",
  "glossary",
  "listicle",
  "comparison",
  "case_study",
  "saas_b2b",
  "integration",
  "paid_landing",
  "product_category",
  "trust_policy",
  "docs",
  "general",
] as const;
export type PageType = (typeof PAGE_TYPES)[number];
export const PAGE_TYPE_LABELS: Record<PageType, string> = {
  homepage: "Homepage",
  about: "About",
  service: "Service",
  local_service: "Local service",
  article: "Article",
  glossary: "Glossary",
  listicle: "Listicle",
  comparison: "Comparison",
  case_study: "Case study",
  saas_b2b: "B2B / SaaS",
  integration: "Integration",
  paid_landing: "Paid landing",
  product_category: "Product category",
  trust_policy: "Trust / policy",
  docs: "Documentation",
  general: "General",
};

export const INTENT_CLASSES = [
  "informational",
  "commercial",
  "transactional",
  "navigational",
  "local",
  "comparison",
  "evaluation",
  "research",
] as const;
export type IntentClass = (typeof INTENT_CLASSES)[number];
export const INTENT_LABELS: Record<IntentClass, string> = {
  informational: "Informational",
  commercial: "Commercial",
  transactional: "Transactional",
  navigational: "Navigational",
  local: "Local",
  comparison: "Comparison",
  evaluation: "Evaluation",
  research: "Research",
};

export const ANSWER_SHAPES = [
  "definition",
  "checklist",
  "procedure",
  "shortlist",
  "table",
  "comparison_verdict",
  "pricing_fact",
  "risk_explanation",
  "proof_block",
  "cta",
] as const;
export type AnswerShape = (typeof ANSWER_SHAPES)[number];
export const ANSWER_SHAPE_LABELS: Record<AnswerShape, string> = {
  definition: "Definition",
  checklist: "Checklist",
  procedure: "Procedure",
  shortlist: "Shortlist",
  table: "Table",
  comparison_verdict: "Comparison verdict",
  pricing_fact: "Pricing fact",
  risk_explanation: "Risk explanation",
  proof_block: "Proof block",
  cta: "Call to action",
};

export const ENTITY_KINDS = [
  "central",
  "brand",
  "organization",
  "product_service",
  "person",
  "location",
  "concept",
  "problem",
  "outcome",
  "process",
  "tool",
  "material",
  "audience",
  "use_case",
  "platform",
  "competitor",
  "metric",
  "price",
  "date",
  "standard",
  "regulation",
  "proof",
  "cta",
  "other",
] as const;
export type EntityKind = (typeof ENTITY_KINDS)[number];
export const ENTITY_KIND_LABELS: Record<EntityKind, string> = {
  central: "Central",
  brand: "Brand",
  organization: "Organization",
  product_service: "Product / service",
  person: "Person",
  location: "Location",
  concept: "Concept",
  problem: "Problem",
  outcome: "Outcome",
  process: "Process",
  tool: "Tool",
  material: "Material",
  audience: "Audience",
  use_case: "Use case",
  platform: "Platform",
  competitor: "Competitor",
  metric: "Metric",
  price: "Price",
  date: "Date",
  standard: "Standard",
  regulation: "Regulation",
  proof: "Proof",
  cta: "Call to action",
  other: "Other",
};

export const EXTRACTION_METHODS = [
  "deterministic",
  "dictionary",
  "ner_local",
  "llm",
  "merged",
] as const;
export type ExtractionMethod = (typeof EXTRACTION_METHODS)[number];
export const EXTRACTION_METHOD_LABELS: Record<ExtractionMethod, string> = {
  deterministic: "Deterministic",
  dictionary: "Dictionary",
  ner_local: "Local NER",
  llm: "Model",
  merged: "Merged",
};

export const EAV_STATUSES = [
  "explicit",
  "vague",
  "missing",
  "conflicting",
  "unverified",
  "not_applicable",
] as const;
export type EAVStatus = (typeof EAV_STATUSES)[number];
export const EAV_STATUS_LABELS: Record<EAVStatus, string> = {
  explicit: "Explicit",
  vague: "Vague",
  missing: "Missing",
  conflicting: "Conflicting",
  unverified: "Unverified",
  not_applicable: "Not applicable",
};

export const TRIPLE_STATUSES = [
  "explicit",
  "implied",
  "missing",
  "wrong",
  "unsupported",
] as const;
export type TripleStatus = (typeof TRIPLE_STATUSES)[number];
export const TRIPLE_STATUS_LABELS: Record<TripleStatus, string> = {
  explicit: "Explicit",
  implied: "Implied",
  missing: "Missing",
  wrong: "Wrong",
  unsupported: "Unsupported",
};

export const TRIPLE_TYPES = [
  "category",
  "capability",
  "audience",
  "geography",
  "process",
  "outcome",
  "price",
  "integration",
  "authority",
  "comparison",
  "requirement",
  "safety_compliance",
  "cause_effect",
  "other",
] as const;
export type TripleType = (typeof TRIPLE_TYPES)[number];
export const TRIPLE_TYPE_LABELS: Record<TripleType, string> = {
  category: "Category",
  capability: "Capability",
  audience: "Audience",
  geography: "Geography",
  process: "Process",
  outcome: "Outcome",
  price: "Price",
  integration: "Integration",
  authority: "Authority",
  comparison: "Comparison",
  requirement: "Requirement",
  safety_compliance: "Safety / compliance",
  cause_effect: "Cause & effect",
  other: "Other",
};

export const EVIDENCE_LABELS = [
  "official",
  "measured_study",
  "first_party",
  "practitioner",
  "analytical_inference",
  "speculative",
  "unverified",
] as const;
export type EvidenceLabel = (typeof EVIDENCE_LABELS)[number];
export const EVIDENCE_LABEL_LABELS: Record<EvidenceLabel, string> = {
  official: "Official",
  measured_study: "Measured study",
  first_party: "First party",
  practitioner: "Practitioner",
  analytical_inference: "Analytical inference",
  speculative: "Speculative",
  unverified: "Unverified",
};

export const CLAIM_RISK_TIERS = ["ordinary", "high_stakes", "regulated"] as const;
export type ClaimRiskTier = (typeof CLAIM_RISK_TIERS)[number];
export const CLAIM_RISK_TIER_LABELS: Record<ClaimRiskTier, string> = {
  ordinary: "Ordinary",
  high_stakes: "High stakes",
  regulated: "Regulated",
};

export const VERIFICATION_STATES = [
  "verified",
  "unverified",
  "conflicting",
  "not_assessed",
] as const;
export type VerificationState = (typeof VERIFICATION_STATES)[number];
export const VERIFICATION_STATE_LABELS: Record<VerificationState, string> = {
  verified: "Verified",
  unverified: "Unverified",
  conflicting: "Conflicting",
  not_assessed: "Not assessed",
};

export const GATE_STATUSES = [
  "pass",
  "pass_with_fixes",
  "fail",
  "not_configured",
  "not_assessed",
] as const;
export type GateStatus = (typeof GATE_STATUSES)[number];
export const GATE_STATUS_LABELS: Record<GateStatus, string> = {
  pass: "Pass",
  pass_with_fixes: "Pass with fixes",
  fail: "Fail — not publishable as-is",
  not_configured: "Not configured",
  not_assessed: "Not assessed",
};

export const SEVERITIES = ["critical", "high", "medium", "low", "info"] as const;
export type Severity = (typeof SEVERITIES)[number];
export const SEVERITY_LABELS: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

export const CONFIDENCES = ["high", "medium", "low", "not_assessed"] as const;
export type Confidence = (typeof CONFIDENCES)[number];
export const CONFIDENCE_LABELS: Record<Confidence, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
  not_assessed: "Not assessed",
};

export const QUERY_ORIGINS = ["observed", "simulated"] as const;
export type QueryOrigin = (typeof QUERY_ORIGINS)[number];

export const QUERY_SOURCES = [
  "gsc",
  "bing",
  "serp_paa",
  "user_brief",
  "competitor",
  "topical_map",
  "generated_hypothesis",
  "other",
] as const;
export type QuerySource = (typeof QUERY_SOURCES)[number];
export const QUERY_SOURCE_LABELS: Record<QuerySource, string> = {
  gsc: "Google Search Console",
  bing: "Bing Webmaster Tools",
  serp_paa: "SERP People-Also-Ask",
  user_brief: "User brief",
  competitor: "Competitor gap",
  topical_map: "Topical map",
  generated_hypothesis: "Generated hypothesis",
  other: "Other",
};

export const QUERY_SCOPES = ["this_page", "sibling_page", "out_of_scope"] as const;
export type QueryScope = (typeof QUERY_SCOPES)[number];
export const QUERY_SCOPE_LABELS: Record<QueryScope, string> = {
  this_page: "This page",
  sibling_page: "Sibling page",
  out_of_scope: "Out of scope",
};

export const COVERAGE_STATUSES = ["covered", "partial", "missing", "excluded"] as const;
export type CoverageStatus = (typeof COVERAGE_STATUSES)[number];
export const COVERAGE_STATUS_LABELS: Record<CoverageStatus, string> = {
  covered: "Covered",
  partial: "Partial",
  missing: "Missing",
  excluded: "Excluded (out of scope)",
};

export const RECOMMENDATION_STATUSES = ["open", "in_progress", "done", "dismissed"] as const;
export type RecommendationStatus = (typeof RECOMMENDATION_STATUSES)[number];
export const RECOMMENDATION_STATUS_LABELS: Record<RecommendationStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  done: "Done",
  dismissed: "Dismissed",
};

export const RESULT_ORIGINS = ["deterministic", "model_generated", "externally_verified"] as const;
export type ResultOrigin = (typeof RESULT_ORIGINS)[number];
export const RESULT_ORIGIN_LABELS: Record<ResultOrigin, string> = {
  deterministic: "Deterministic",
  model_generated: "Model generated",
  externally_verified: "Externally verified",
};

export const STAGE_STATUSES = [
  "pending",
  "running",
  "succeeded",
  "failed",
  "skipped",
  "cached",
] as const;
export type StageStatus = (typeof STAGE_STATUSES)[number];
export const STAGE_STATUS_LABELS: Record<StageStatus, string> = {
  pending: "Pending",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  skipped: "Skipped",
  cached: "Cached",
};

export const AUDIT_DEPTHS = ["quick", "standard", "deep"] as const;
export type AuditDepth = (typeof AUDIT_DEPTHS)[number];
export const AUDIT_DEPTH_LABELS: Record<AuditDepth, string> = {
  quick: "Quick",
  standard: "Standard",
  deep: "Deep",
};

export const SOURCE_PROFILES = [
  "offline",
  "local_web_search",
  "user_supplied_sources",
  "connected_data",
] as const;
export type SourceProfile = (typeof SOURCE_PROFILES)[number];
export const SOURCE_PROFILE_LABELS: Record<SourceProfile, string> = {
  offline: "Offline only",
  local_web_search: "Local web search",
  user_supplied_sources: "User-supplied sources",
  connected_data: "Connected data",
};

export const SENSITIVITY_TIERS = ["ordinary", "high_stakes", "regulated"] as const;
export type SensitivityTier = (typeof SENSITIVITY_TIERS)[number];
export const SENSITIVITY_TIER_LABELS: Record<SensitivityTier, string> = {
  ordinary: "Ordinary",
  high_stakes: "High stakes (health, finance, safety)",
  regulated: "Regulated (legal, medical, financial advice)",
};

export const SCORE_KEYS = [
  "EOS",
  "ERS",
  "KGR",
  "FCS",
  "PRS",
  "CWS",
  "HRS",
  "AVR",
  "INTENT",
  "LOCAL_FIT",
  "PAID_FIT",
  "CONVERSION",
  "TRUST",
  "LINKS",
] as const;
export type ScoreKey = (typeof SCORE_KEYS)[number];

export const CORE_SCORE_KEYS: readonly ScoreKey[] = [
  "EOS",
  "ERS",
  "KGR",
  "FCS",
  "PRS",
  "CWS",
  "HRS",
] as const;

export const SCORE_LABELS: Record<ScoreKey, string> = {
  EOS: "Entity Optimization Score",
  ERS: "Entity Relationship Score",
  KGR: "Knowledge-Graph Readiness",
  FCS: "Fan-out Coverage Score",
  PRS: "Passage Retrievability Score",
  CWS: "Citation-Worthiness / Information Gain",
  HRS: "Human Readability & Utility",
  AVR: "Composite AI Visibility Readiness",
  INTENT: "Intent Alignment",
  LOCAL_FIT: "Local Fit",
  PAID_FIT: "Paid Landing Page Fit",
  CONVERSION: "Conversion Readiness",
  TRUST: "Trust / E-E-A-T Coverage",
  LINKS: "Internal-Link Readiness",
};

export const SCORE_ABBREVIATIONS: Record<ScoreKey, string> = {
  EOS: "Entity focus, attributes and intent fit",
  ERS: "Clarity and accuracy of entity relationships",
  KGR: "Explicit triples and knowledge-graph consistency",
  FCS: "Weighted coverage of in-scope fan-out queries",
  PRS: "Extractability of standalone, answer-first passages",
  CWS: "Original information and verifiable sourcing",
  HRS: "Clarity, structure and practical completeness",
  AVR: "Weighted composite of applicable components",
  INTENT: "Fit between page content and primary intent",
  LOCAL_FIT: "Local relevance for location-targeted pages",
  PAID_FIT: "Fit for paid landing-page requirements",
  CONVERSION: "Clarity of the next step for the target action",
  TRUST: "Evidence, authorship and E-E-A-T signals",
  LINKS: "Internal-link readiness and anchor quality",
};

export const MODEL_PROVIDER_TYPES = ["dummy", "ollama", "openai", "anthropic", "gemini"] as const;
export type ModelProviderType = (typeof MODEL_PROVIDER_TYPES)[number];

/* --------------------------------------------------------------- structure */

export interface HealthStatus {
  status: string;
  version: string;
}

export interface ReadinessStatus {
  status: string;
  checks: Record<string, string>;
}

export interface ApiErrorShape {
  code: string;
  message: string;
  trace_id: string | null;
}

/* ---------------------------------------------------------------- projects */

export interface SiteProfile {
  site_name: string;
  canonical_domain: string;
  brand_entity: string;
  primary_locale: string;
  description?: string | null;
  social_profiles: string[];
}

export interface ProjectCreate {
  name: string;
  /* Flat fields accepted by apps/api (ega_schemas.project.ProjectCreate). */
  brand?: string | null;
  base_url?: string | null;
  languages?: string[];
  country_region?: string | null;
  target_market?: string | null;
  industry?: string | null;
  audience_icp?: string | null;
  central_entity?: string | null;
  target_conversion?: string | null;
  model_profile?: string;
  context_pack_ids?: string[];
  source_connectors?: string[];
  archived?: boolean;
  /* Tolerated extras (older contract / nested site profile). */
  slug?: string | null;
  description?: string | null;
  site_profile?: SiteProfile | null;
}

export interface ProjectRead {
  project_id: string;
  name: string;
  slug: string;
  description?: string | null;
  site_profile?: SiteProfile | null;
  /* Flat fields currently emitted by the API (apps/api routes/projects.py). */
  brand?: string | null;
  base_url?: string | null;
  languages?: string[];
  country_region?: string | null;
  target_market?: string | null;
  industry?: string | null;
  audience_icp?: string | null;
  central_entity?: string | null;
  target_conversion?: string | null;
  model_profile?: string | null;
  context_pack_ids?: string[];
  source_connectors?: string[];
  archived?: boolean;
  audit_count?: number;
  created_at: string;
  updated_at: string;
}

/* ----------------------------------------------------------------- content */

export interface DocumentSummary {
  word_count: number;
  headings: number;
  language_hint: string;
  warnings: string[];
  extraction_notes: string[];
  /* Additional fields emitted by the API import summary. */
  title?: string | null;
  sections?: number;
  passages?: number;
  canonical_url?: string | null;
  suggested_page_type?: PageType | null;
  page_type_confidence?: number | null;
  page_type_rationale?: string | null;
  content_hash?: string | null;
}

export interface ContentImportResponse {
  content_version_id: string;
  document_summary: DocumentSummary;
  content_hash?: string;
}

export interface ContentImportJson {
  text: string;
  format: "markdown" | "html" | "text";
  filename?: string;
}

export interface FetchUrlRequest {
  url: string;
}

export interface FetchUrlResponse {
  content_version_id?: string;
  http_status: number;
  fetched_at: string;
  canonical_url: string;
  limitations: string[];
  /* Additional fields emitted by the API fetch endpoint. */
  url?: string;
  final_url?: string;
  content_type?: string;
  robots?: string | boolean;
  document_summary?: DocumentSummary;
}

/* ----------------------------------------------------------- context packs */

export interface ContextPackFile {
  path: string;
  size_bytes: number;
  role: string;
}

export interface ContextPackSummary {
  pack_id: string;
  name: string;
  version: string;
  version_hash: string;
  description?: string;
  created_at?: string;
  imported_at?: string;
  source_file?: string | null;
  scope?: string;
  document_count?: number;
  rule_count?: number;
  files: Array<ContextPackFile | string>;
  warnings: string[];
  conflicts: string[];
  counts?: {
    brand_rules: number;
    canonical_facts: number;
    approved_claims: number;
    banned_terms: number;
    topical_map: number;
    internal_links: number;
  };
}

export interface BrandRule {
  rule_id: string;
  rule_type: string;
  statement: string;
  severity: Severity;
}

export interface CanonicalFact {
  fact_id: string;
  entity: string;
  attribute: string;
  canonical_value: string;
  verification_source?: string | null;
}

export interface ApprovedClaim {
  claim_id: string;
  approved_statement: string;
  required_citations: string[];
}

export interface BannedTerm {
  term: string;
  reason: string;
  suggested_replacement?: string | null;
}

export interface TopicalMapRow {
  topic: string;
  primary_entity: string;
  intent: IntentClass;
  target_url?: string | null;
}

export interface InternalLinkTarget {
  anchor_phrase: string;
  target_url: string;
  entity: string;
}

export interface ContextPackDetail extends ContextPackSummary {
  brand_rules: BrandRule[];
  canonical_facts: CanonicalFact[];
  approved_claims: ApprovedClaim[];
  banned_terms: BannedTerm[];
  topical_map: TopicalMapRow[];
  internal_links: InternalLinkTarget[];
}

/* ------------------------------------------------------------------- audit */

export interface AuditCreateRequest {
  project_id: string;
  content_version_id?: string | null;
  content_text?: string | null;
  content_url?: string | null;
  page_type?: PageType | null;
  primary_query?: string | null;
  secondary_queries?: string[];
  audience_icp?: string | null;
  location_target?: string | null;
  conversion_goal?: string | null;
  page_url?: string | null;
  competitor_urls?: string[];
  lifecycle?: string;
  target_platforms?: string[];
  sensitivity?: SensitivityTier;
  source_profile?: SourceProfile;
  context_pack_ids?: string[];
  score_profile?: string | null;
  depth?: AuditDepth;
  content_format?: string;
  language?: string | null;
  disable_cache?: boolean;
}

export interface AuditCreateResponse {
  audit_id: string;
  status: "queued";
}

export type AuditRunStatus = "queued" | "running" | "succeeded" | "failed";

export interface AuditListRow {
  audit_id: string;
  project_id: string;
  created_at: string;
  page_type: PageType;
  status: AuditRunStatus;
  gate_status: GateStatus | null;
  composite: number | null;
  central_entity: string | null;
  primary_query: string | null;
  /* Extra summary columns emitted by the API list endpoint. */
  content_version_id?: string | null;
  completed_at?: string | null;
  language?: string | null;
  score_profile?: string | null;
  provider_model?: string | null;
  deterministic_only?: boolean;
  depth?: AuditDepth | string | null;
  error?: { code: string; message: string } | string | null;
}

export interface StageRecord {
  node: string;
  label: string;
  status: StageStatus;
  origin: ResultOrigin;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  retries: number;
  attempts?: number;
  error?: string | null;
  detail?: string | null;
  cached?: boolean;
  tokens_estimated?: number | null;
}

export interface AuditProgress {
  stages: StageRecord[];
  completed: number;
  total: number;
}

export interface AuditRunDetail {
  audit_id?: string;
  status: AuditRunStatus;
  progress: AuditProgress;
  report: AuditReport | null;
  error: { code: string; message: string } | null;
  /* Summary columns emitted by the API. */
  created_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  page_type?: PageType | null;
  gate_status?: GateStatus | null;
  composite?: number | null;
  provider_model?: string | null;
  deterministic_only?: boolean;
}

export interface AuditStageEvent {
  type?: "stage";
  node: string;
  label?: string;
  status: StageStatus;
  origin: ResultOrigin;
  detail?: string | null;
  at: string;
}

export interface AuditStatusEvent {
  type: "status";
  status: AuditRunStatus;
  gate?: GateStatus | null;
  error?: string | null;
  at: string;
}

/* ------------------------------------------------------------------ report */

export interface AuditMetadata {
  project_id: string;
  run_id: string;
  page_type: PageType;
  language: string;
  central_entity: string;
  primary_intent: IntentClass;
  primary_query?: string | null;
  created_at: string;
  content_hash: string;
  score_profile_version: string;
  provider_model: string;
  context_pack_versions: string[];
  assumptions: string[];
  warnings: string[];
  /** True when this run used only deterministic (zero-API) providers. */
  deterministic_only?: boolean;
}

export interface SwotAnalysis {
  strengths: string[];
  weaknesses: string[];
  opportunities: string[];
  threats: string[];
}

export interface ComponentScore {
  score_key: ScoreKey;
  value: number;
  weight: number;
  confidence: Confidence;
  rationale: string;
  sub_scores: Record<string, number>;
  lost_points_reasons: string[];
  observed_queries?: number | null;
  simulated_queries?: number | null;
}

export interface GateIssue {
  category?: string;
  severity?: string;
  message?: string;
  rule_id?: string | null;
  issue_id?: string | null;
  title?: string | null;
  detail?: string | null;
}

export interface GateResult {
  status: GateStatus;
  /* The API emits `list[str | GateIssue]`; older/mock payloads use plain strings. */
  critical_issues: Array<string | GateIssue>;
  noncritical_issues: Array<string | GateIssue>;
}

export interface Scorecard {
  scores: Record<string, ComponentScore>;
  gate: GateResult;
  avr?: number | null;
  profile_name: string;
  confidence: Confidence;
  warning: string;
}

export interface EntityOccurrence {
  passage_id: string;
  start_offset: number;
  end_offset: number;
  sentence: string;
}

export interface Entity {
  entity_id: string;
  canonical_name: string;
  kind: EntityKind;
  confidence: Confidence;
  salience: number;
  occurrences: EntityOccurrence[];
  aliases: string[];
  is_central: boolean;
  method: ExtractionMethod;
  wikidata_id?: string | null;
}

export interface EAVRow {
  eav_id: string;
  entity_name: string;
  attribute: string;
  value?: string | null;
  status: EAVStatus;
  evidence_excerpt?: string | null;
  passage_id?: string | null;
  confidence: Confidence;
  notes?: string | null;
  is_required_by_page_type: boolean;
}

export interface SemanticTriple {
  triple_id: string;
  subject: string;
  predicate: string;
  object_: string;
  triple_type: TripleType;
  status: TripleStatus;
  evidence_excerpt?: string | null;
  passage_id?: string | null;
  confidence: Confidence;
  notes?: string | null;
}

export interface FanoutQuery {
  query_id: string;
  query_text: string;
  origin: QueryOrigin;
  source: QuerySource;
  intent: IntentClass;
  importance: 1 | 2 | 3;
  answer_shape: AnswerShape;
  scope: QueryScope;
}

export interface CoverageRow {
  query_id: string;
  query_text: string;
  status: CoverageStatus;
  matched_passage_ids: string[];
  coverage_score: number;
  gap_reason?: string | null;
  destination_page?: string | null;
}

export interface FindingWhere {
  section_id?: string | null;
  passage_id?: string | null;
  start_offset?: number | null;
  end_offset?: number | null;
  excerpt?: string | null;
}

export interface FindingWhy {
  intent_or_query?: string | null;
  layer?: string | null;
  entity?: string | null;
  attribute?: string | null;
  eav_status?: string | null;
  rule_id?: string | null;
}

export interface FindingHow {
  suggested_rewrite?: string | null;
  verification_condition?: string | null;
  implementation_steps: string[];
}

export interface Finding {
  finding_id: string;
  category: string;
  severity: Severity;
  title: string;
  what: string;
  where?: FindingWhere | null;
  why?: FindingWhy | null;
  how?: FindingHow | null;
  evidence: string[];
  confidence: Confidence;
  impact: number;
  confidence_numeric: number;
  effort: number;
  priority_score: number;
  status: RecommendationStatus;
}

export interface Passage {
  passage_id: string;
  section_id: string;
  text: string;
  word_count: number;
  start_offset: number;
  end_offset: number;
  named_subject: boolean;
  answer_first: boolean;
  answer_shape?: AnswerShape | null;
  issues: string[];
}

export interface PassageSkill {
  passage_id: string;
  strengths: string[];
  issues: string[];
}

export interface EvidenceSource {
  source_id: string;
  label: EvidenceLabel;
  title: string;
  url?: string | null;
  publisher?: string | null;
  publication_date?: string | null;
  excerpt?: string | null;
  accessed_at?: string | null;
}

export interface Claim {
  claim_id: string;
  statement: string;
  risk_tier: ClaimRiskTier;
  verification_state: VerificationState;
  passage_id?: string | null;
  evidence_source_ids: string[];
  requires_substantiation: boolean;
  issue?: string | null;
}

export interface AuditReport {
  audit_metadata: AuditMetadata;
  gate: GateResult;
  scores: Record<string, ComponentScore>;
  composite_avr?: number | null;
  entities: Entity[];
  eav_rows: EAVRow[];
  triples: SemanticTriple[];
  fanout: FanoutQuery[];
  coverage_rows: CoverageRow[];
  passage_findings: Finding[];
  passage_skills?: PassageSkill[];
  passages?: Passage[];
  claims: Claim[];
  recommendations: Finding[];
  swot: SwotAnalysis;
  measurement_plan: Array<Record<string, unknown>>;
  sources: EvidenceSource[];
  limitations?: string[];
  not_assessed?: string[];
  technical_flags?: TechnicalFlag[];
}

export interface TechnicalFlag {
  flag_id: string;
  label: string;
  severity: Severity;
  detail: string;
  detected: boolean;
}

/* -------------------------------------------------- document structure */

export interface TextSpan {
  start_offset: number;
  end_offset: number;
  text: string;
}

export interface Heading {
  level: number;
  text: string;
  id: string;
  offset: number;
}

export interface Link {
  url: string;
  anchor_text: string;
  is_internal: boolean;
  is_anchor: boolean;
}

export interface Section {
  section_id: string;
  heading?: Heading | null;
  passages: Passage[];
  raw_text: string;
  word_count: number;
}

export interface ParsedDocument {
  raw_text: string;
  normalized_text: string;
  title?: string | null;
  sections: Section[];
  passages: Passage[];
  headings: Heading[];
  links: Link[];
  word_count: number;
  char_count: number;
  reading_time_minutes: number;
  content_hash: string;
}

/* ----------------------------------------------------------------- compare */

export interface ScoreDelta {
  key: string;
  baseline: number | null;
  candidate: number | null;
  delta: number | null;
}

export interface EntityChangeItem {
  id?: string;
  label?: string;
  kind?: string;
  field?: string;
  before?: unknown;
  after?: unknown;
}

/** A single row in a compare change list (entity, EAV or coverage). */
export interface ChangeItem {
  id?: string;
  label?: string;
  kind?: string;
  field?: string;
  triple?: string;
  entity?: string;
  attribute?: string;
  before?: unknown;
  after?: unknown;
  before_status?: string;
  after_status?: string;
}

export interface EavChangeItem {
  entity?: string;
  attribute?: string;
  before_status?: string;
  after_status?: string;
  evidence_excerpt?: string;
}

export interface CompareResponse {
  score_delta: ScoreDelta[];
  entity_changes: {
    added: Array<string | EntityChangeItem>;
    removed: Array<string | EntityChangeItem>;
    changed: Array<string | EntityChangeItem>;
  };
  eav_improved: Array<string | EavChangeItem>;
  eav_regressed: Array<string | EavChangeItem>;
  coverage_delta: {
    baseline_covered?: number;
    candidate_covered?: number;
    total?: number;
    baseline_fcs?: number;
    candidate_fcs?: number;
    improved?: unknown[];
    regressed?: unknown[];
  };
  new_findings: Finding[];
  resolved_findings: Finding[];
  warnings: string[];
}

/* ---------------------------------------------------------------- handoff */

export interface WriterHandoff {
  brief_markdown: string;
  actions: Array<{ finding_id: string; title: string; suggested_rewrite?: string | null }>;
  lexicon: { include: string[]; replace: string[]; avoid: string[] };
}

export type ExportFormat = "markdown" | "html" | "json" | "csv";

/* -------------------------------------------------------------- providers */

export interface ProviderInfo {
  id: ModelProviderType | string;
  type: ModelProviderType;
  label: string;
  requires_api_key: boolean;
  local: boolean;
  structured_output: boolean;
  sends_data_off_device: boolean;
  description: string;
  cost_warning?: string | null;
}

export interface ProvidersResponse {
  providers: ProviderInfo[];
}

export interface TestConnectionRequest {
  provider_type: ModelProviderType;
  base_url?: string | null;
  model: string;
  api_key?: string | null;
}

export interface TestConnectionResponse {
  ok: boolean;
  latency_ms: number;
  detail: string;
  /** Extra fields some API builds echo back. */
  status?: string;
  provider?: string;
  model_name?: string;
}

/* --------------------------------------------------------------- mcp (v1) */

export interface McpServerConfig {
  id: string;
  name: string;
  transport: "stdio" | "http";
  endpoint: string;
  allowed_tools: string[];
  timeout_seconds: number;
  enabled: boolean;
}

/* ------------------------------------------------------------- workspace */
/* Mirrors packages/schemas/ega_schemas/workspace.py — deterministic read
 * models backing the Entity Hub, Brief Builder and Optimizer screens. */

export interface EntityFact {
  property: string;
  value: string;
  source: string;
  date?: string | null;
  verified: boolean;
}

export interface EntitySourceRef {
  title: string;
  url?: string | null;
}

export interface WorkspaceEntity {
  entity_id: string;
  canonical_id: string;
  name: string;
  kind: string;
  entity_kind: string;
  aliases: string[];
  pages_used: number;
  facts_count: number;
  last_verified?: string | null;
  status: "healthy" | "conflict" | "needs_review";
  conflict_detail?: string | null;
  definition: string;
  at_id: string;
  schema_type: string;
  facts: EntityFact[];
  sources: EntitySourceRef[];
  origins: string[];
}

export interface WorkspaceEntitiesResponse {
  project_id?: string | null;
  entities: WorkspaceEntity[];
  generated_at: string;
  source_audits: number;
  source_packs: number;
  disclaimer: string;
}

export interface BriefSourceItem {
  id: string;
  kind: "question" | "fact" | "gap";
  title: string;
  source: string;
  tag: string;
  provenance: string;
}

export interface BriefEntityRef {
  name: string;
  kind: string;
}

export interface BriefSection {
  id: string;
  h2_number: number;
  title: string;
  badge: string;
  entities: BriefEntityRef[];
  facts: string[];
  directive: string;
  word_range: string;
}

export interface BriefConstraints {
  audience?: string | null;
  tone?: string | null;
  reading_level: string;
  intent?: string | null;
}

export interface BriefInformationGain {
  directive: string;
  polarity: "do" | "avoid";
}

export interface BriefBasis {
  audit_id?: string | null;
  audit_created_at?: string | null;
  context_pack_ids: string[];
  context_pack_versions: string[];
}

export interface BriefGenerateRequest {
  project_id: string;
  target_query?: string | null;
  audit_id?: string | null;
  context_pack_ids?: string[];
  max_sections?: number;
}

export interface BriefResponse {
  project_id: string;
  target_query: string;
  sources: BriefSourceItem[];
  sections: BriefSection[];
  constraints: BriefConstraints;
  information_gain: BriefInformationGain[];
  basis: BriefBasis;
  generated_at: string;
  disclaimer: string;
}

/** Request payload for the deterministic content-brief generator (`POST /content/brief`). */
export interface ContentBriefPayload {
  target_query: string;
  page_type?: string;
  project_id?: string;
  brand_name?: string;
  location?: string;
  context_pack_id?: string;
}

/** A single research source in a generated content brief. */
export interface ContentBriefSource {
  id: string;
  type: "question" | "fact" | "gap";
  title: string;
  source: string;
  tag: string;
  tagColor: string;
}

/** A single H2 outline section in a generated content brief. */
export interface ContentBriefSection {
  id: string;
  h2Number: number;
  title: string;
  badge: string;
  badgeColor: string;
  entities: Array<{ name: string; type: string }>;
  facts: string[];
  directive: string;
  wordRange: string;
}

/** Response from the deterministic content-brief generator. */
export interface ContentBriefResponse {
  target_query: string;
  page_type: string;
  brand_name: string;
  location: string;
  intent: string;
  recommended_word_count: string;
  reading_level: string;
  sources: ContentBriefSource[];
  sections: ContentBriefSection[];
  lexicon: {
    include: string[];
    replace: Array<{ from: string; to: string }>;
    avoid: string[];
  };
  grounded?: boolean;
  disclaimer?: string;
}

export interface AnalyzeRequest {
  text: string;
  primary_query?: string | null;
  page_type?: string | null;
  target_entities?: string[];
  banned_terms?: string[];
  context_pack_ids?: string[];
  word_target?: number;
}

export interface AnalyzeHeading {
  level: number;
  text: string;
  is_question: boolean;
}

export interface AnalyzeEntityHit {
  name: string;
  count: number;
  expected: boolean;
  status: "ok" | "thin" | "missing";
}

export interface AnalyzeViolation {
  term: string;
  count: number;
  replacement?: string | null;
}

export interface AnalyzeDimension {
  key: string;
  label: string;
  score: number;
  band: "weak" | "fair" | "strong";
  note: string;
}

export interface AnalyzeRecommendation {
  id: string;
  title: string;
  detail: string;
  dimension: string;
  impact: "high" | "medium" | "low";
  action: string;
}

export interface AnalyzeMetrics {
  word_count: number;
  sentence_count: number;
  paragraph_count: number;
  reading_time_minutes: number;
  reading_ease: number;
  flesch_kincaid_grade: number;
}

export interface AnalyzeResponse {
  metrics: AnalyzeMetrics;
  headings: AnalyzeHeading[];
  entities: AnalyzeEntityHit[];
  violations: AnalyzeViolation[];
  dimensions: AnalyzeDimension[];
  recommendations: AnalyzeRecommendation[];
  overall_score: number;
  disclaimer: string;
}
