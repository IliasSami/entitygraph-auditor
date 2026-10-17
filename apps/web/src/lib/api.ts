/**
 * Typed client for the EntityGraph Auditor API (`/api/v1`).
 *
 * When `NEXT_PUBLIC_MOCK=1` every method is served by the deterministic
 * in-memory mock (`./mock`), which lets the whole UI be demonstrated without a
 * backend. All other methods hit `NEXT_PUBLIC_API_BASE` (default
 * http://localhost:8000) and translate the backend's stable error shape
 * `{code, message, trace_id}` into `ApiError`.
 */

import { ApiError } from "@/lib/errors";
import { mock } from "@/lib/mock";
import type {
  AuditCreateRequest,
  AuditCreateResponse,
  AuditListRow,
  AuditRunDetail,
  AuditStageEvent,
  AuditStatusEvent,
  AnalyzeRequest,
  AnalyzeResponse,
  BriefGenerateRequest,
  BriefResponse,
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
  SemanticTriple,
  TestConnectionRequest,
  TestConnectionResponse,
  WorkspaceEntitiesResponse,
  WriterHandoff,
  AuditDepth,
  SourceProfile,
} from "@/lib/types";

export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"
).replace(/\/$/, "");

export const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK === "1";

export const isMockMode = (): boolean => MOCK_MODE;

const API_PREFIX = "/api/v1";

async function parseError(response: Response): Promise<ApiError> {
  let payload: { code?: string; message?: string; trace_id?: string | null } = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  return ApiError.fromPayload(
    {
      code: payload.code ?? `HTTP_${response.status}`,
      message: payload.message ?? `Request failed with status ${response.status}.`,
      trace_id: payload.trace_id ?? null,
    },
    response.status,
  );
}

async function request<T>(
  path: string,
  init: RequestInit & { json?: unknown; formData?: FormData } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  if (init.formData) body = init.formData;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
      ...init,
      headers,
      body,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "NETWORK_ERROR",
      `Cannot reach the API at ${API_BASE}. Start the backend or enable mock mode.`,
      0,
    );
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/* Real-mode SSE via EventSource; tolerates both the implemented event shape
 * (`{type:"stage"|"status", ...}`) and the documented bare payloads. */
function subscribeReal(
  auditId: string,
  onStage: (event: AuditStageEvent) => void,
  onStatus: (event: AuditStatusEvent) => void,
  onError?: (error: Error) => void,
): () => void {
  const source = new EventSource(
    `${API_BASE}${API_PREFIX}/audits/${encodeURIComponent(auditId)}/events`,
  );
  source.onmessage = (message) => {
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(message.data);
    } catch {
      return;
    }
    if (payload.type === "stage" || typeof payload.node === "string") {
      onStage(payload as unknown as AuditStageEvent);
      return;
    }
    if (payload.type === "status" || typeof payload.status === "string") {
      onStatus(payload as unknown as AuditStatusEvent);
      return;
    }
  };
  source.onerror = () => {
    // EventSource retries automatically; only report when the stream is closed.
    if (source.readyState === EventSource.CLOSED) {
      onError?.(new Error("The audit event stream closed before completion."));
    }
  };
  return () => source.close();
}

function normaliseProviders(payload: unknown): { providers: ProviderInfo[] } {
  const raw = Array.isArray(payload)
    ? payload
    : ((payload as { providers?: unknown[] })?.providers ?? []);
  return {
    providers: raw.map((item) => {
      const provider = item as Partial<ProviderInfo> & {
        name?: string;
        is_local?: boolean;
        model?: string;
      };
      const local = provider.local ?? provider.is_local ?? false;
      return {
        id: provider.id ?? provider.type ?? "unknown",
        type: provider.type ?? (provider.id as ProviderInfo["type"]) ?? "dummy",
        label: provider.label ?? provider.name ?? String(provider.id ?? "Provider"),
        requires_api_key: provider.requires_api_key ?? !local,
        local,
        structured_output: provider.structured_output ?? true,
        sends_data_off_device: provider.sends_data_off_device ?? !local,
        description: provider.description ?? "",
        cost_warning:
          provider.cost_warning ??
          (!local
            ? "Cloud provider: audited page text is sent off this machine and usage may be billed."
            : null),
      } satisfies ProviderInfo;
    }),
  };
}

