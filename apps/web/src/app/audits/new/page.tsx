"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Cpu,
  FolderOpen,
  Info,
  Plug,
  Upload,
} from "@/components/icons";
import { z } from "zod";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonClasses } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { SampleDataBanner } from "@/components/status";
import { ErrorState, LoadingState } from "@/components/states";
import { api, isMockMode } from "@/lib/api";
import { usePageTitle } from "@/lib/use-page-title";
import { titleCase } from "@/lib/format";
import type {
  AuditCreateRequest,
  AuditDepth,
  ContentImportResponse,
  ModelProviderType,
  PageType,
  SensitivityTier,
  SourceProfile,
} from "@/lib/types";
import {
  AUDIT_DEPTHS,
  AUDIT_DEPTH_LABELS,
  PAGE_TYPES,
  PAGE_TYPE_LABELS,
  SENSITIVITY_TIERS,
  SENSITIVITY_TIER_LABELS,
  SOURCE_PROFILES,
  SOURCE_PROFILE_LABELS,
} from "@/lib/types";

const STEPS = [
  { id: 1, title: "Project & page" },
  { id: 2, title: "Content" },
  { id: 3, title: "Context & rules" },
  { id: 4, title: "Depth & provider" },
  { id: 5, title: "Review & run" },
] as const;

type ContentSource = "paste" | "upload" | "url";

interface FormValues {
  project_id: string;
  new_project_name: string;
  page_url: string;
  page_type: PageType | "";
  content_source: ContentSource;
  content_text: string;
  content_format: "markdown" | "html" | "text";
  content_url: string;
  primary_query: string;
  secondary_queries: string;
  audience_icp: string;
  location_target: string;
  conversion_goal: string;
  lifecycle: string;
  output_language: string;
  source_profile: SourceProfile;
  sensitivity: SensitivityTier;
  context_pack_ids: string[];
  depth: AuditDepth;
  deterministic_only: boolean;
  provider_type: ModelProviderType;
  model: string;
  base_url: string;
  api_key: string;
}

const DEFAULTS: FormValues = {
  project_id: "",
  new_project_name: "",
  page_url: "",
  page_type: "",
  content_source: "paste",
  content_text: "",
  content_format: "markdown",
  content_url: "",
  primary_query: "",
  secondary_queries: "",
  audience_icp: "",
  location_target: "",
  conversion_goal: "",
  lifecycle: "new_page",
  output_language: "en",
  source_profile: "offline",
  sensitivity: "ordinary",
  context_pack_ids: [],
  depth: "standard",
  deterministic_only: true,
  provider_type: "dummy",
  model: "",
  base_url: "",
  api_key: "",
};

const step1Schema = z.object({
  project_id: z.string().min(1, "Choose a project or create a new one."),
  page_type: z.string().min(1, "Choose a page type — it drives the EAV schema."),
});

const step2Schema = z.object({
  primary_query: z.string().min(3, "Describe the main query this page should answer."),
});

const step4Schema = z.object({
  model: z.string(),
});

function ErrorText({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="mt-1 text-xs font-medium text-destructive">
      {message}
    </p>
  );
}