export const api = {
  /* ------------------------------------------------------------ system */

  health: (): Promise<HealthStatus> =>
    MOCK_MODE ? mock.health() : request<HealthStatus>("/health"),

  readiness: (): Promise<ReadinessStatus> =>
    MOCK_MODE ? mock.readiness() : request<ReadinessStatus>("/readiness"),

  /* ---------------------------------------------------------- projects */

  listProjects: (): Promise<ProjectRead[]> =>
    MOCK_MODE ? mock.listProjects() : request<ProjectRead[]>("/projects"),

  getProject: (projectId: string): Promise<ProjectRead> =>
    MOCK_MODE
      ? mock.getProject(projectId)
      : request<ProjectRead>(`/projects/${encodeURIComponent(projectId)}`),

  createProject: (payload: ProjectCreate): Promise<ProjectRead> =>
    MOCK_MODE
      ? mock.createProject(payload)
      : request<ProjectRead>("/projects", { method: "POST", json: payload }),

  deleteProject: async (projectId: string): Promise<{ deleted: boolean }> => {
    if (MOCK_MODE) return mock.deleteProject(projectId);
    await request<void>(`/projects/${encodeURIComponent(projectId)}`, { method: "DELETE" });
    return { deleted: true };
  },

  /* ----------------------------------------------------------- content */

  importContent: (input: {
    text?: string;
    format?: string;
    filename?: string;
    file?: File;
    project_id?: string;
  }): Promise<ContentImportResponse> => {
    if (MOCK_MODE) return mock.importContent(input);
    const query = input.project_id ? `?project_id=${encodeURIComponent(input.project_id)}` : "";
    if (input.file) {
      const formData = new FormData();
      formData.append("file", input.file);
      return request<ContentImportResponse>(`/content/import${query}`, {
        method: "POST",
        formData,
      });
    }
    return request<ContentImportResponse>(`/content/import${query}`, {
      method: "POST",
      json: { text: input.text, format: input.format ?? "markdown", filename: input.filename },
    });
  },

  fetchUrl: (payload: {
    url: string;
    project_id?: string;
  }): Promise<import("@/lib/types").FetchUrlResponse> => {
    if (MOCK_MODE) return mock.fetchUrl(payload);
    const query = payload.project_id ? `?project_id=${encodeURIComponent(payload.project_id)}` : "";
    return request<import("@/lib/types").FetchUrlResponse>(`/content/fetch-url${query}`, {
      method: "POST",
      json: { url: payload.url, store: true },
    });
  },

  generateContentBrief: (payload: ContentBriefPayload): Promise<ContentBriefResponse> =>
    MOCK_MODE
      ? mock.generateContentBrief(payload)
      : request("/content/brief", { method: "POST", json: payload }),

  /* ------------------------------------------------------ context packs */

  listContextPacks: (): Promise<ContextPackSummary[]> =>
    MOCK_MODE ? mock.listContextPacks() : request<ContextPackSummary[]>("/context-packs"),

  getContextPack: (packId: string): Promise<ContextPackDetail & { payload?: Record<string, unknown> }> =>
    MOCK_MODE
      ? mock.getContextPack(packId)
      : request<ContextPackDetail & { payload?: Record<string, unknown> }>(`/context-packs/${encodeURIComponent(packId)}`),

  importContextPack: (file: File): Promise<ContextPackSummary> => {
    if (MOCK_MODE) return mock.importContextPack(file);
    const formData = new FormData();
    formData.append("file", file);
    return request<ContextPackSummary>("/context-packs/import", { method: "POST", formData });
  },

  addPackFact: (
    packId: string,
    fact: { property?: string; key?: string; value: string; source?: string },
  ): Promise<{ success: boolean; fact: unknown; total_facts: number }> =>
    request(`/context-packs/${encodeURIComponent(packId)}/facts`, { method: "POST", json: fact }),

  addPackEntity: (
    packId: string,
    entity: { name: string; type?: string; definition?: string; canonical_id?: string; at_id?: string },
  ): Promise<{ success: boolean; entity: unknown; total_entities: number }> =>
    request(`/context-packs/${encodeURIComponent(packId)}/entities`, { method: "POST", json: entity }),

  getPackSchemaJsonLd: (packId: string): Promise<Record<string, unknown>> =>
    request(`/context-packs/${encodeURIComponent(packId)}/schema-jsonld`),

  /* ------------------------------------------------------------ audits */

  listAudits: (filters?: { project_id?: string; status?: string }): Promise<AuditListRow[]> => {
    if (MOCK_MODE) return mock.listAudits(filters);
    const params = new URLSearchParams();
    if (filters?.project_id) params.set("project_id", filters.project_id);
    if (filters?.status) params.set("status", filters.status);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request<AuditListRow[]>(`/audits${query}`);
  },

  getAudit: (auditId: string): Promise<AuditRunDetail> =>
    MOCK_MODE
      ? mock.getAudit(auditId)
      : request<AuditRunDetail>(`/audits/${encodeURIComponent(auditId)}`),

  createAudit: (payload: AuditCreateRequest): Promise<AuditCreateResponse> =>
    MOCK_MODE
      ? mock.createAudit(payload)
      : request<AuditCreateResponse>("/audits", { method: "POST", json: payload }),

  subscribeAuditEvents: (
    auditId: string,
    onStage: (event: AuditStageEvent) => void,
    onStatus: (event: AuditStatusEvent) => void,
    onError?: (error: Error) => void,
  ): (() => void) =>
    MOCK_MODE
      ? mock.subscribeAuditEvents(auditId, onStage, onStatus, onError)
      : subscribeReal(auditId, onStage, onStatus, onError),

  getAuditEntities: (auditId: string) =>
    MOCK_MODE
      ? mock.getAuditEntities(auditId)
      : request<import("@/lib/types").Entity[]>(`/audits/${encodeURIComponent(auditId)}/entities`),

  getAuditTriples: (auditId: string): Promise<SemanticTriple[]> =>
    MOCK_MODE
      ? mock.getAuditTriples(auditId)
      : request<SemanticTriple[]>(`/audits/${encodeURIComponent(auditId)}/triples`),

  getAuditFanout: (auditId: string) =>
    MOCK_MODE
      ? mock.getAuditFanout(auditId)
      : request<import("@/lib/types").FanoutQuery[]>(`/audits/${encodeURIComponent(auditId)}/fanout`),

  getAuditFindings: (auditId: string): Promise<Finding[]> =>
    MOCK_MODE
      ? mock.getAuditFindings(auditId)
      : request<Finding[]>(`/audits/${encodeURIComponent(auditId)}/findings`),

  getAuditScores: (auditId: string): Promise<Scorecard> =>
    MOCK_MODE
      ? mock.getAuditScores(auditId)
      : request<Scorecard>(`/audits/${encodeURIComponent(auditId)}/scores`),

  compareAudits: (baselineId: string, candidateId: string): Promise<CompareResponse> =>
    MOCK_MODE
      ? mock.compareAudits(baselineId, candidateId)
      : request<CompareResponse>("/audits/compare", {
          method: "POST",
          json: { baseline_id: baselineId, candidate_id: candidateId },
        }),

  writerHandoff: (auditId: string): Promise<WriterHandoff> =>
    MOCK_MODE
      ? mock.writerHandoff(auditId)
      : request<WriterHandoff>(`/audits/${encodeURIComponent(auditId)}/writer-handoff`, {
          method: "POST",
        }),

  /** Downloads an export blob plus a filename (from Content-Disposition). */
  exportAudit: (
    auditId: string,
    format: ExportFormat,
  ): Promise<{ blob: Blob; filename: string }> => {
    if (MOCK_MODE) return mock.exportAudit(auditId, format);
    return (async () => {
      const response = await fetch(
        `${API_BASE}${API_PREFIX}/audits/${encodeURIComponent(auditId)}/export`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ format }),
          cache: "no-store",
        },
      );
      if (!response.ok) throw await parseError(response);
      const disposition = response.headers.get("Content-Disposition") ?? "";
      const match = disposition.match(/filename="?([^";]+)"?/);
      return {
        blob: await response.blob(),
        filename: match?.[1] ?? `audit-${auditId}.${format === "markdown" ? "md" : format}`,
      };
    })();
  },

  deleteAudit: async (auditId: string): Promise<{ deleted: boolean }> => {
    if (MOCK_MODE) return mock.deleteAudit(auditId);
    await request<void>(`/audits/${encodeURIComponent(auditId)}`, { method: "DELETE" });
    return { deleted: true };
  },

  /* ---------------------------------------------------------- workspace */

  listEntities: (projectId: string): Promise<WorkspaceEntitiesResponse> =>
    MOCK_MODE
      ? mock.listEntities(projectId)
      : request<WorkspaceEntitiesResponse>(
          `/workspace/entities?project_id=${encodeURIComponent(projectId)}`,
        ),

  generateBrief: (payload: BriefGenerateRequest): Promise<BriefResponse> =>
    MOCK_MODE
      ? mock.generateBrief(payload)
      : request<BriefResponse>("/workspace/briefs/generate", {
          method: "POST",
          json: payload,
        }),

  analyzeContent: (payload: AnalyzeRequest): Promise<AnalyzeResponse> =>
    MOCK_MODE
      ? mock.analyzeContent(payload)
      : request<AnalyzeResponse>("/workspace/analyze", { method: "POST", json: payload }),

  /* ---------------------------------------------------------- providers */

  listProviders: (): Promise<{ providers: ProviderInfo[] }> => {
    if (MOCK_MODE) return mock.listProviders();
    return request<unknown>("/models/providers").then(normaliseProviders);
  },

  testConnection: (payload: TestConnectionRequest): Promise<TestConnectionResponse> => {
    if (MOCK_MODE) return mock.testConnection(payload);
    return request<Record<string, unknown>>("/models/test-connection", {
      method: "POST",
      json: {
        provider_type: payload.provider_type,
        model_name: payload.model,
        base_url: payload.base_url,
        api_key: payload.api_key,
      },
    }).then((raw) => {
      const status = String(raw.status ?? "");
      const ok = raw.ok === true || status === "connected" || status === "ok";
      return {
        ok,
        latency_ms: Number(raw.latency_ms ?? 0),
        detail: ok
          ? String(raw.detail ?? `${raw.provider ?? payload.provider_type} responded in ${raw.latency_ms ?? 0} ms.`)
          : String(raw.detail ?? raw.error ?? "Connection failed."),
        status,
        provider: raw.provider as string | undefined,
        model_name: (raw.model_name ?? payload.model) as string | undefined,
      };
    });
  },

  /* --------------------------------------------------------------- mcp */

  /** v1 may not implement MCP config yet; 404 is treated as "not configured". */
  listMcpServers: async (): Promise<McpServerConfig[]> => {
    if (MOCK_MODE) return mock.listMcpServers();
    try {
      return await request<McpServerConfig[]>("/mcp/servers");
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return [];
      throw error;
    }
  },

  getMcpTools: async (): Promise<{ tools: Array<{ name: string; description: string; parameters?: unknown }>; security: string }> => {
    if (MOCK_MODE) {
      return {
        tools: [
          { name: "run_content_audit", description: "Run a full local-first entity and AEO/GEO audit on web content or markdown." },
          { name: "analyze_entities", description: "Fast extraction of the central entity, candidate concepts, knowledge triples, and EAV status." },
          { name: "check_brand_compliance", description: "Evaluate brand compliance and publication gates: checks for banned terminology." },
          { name: "get_audit_report", description: "Retrieve an existing audit report by audit_id." },
        ],
        security: "Tool results and server descriptions are untrusted data.",
      };
    }
    return request<{ tools: Array<{ name: string; description: string; parameters?: unknown }>; security: string }>("/mcp/tools");
  },

  purgeTestData: (): Promise<{ ok: boolean; deleted_count: number; message: string }> => {
    if (MOCK_MODE) {
      return Promise.resolve({ ok: true, deleted_count: 0, message: "Mock storage purged." });
    }
    return request<{ ok: boolean; deleted_count: number; message: string }>("/system/maintenance/purge-test-data", {
      method: "POST",
    });
  },
};

export { ApiError };
export type {
  AuditDepth,
  SourceProfile,
  AuditCreateRequest,
  AuditStageEvent,
  AuditStatusEvent,
};