export default function NewAuditPage() {
  usePageTitle("New audit");
  const router = useRouter();
  const queryClient = useQueryClient();
  const [step, setStep] = useState(1);
  const [imported, setImported] = useState<ContentImportResponse | null>(null);
  const [importError, setImportError] = useState<unknown>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fetchResult, setFetchResult] = useState<{
    content_version_id?: string;
    limitations: string[];
  } | null>(null);
  const [suggestionUsed, setSuggestionUsed] = useState<boolean | null>(null);
  const [runError, setRunError] = useState<unknown>(null);
  const [testResult, setTestResult] = useState<string | null>(null);

  const form = useForm<FormValues>({ defaultValues: DEFAULTS, mode: "onSubmit" });
  const { register, handleSubmit, watch, setValue, formState } = form;

  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.listProjects() });
  const packs = useQuery({ queryKey: ["context-packs"], queryFn: () => api.listContextPacks() });
  const providers = useQuery({ queryKey: ["providers"], queryFn: () => api.listProviders() });

  const values = watch();

  /* Prefill the project when arriving from a project or history screen. */
  useEffect(() => {
    if (values.project_id) return;
    const params = new URLSearchParams(window.location.search);
    const fromQuery = params.get("project_id");
    if (fromQuery) {
      setValue("project_id", fromQuery);
      return;
    }
    const first = projects.data?.[0];
    if (first) setValue("project_id", first.project_id);
  }, [projects.data, setValue, values.project_id]);

  const activeProvider = useMemo(
    () => providers.data?.providers.find((p) => p.type === values.provider_type) ?? null,
    [providers.data, values.provider_type],
  );

  const importMutation = useMutation({
    mutationFn: async () => {
      if (values.content_source === "paste") {
        return api.importContent({
          text: values.content_text,
          format: values.content_format,
          project_id: values.project_id,
        });
      }
      if (values.content_source === "upload") {
        if (!file) throw new Error("Choose a file to upload first.");
        return api.importContent({ file, project_id: values.project_id });
      }
      throw new Error("Use “Fetch URL” to import from a URL.");
    },
    onSuccess: (data) => {
      setImported(data);
      setImportError(null);
      setSuggestionUsed(null);
      const suggested = data.document_summary.suggested_page_type;
      if (suggested) setValue("page_type", suggested);
    },
    onError: (error) => {
      setImportError(error);
      setImported(null);
    },
  });

  const fetchMutation = useMutation({
    mutationFn: () => api.fetchUrl({ url: values.content_url, project_id: values.project_id }),
    onSuccess: (data) => {
      setFetchResult({ content_version_id: data.content_version_id, limitations: data.limitations });
      setImportError(null);
      if (data.content_version_id) {
        setImported({
          content_version_id: data.content_version_id,
          document_summary: data.document_summary ?? {
            word_count: 0,
            headings: 0,
            language_hint: "en",
            warnings: [],
            extraction_notes: [],
          },
        });
        const suggested = data.document_summary?.suggested_page_type;
        if (suggested) setValue("page_type", suggested);
      }
    },
    onError: (error) => {
      setImportError(error);
      setFetchResult(null);
    },
  });

  const testConnection = useMutation({
    mutationFn: () =>
      api.testConnection({
        provider_type: values.provider_type,
        model: values.model,
        base_url: values.base_url || null,
        api_key: values.api_key || null,
      }),
    onSuccess: (result) => {
      setTestResult(
        result.ok
          ? `Connected in ${result.latency_ms} ms. ${result.detail}`
          : `Failed: ${result.detail}`,
      );
    },
    onError: (error) => {
      setTestResult(error instanceof Error ? error.message : "Connection test failed.");
    },
  });

  const runMutation = useMutation({
    mutationFn: (payload: AuditCreateRequest) => api.createAudit(payload),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["audits"] });
      router.push(`/audits/${data.audit_id}`);
    },
    onError: (error) => setRunError(error),
  });

  const ensureContentId = async (): Promise<string | null> => {
    if (imported?.content_version_id) return imported.content_version_id;
    if (fetchResult?.content_version_id) return fetchResult.content_version_id;
    return null;
  };

  const goNext = async () => {
    if (step === 1) {
      const ok = await form.trigger(["project_id", "page_type"]);
      const parsed = step1Schema.safeParse({
        project_id: values.project_id,
        page_type: values.page_type,
      });
      if (!ok || !parsed.success) return;
      setStep(2);
      return;
    }
    if (step === 2) {
      const parsed = step2Schema.safeParse({ primary_query: values.primary_query });
      if (!parsed.success) {
        form.setError("primary_query", {
          message: parsed.error.issues[0]?.message ?? "Required",
        });
        return;
      }
      const contentId = await ensureContentId();
      if (!contentId) {
        setImportError(
          new Error("Import the page content before continuing — the audit needs the text."),
        );
        return;
      }
      form.clearErrors("primary_query");
      setStep(3);
      return;
    }
    if (step === 3) {
      setStep(4);
      return;
    }
    if (step === 4) {
      step4Schema.parse({ model: values.model });
      if (!values.deterministic_only && activeProvider?.requires_api_key && !values.api_key) {
        form.setError("api_key", { message: "This provider needs an API key." });
        return;
      }
      if (!values.deterministic_only && !values.model.trim()) {
        form.setError("model", { message: "Name the model to use." });
        return;
      }
      form.clearErrors(["api_key", "model"]);
      setStep(5);
    }
  };

  const onSubmit = handleSubmit(async (data) => {
    setRunError(null);
    const contentId = await ensureContentId();
    if (!contentId) {
      setImportError(new Error("Content must be imported before running the audit."));
      setStep(2);
      return;
    }
    const payload: AuditCreateRequest = {
      project_id: data.project_id,
      content_version_id: contentId,
      page_type: data.page_type || null,
      primary_query: data.primary_query,
      secondary_queries: data.secondary_queries
        .split(/[\n,]+/)
        .map((q) => q.trim())
        .filter(Boolean),
      audience_icp: data.audience_icp || null,
      location_target: data.location_target || null,
      conversion_goal: data.conversion_goal || null,
      page_url: data.page_url || null,
      lifecycle: data.lifecycle,
      context_pack_ids: data.context_pack_ids,
      source_profile: data.source_profile,
      sensitivity: data.sensitivity,
      depth: data.depth,
      language: data.output_language,
    };
    if (!data.deterministic_only) {
      payload.score_profile = null;
    }
    runMutation.mutate(payload);
  });

  const summary = imported?.document_summary ?? null;
  const selectedPackDetails = (packs.data ?? []).filter((p) =>
    values.context_pack_ids.includes(p.pack_id),
  );

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">New audit</h1>
        <p className="text-sm text-muted-foreground">
          Five steps: project and page, content, context rules, depth and provider, then
          review. Nothing is sent off this machine unless you choose a cloud provider.
        </p>
      </div>

      {isMockMode() ? <SampleDataBanner /> : null}

      <nav aria-label="Audit wizard progress">
        <ol className="flex flex-wrap gap-2">
          {STEPS.map((s) => (
            <li key={s.id} className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => (s.id < step ? setStep(s.id) : undefined)}
                aria-current={step === s.id ? "step" : undefined}
                disabled={s.id > step}
                className={`flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${
                  step === s.id
                    ? "border-primary bg-primary text-primary-foreground"
                    : s.id < step
                      ? "border-success/40 bg-success/10 text-success"
                      : "border-border text-muted-foreground"
                }`}
              >
                {s.id < step ? (
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                ) : (
                  <span aria-hidden className="tabular-nums">
                    {s.id}
                  </span>
                )}
                {s.title}
              </button>
            </li>
          ))}
        </ol>
      </nav>

      <form onSubmit={onSubmit} noValidate>
        <div data-testid="wizard-step" data-step={step}>
          {step === 1 ? (
            <Card>
              <CardHeader>
                <CardTitle>Project &amp; page</CardTitle>
                <CardDescription>
                  An audit always belongs to a project so scores can be compared over time.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {projects.isPending ? (
                  <LoadingState label="Loading projects…" />
                ) : projects.error ? (
                  <ErrorState error={projects.error} onRetry={() => projects.refetch()} />
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <Label htmlFor="project_id">Project</Label>
                      <Select id="project_id" {...register("project_id")}>
                        <option value="">Choose a project…</option>
                        {(projects.data ?? []).map((project) => (
                          <option key={project.project_id} value={project.project_id}>
                            {project.name}
                          </option>
                        ))}
                      </Select>
                      <ErrorText message={formState.errors.project_id?.message} />
                      <p className="mt-1 text-xs text-muted-foreground">
                        No project yet?{" "}
                        <Link href="/projects/new" className="text-primary hover:underline">
                          Create one first
                        </Link>
                        .
                      </p>
                    </div>
                    <div>
                      <Label htmlFor="page_type">Page type</Label>
                      <Select id="page_type" {...register("page_type")}>
                        <option value="">Choose a page type…</option>
                        {PAGE_TYPES.map((pageType) => (
                          <option key={pageType} value={pageType}>
                            {PAGE_TYPE_LABELS[pageType]}
                          </option>
                        ))}
                      </Select>
                      <ErrorText message={formState.errors.page_type?.message} />
                      <p className="mt-1 text-xs text-muted-foreground">
                        Page type selects the expected entity attributes. The classifier in
                        step 2 will suggest one from your content.
                      </p>
                    </div>
                    <div className="sm:col-span-2">
                      <Label htmlFor="page_url">Page URL (optional)</Label>
                      <Input
                        id="page_url"
                        type="url"
                        placeholder="https://example.com/services/roof-replacement"
                        {...register("page_url")}
                      />
                      <p className="mt-1 text-xs text-muted-foreground">
                        Used to identify the page in reports and to compare it with sibling
                        pages.
                      </p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : null}

          {step === 2 ? (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Content</CardTitle>
                  <CardDescription>
                    Provide the page content so it can be parsed deterministically. The audit
                    scores the text you give it — nothing else.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <fieldset>
                    <legend className="mb-2 text-xs font-medium text-muted-foreground">
                      Content source
                    </legend>
                    <div className="flex flex-wrap gap-2">
                      {(
                        [
                          ["paste", "Paste text"],
                          ["upload", "Upload file"],
                          ["url", "Fetch URL"],
                        ] as const
                      ).map(([key, label]) => (
                        <label
                          key={key}
                          className={`cursor-pointer rounded-full border px-3 py-1 text-xs font-medium ${
                            values.content_source === key
                              ? "border-primary bg-primary/10 text-primary"
                              : "border-border text-muted-foreground"
                          }`}
                        >
                          <input
                            type="radio"
                            value={key}
                            className="sr-only"
                            {...register("content_source")}
                          />
                          {label}
                        </label>
                      ))}
                    </div>
                  </fieldset>

                  {values.content_source === "paste" ? (
                    <div className="space-y-2">
                      <Label htmlFor="content_text">
                        Page content ({values.content_format})
                      </Label>
                      <Textarea
                        id="content_text"
                        rows={10}
                        placeholder="# Page heading&#10;&#10;Paste the page copy exactly as it will be published…"
                        {...register("content_text")}
                      />
                      <div>
                        <Label htmlFor="content_format">Content format</Label>
                        <Select id="content_format" className="sm:w-48" {...register("content_format")}>
                          <option value="markdown">Markdown</option>
                          <option value="html">HTML</option>
                          <option value="text">Plain text</option>
                        </Select>
                      </div>
                    </div>
                  ) : null}

                  {values.content_source === "upload" ? (
                    <div className="space-y-2">
                      <Label htmlFor="content_file">Markdown, HTML, or text file</Label>
                      <input
                        id="content_file"
                        type="file"
                        accept=".md,.markdown,.html,.htm,.txt"
                        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                        className="block w-full rounded-md border border-input bg-card p-2 text-sm file:mr-3 file:rounded file:border-0 file:bg-secondary file:px-3 file:py-1 file:text-xs"
                      />
                      {file ? (
                        <p className="text-xs text-muted-foreground">
                          {file.name} · {Math.max(1, Math.round(file.size / 1024))} KB
                        </p>
                      ) : null}
                    </div>
                  ) : null}

                  {values.content_source === "url" ? (
                    <div className="space-y-2">
                      <Label htmlFor="content_url">Page URL to fetch</Label>
                      <Input
                        id="content_url"
                        type="url"
                        placeholder="https://example.com/page"
                        {...register("content_url")}
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => fetchMutation.mutate()}
                        disabled={fetchMutation.isPending || !values.content_url}
                      >
                        <Plug className="h-3.5 w-3.5" aria-hidden />
                        {fetchMutation.isPending ? "Fetching…" : "Fetch URL"}
                      </Button>
                      <Alert variant="warning" title="What fetching cannot do">
                        <ul className="list-disc space-y-1 pl-4">
                          <li>JavaScript-rendered content is not executed.</li>
                          <li>
                            Private-network and loopback addresses are blocked (SSRF
                            protection).
                          </li>
                          <li>Images, PDFs, and page speed are not analysed by a fetch.</li>
                        </ul>
                      </Alert>
                      {fetchResult?.limitations.length ? (
                        <div className="rounded-md border p-3 text-xs text-muted-foreground">
                          <p className="font-medium text-foreground">
                            Limitations reported for this fetch
                          </p>
                          <ul className="mt-1 list-disc space-y-1 pl-4">
                            {fetchResult.limitations.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {values.content_source !== "url" ? (
                    <div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => importMutation.mutate()}
                        disabled={importMutation.isPending}
                      >
                        <Upload className="h-3.5 w-3.5" aria-hidden />
                        {importMutation.isPending ? "Importing…" : "Import content"}
                      </Button>
                    </div>
                  ) : null}

                  {importError ? (
                    <ErrorState error={importError} title="Content import failed" />
                  ) : null}

                  {summary ? (
                    <div className="rounded-md border p-3" data-testid="content-summary">
                      <p className="flex items-center gap-2 text-sm font-semibold">
                        <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />
                        Content imported
                      </p>
                      <dl className="mt-2 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
                        <div>
                          <dt className="text-muted-foreground">Words</dt>
                          <dd className="tabular-nums">{summary.word_count}</dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">Headings</dt>
                          <dd className="tabular-nums">{summary.headings}</dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">Language hint</dt>
                          <dd>{summary.language_hint}</dd>
                        </div>
                      </dl>
                      {summary.suggested_page_type ? (
                        <div className="mt-3 rounded-md border border-info/40 bg-info/5 p-3">
                          <p className="flex items-center gap-2 text-sm font-medium">
                            <Info className="h-4 w-4 text-info" aria-hidden />
                            Classifier suggestion:{" "}
                            {PAGE_TYPE_LABELS[summary.suggested_page_type]}
                            {summary.page_type_confidence != null
                              ? ` (confidence ${summary.page_type_confidence.toFixed(2)})`
                              : ""}
                          </p>
                          {summary.page_type_rationale ? (
                            <p className="mt-1 text-sm text-muted-foreground">
                              {summary.page_type_rationale}
                            </p>
                          ) : null}
                          <div className="mt-2 flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setValue("page_type", summary.suggested_page_type as PageType);
                                setSuggestionUsed(true);
                              }}
                            >
                              Use suggestion
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setSuggestionUsed(false)}
                            >
                              Keep my choice
                            </Button>
                          </div>
                          {suggestionUsed === true ? (
                            <p className="mt-1 text-xs text-muted-foreground">
                              Using the classifier suggestion — you can still override it above.
                            </p>
                          ) : suggestionUsed === false ? (
                            <p className="mt-1 text-xs text-muted-foreground">
                              Keeping the page type you chose. The report will note the
                              difference.
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                      {summary.warnings.length ? (
                        <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-warning">
                          {summary.warnings.map((warning) => (
                            <li key={warning}>{warning}</li>
                          ))}
                        </ul>
                      ) : null}
                      {summary.extraction_notes.length ? (
                        <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted-foreground">
                          {summary.extraction_notes.map((note) => (
                            <li key={note}>{note}</li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Queries &amp; audience</CardTitle>
                  <CardDescription>
                    The queries you supply are treated as observed intent. Everything else the
                    auditor generates is labelled simulated.
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <Label htmlFor="primary_query">Primary query</Label>
                    <Input
                      id="primary_query"
                      placeholder="roof replacement bellingham wa"
                      {...register("primary_query")}
                    />
                    <ErrorText message={formState.errors.primary_query?.message} />
                  </div>
                  <div className="sm:col-span-2">
                    <Label htmlFor="secondary_queries">
                      Secondary queries (one per line or comma separated)
                    </Label>
                    <Textarea
                      id="secondary_queries"
                      rows={3}
                      placeholder={"how much does a new roof cost in bellingham\nmetal roof vs asphalt shingle cost"}
                      {...register("secondary_queries")}
                    />
                  </div>
                  <div>
                    <Label htmlFor="audience_icp">Audience / ICP</Label>
                    <Input id="audience_icp" {...register("audience_icp")} />
                  </div>
                  <div>
                    <Label htmlFor="location_target">Location target</Label>
                    <Input id="location_target" placeholder="Bellingham, WA" {...register("location_target")} />
                  </div>
                  <div>
                    <Label htmlFor="conversion_goal">Conversion goal</Label>
                    <Input
                      id="conversion_goal"
                      placeholder="Book a free roof inspection"
                      {...register("conversion_goal")}
                    />
                  </div>
                  <div>
                    <Label htmlFor="lifecycle">Page lifecycle</Label>
                    <Select id="lifecycle" {...register("lifecycle")}>
                      <option value="new_page">New page</option>
                      <option value="refresh">Refresh existing page</option>
                      <option value="post_migration">Post-migration check</option>
                    </Select>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : null}

          {step === 3 ? (
            <Card>
              <CardHeader>
                <CardTitle>Context &amp; rules</CardTitle>
                <CardDescription>
                  Context packs supply approved facts, brand rules, and banned terms. Where
                  they conflict, the conflict is shown rather than silently resolved.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <Label htmlFor="source_profile">Source profile</Label>
                    <Select id="source_profile" {...register("source_profile")}>
                      {SOURCE_PROFILES.map((profile) => (
                        <option key={profile} value={profile}>
                          {SOURCE_PROFILE_LABELS[profile]}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="sensitivity">Sensitivity</Label>
                    <Select id="sensitivity" {...register("sensitivity")}>
                      {SENSITIVITY_TIERS.map((tier) => (
                        <option key={tier} value={tier}>
                          {SENSITIVITY_TIER_LABELS[tier]}
                        </option>
                      ))}
                    </Select>
                    <p className="mt-1 text-xs text-muted-foreground">
                      High-stakes and regulated content triggers stricter claim checks.
                    </p>
                  </div>
                  <div>
                    <Label htmlFor="output_language">Language</Label>
                    <Input id="output_language" {...register("output_language")} />
                  </div>
                </div>

                <fieldset>
                  <legend className="mb-2 text-xs font-medium text-muted-foreground">
                    Context packs
                  </legend>
                  {packs.isPending ? (
                    <LoadingState label="Loading context packs…" />
                  ) : packs.error ? (
                    <ErrorState error={packs.error} onRetry={() => packs.refetch()} />
                  ) : (packs.data ?? []).length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No context packs are installed.{" "}
                      <Link href="/context-packs" className="text-primary hover:underline">
                        Import a pack
                      </Link>{" "}
                      to check this page against your canonical facts.
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {(packs.data ?? []).map((pack) => {
                        const checked = values.context_pack_ids.includes(pack.pack_id);
                        return (
                          <li key={pack.pack_id} className="rounded-md border p-3">
                            <label className="flex items-start gap-3">
                              <input
                                type="checkbox"
                                className="mt-1 h-4 w-4"
                                checked={checked}
                                onChange={(e) => {
                                  const next = e.target.checked
                                    ? [...values.context_pack_ids, pack.pack_id]
                                    : values.context_pack_ids.filter((id) => id !== pack.pack_id);
                                  setValue("context_pack_ids", next);
                                }}
                              />
                              <span className="min-w-0">
                                <span className="flex flex-wrap items-center gap-2">
                                  <span className="text-sm font-medium">{pack.name}</span>
                                  <Badge variant="secondary">v{pack.version}</Badge>
                                  <span className="text-xs text-muted-foreground">
                                    {pack.counts ? (
                                      <>
                                        {pack.counts.canonical_facts} facts ·{" "}
                                        {pack.counts.brand_rules} rules ·{" "}
                                        {pack.counts.banned_terms} banned terms
                                      </>
                                    ) : (
                                      <>
                                        {pack.rule_count ?? 0} rules · {pack.document_count ?? 0} documents
                                      </>
                                    )}
                                  </span>
                                </span>
                                <span className="mt-1 block text-xs text-muted-foreground">
                                  {pack.description}
                                </span>
                                {pack.conflicts.length ? (
                                  <span className="mt-2 block rounded border border-warning/40 bg-warning/5 p-2 text-xs text-warning">
                                    <span className="flex items-center gap-1 font-medium">
                                      <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
                                      {pack.conflicts.length} internal conflict
                                      {pack.conflicts.length === 1 ? "" : "s"} — reviewed in the
                                      report
                                    </span>
                                  </span>
                                ) : null}
                              </span>
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </fieldset>

                {selectedPackDetails.length > 0 ? (
                  <p className="text-xs text-muted-foreground" data-testid="selected-packs">
                    Selected: {selectedPackDetails.map((p) => `${p.name} v${p.version}`).join(", ")}
                  </p>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {step === 4 ? (
            <Card>
              <CardHeader>
                <CardTitle>Depth &amp; provider</CardTitle>
                <CardDescription>
                  Deterministic-only mode runs entirely on this machine. Adding a model
                  provider improves some checks but may send page text off-device.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <fieldset>
                  <legend className="mb-2 text-xs font-medium text-muted-foreground">
                    Audit depth
                  </legend>
                  <div className="grid gap-2 sm:grid-cols-3">
                    {AUDIT_DEPTHS.map((depth) => (
                      <label
                        key={depth}
                        className={`cursor-pointer rounded-md border p-3 text-sm ${
                          values.depth === depth
                            ? "border-primary bg-primary/5"
                            : "border-border"
                        }`}
                      >
                        <input
                          type="radio"
                          value={depth}
                          className="sr-only"
                          {...register("depth")}
                        />
                        <span className="font-medium">{AUDIT_DEPTH_LABELS[depth]}</span>
                        <span className="mt-1 block text-xs text-muted-foreground">
                          {depth === "quick"
                            ? "Core scores only. Fastest, fewest simulated queries."
                            : depth === "standard"
                              ? "All core scores plus passage and claim checks."
                              : "Adds expanded query fan-out and competitor gap analysis."}
                        </span>
                      </label>
                    ))}
                  </div>
                </fieldset>

                <div className="flex items-start gap-3 rounded-md border p-3">
                  <Switch
                    id="deterministic_only"
                    checked={values.deterministic_only}
                    onCheckedChange={(checked) => setValue("deterministic_only", checked)}
                  />
                  <div>
                    <Label htmlFor="deterministic_only" className="mb-0">
                      Deterministic-only (recommended)
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Runs every check with local rules — no API keys, no network calls, no
                      billing. Model-generated stages will be labelled “skipped”.
                    </p>
                  </div>
                </div>

                {!values.deterministic_only ? (
                  <div className="space-y-4 rounded-md border p-3">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <Label htmlFor="provider_type">Model provider</Label>
                        <Select
                          id="provider_type"
                          {...register("provider_type")}
                          onChange={(e) => {
                            const type = e.target.value as ModelProviderType;
                            setValue("provider_type", type);
                            const info = providers.data?.providers.find((p) => p.type === type);
                            setValue("model", info?.label && type === "ollama" ? "llama3.1:8b" : "");
                          }}
                        >
                          {(providers.data?.providers ?? []).map((provider) => (
                            <option key={provider.type} value={provider.type}>
                              {provider.label}
                            </option>
                          ))}
                        </Select>
                      </div>
                      <div>
                        <Label htmlFor="model">Model name</Label>
                        <Input
                          id="model"
                          placeholder={values.provider_type === "ollama" ? "llama3.1:8b" : "gpt-4o-mini"}
                          {...register("model")}
                        />
                        <ErrorText message={formState.errors.model?.message} />
                      </div>
                      {activeProvider?.local ? (
                        <div className="sm:col-span-2">
                          <Label htmlFor="base_url">Local endpoint</Label>
                          <Input
                            id="base_url"
                            placeholder="http://localhost:11434"
                            {...register("base_url")}
                          />
                        </div>
                      ) : (
                        <div className="sm:col-span-2">
                          <Label htmlFor="api_key">API key</Label>
                          <Input
                            id="api_key"
                            type="password"
                            autoComplete="off"
                            {...register("api_key")}
                          />
                          <ErrorText message={formState.errors.api_key?.message} />
                          <p className="mt-1 text-xs text-muted-foreground">
                            Keys are held in memory for this request only and are never
                            written to logs or to the report.
                          </p>
                        </div>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => testConnection.mutate()}
                        disabled={testConnection.isPending || !values.model}
                      >
                        <Cpu className="h-3.5 w-3.5" aria-hidden />
                        {testConnection.isPending ? "Testing…" : "Test connection"}
                      </Button>
                      {testResult ? (
                        <span
                          className="text-xs text-muted-foreground"
                          role="status"
                          data-testid="test-connection-result"
                        >
                          {testResult}
                        </span>
                      ) : null}
                    </div>

                    {activeProvider?.sends_data_off_device ? (
                      <Alert variant="warning" title="This provider sends data off-device">
                        <p>{activeProvider.cost_warning ?? activeProvider.description}</p>
                      </Alert>
                    ) : (
                      <Alert variant="info" title="Local provider">
                        <p>
                          {activeProvider?.description ??
                            "The selected provider runs locally on this machine."}
                        </p>
                      </Alert>
                    )}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {step === 5 ? (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Review &amp; run</CardTitle>
                  <CardDescription>
                    Check the inputs. Running starts the staged pipeline; you will see each
                    stage complete on the report screen.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
                    <div>
                      <dt className="text-muted-foreground">Project</dt>
                      <dd>
                        {(projects.data ?? []).find((p) => p.project_id === values.project_id)
                          ?.name ?? values.project_id}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Page type</dt>
                      <dd>
                        {values.page_type
                          ? PAGE_TYPE_LABELS[values.page_type as PageType]
                          : "Not set"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Page URL</dt>
                      <dd className="break-all">{values.page_url || "Not set"}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Content</dt>
                      <dd>
                        {summary
                          ? `${summary.word_count} words, ${summary.headings} headings (imported)`
                          : "Not imported"}
                      </dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-muted-foreground">Primary query</dt>
                      <dd>{values.primary_query || "Not set"}</dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-muted-foreground">Secondary queries</dt>
                      <dd>
                        {values.secondary_queries
                          ? values.secondary_queries
                              .split(/[\n,]+/)
                              .map((s) => s.trim())
                              .filter(Boolean)
                              .join(" · ")
                          : "None supplied — the auditor will simulate the fan-out"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Context packs</dt>
                      <dd>
                        {selectedPackDetails.length
                          ? selectedPackDetails.map((p) => `${p.name} v${p.version}`).join(", ")
                          : "None"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Source profile / sensitivity</dt>
                      <dd>
                        {SOURCE_PROFILE_LABELS[values.source_profile]} ·{" "}
                        {SENSITIVITY_TIER_LABELS[values.sensitivity]}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Depth</dt>
                      <dd>{AUDIT_DEPTH_LABELS[values.depth]}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Provider</dt>
                      <dd>
                        {values.deterministic_only
                          ? "Deterministic only (no model calls)"
                          : `${titleCase(values.provider_type)} · ${values.model || "model not set"}`}
                      </dd>
                    </div>
                  </dl>

                  <Alert variant="info" title="What the run will and will not do">
                    <ul className="list-disc space-y-1 pl-4">
                      <li>
                        Every score is an internal editorial heuristic, not an official
                        platform metric.
                      </li>
                      <li>
                        {values.deterministic_only
                          ? "Model-generated stages will be skipped; the report will say so rather than substituting an estimate."
                          : "Model-generated stages may vary between runs; origins are labelled per stage."}
                      </li>
                      <li>
                        Queries are simulated unless you supply them or connect a data source.
                      </li>
                    </ul>
                  </Alert>

                  {runError ? (
                    <ErrorState error={runError} title="Could not start the audit" />
                  ) : null}
                </CardContent>
              </Card>
            </div>
          ) : null}
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <Button
            variant="outline"
            onClick={() => setStep((s) => Math.max(1, s - 1))}
            disabled={step === 1 || runMutation.isPending}
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Back
          </Button>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground" role="status">
              Step {step} of {STEPS.length}
            </span>
            {step < STEPS.length ? (
              <Button onClick={goNext} disabled={runMutation.isPending}>
                Next <ArrowRight className="h-3.5 w-3.5" aria-hidden />
              </Button>
            ) : (
              <Button type="submit" disabled={runMutation.isPending}>
                {runMutation.isPending ? "Starting…" : "Run audit"}
              </Button>
            )}
          </div>
        </div>
      </form>

      <p className="text-xs text-muted-foreground">
        Draft states are not stored: leaving this page discards the wizard. Imported content
        versions created before you leave are kept and can be re-used.
      </p>
      <Link href="/audits" className={buttonClasses({ variant: "link", size: "sm" })}>
        <FolderOpen className="h-3.5 w-3.5" aria-hidden /> Back to all audits
      </Link>
    </div>
  );
}
