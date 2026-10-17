"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Boxes,
  CheckCircle2,
  Copy,
  Cpu,
  FolderOpen,
  Info,
  Loader2,
  Plug,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trash2,
  Zap,
} from "@/components/icons";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { QueryView } from "@/components/states";
import { HeuristicDisclaimer, SampleDataBanner } from "@/components/status";
import { API_BASE, MOCK_MODE, api, isMockMode } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { usePageTitle } from "@/lib/use-page-title";
import type { ProjectRead } from "@/lib/types";
import {
  useBrand,
  BRAND_THEMES,
  LOGO_VARIANTS,
  type BrandThemeId,
  type LogoVariantId,
} from "@/components/brand/brand-context";
import { AentioLogo } from "@/components/brand/logo";

const LIMITATIONS: Array<{ title: string; body: string }> = [
  {
    title: "Scores are an internal editorial heuristic",
    body: "EOS, ERS, KGR, FCS, PRS, CWS, HRS and the composite AVR are weighted rubric scores from the PRD. They are not Google, Bing, OpenAI, Anthropic or Perplexity metrics, and no ranking outcome is implied.",
  },
  {
    title: "Model stages are labelled simulated",
    body: "When a model provider is used, semantic stages (passage skill, claim verification drafts, relationship inference) are marked with their origin. Deterministic stages are marked observed. Nothing simulated is presented as measured fact.",
  },
  {
    title: "Fan-out queries are simulated, not live search",
    body: "Fan-out coverage answers how well the page would serve a query set derived from your primary intent. It does not query a search engine or an LLM and report real answers.",
  },
  {
    title: "Page fetching has limits",
    body: "Fetches execute no JavaScript, extract only the primary content region, and refuse private-network URLs (SSRF protection). Client-rendered pages may import with missing body text.",
  },
  {
    title: "Nothing is verified by default",
    body: "Claims are assessed against the page, the context pack and any evidence sources you supply. Verification states say what is supported, not what is true in the world.",
  },
];

export default function SettingsPage() {
  usePageTitle("Settings & Connectors");

  const [activeTab, setActiveTab] = useState("connectors");
  const { themeId, setThemeId, logoVariant, setLogoVariant, activeTheme } = useBrand();
  const [lastChecked, setLastChecked] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [maintenanceFeedback, setMaintenanceFeedback] = useState<string | null>(null);

  // Queries
  const health = useQuery({ queryKey: ["health"], queryFn: () => api.health() });
  const readiness = useQuery({ queryKey: ["readiness"], queryFn: () => api.readiness() });
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.listProjects() });
  const packs = useQuery({ queryKey: ["context-packs"], queryFn: () => api.listContextPacks() });
  const mcpTools = useQuery({ queryKey: ["mcp-tools"], queryFn: () => api.getMcpTools() });

  // Derive the effective selection: explicit choice, else the first project.
  const resolvedProjectId = selectedProjectId || projects.data?.[0]?.project_id || "";

  const selectedProject = useMemo<ProjectRead | null>(() => {
    if (!resolvedProjectId || !projects.data) return null;
    return projects.data.find((p: ProjectRead) => p.project_id === resolvedProjectId) ?? null;
  }, [resolvedProjectId, projects.data]);

  const recheck = useMutation({
    mutationFn: async () => {
      await Promise.all([health.refetch(), readiness.refetch()]);
      return new Date().toISOString();
    },
    onSuccess: (iso) => setLastChecked(iso),
  });

  const purgeMutation = useMutation({
    mutationFn: () => api.purgeTestData(),
    onSuccess: (res) => {
      setMaintenanceFeedback(res.message);
      void projects.refetch();
    },
    onError: (err) => {
      setMaintenanceFeedback(`Error: ${String(err)}`);
    },
  });

  const handleCopy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2500);
    } catch {
      // ignore clipboard error
    }
  };

  // Generate Claude Project Knowledge Context
  const claudeProjectContext = useMemo(() => {
    const p = selectedProject;
    if (!p) return "";

    return `# EntityGraph Project Knowledge & Context: ${p.name}

## 1. Project Profile & Entity Identity
- **Brand Name**: ${p.brand || p.name}
- **Primary Central Entity**: ${p.central_entity || p.name}
- **Target Audience (ICP)**: ${p.audience_icp || "Enterprise decision-makers and subject-matter experts"}
- **Industry & Domain**: ${p.industry || "Technology / Professional Services"}
- **Target Market / Geography**: ${p.country_region || p.target_market || "Global / English"}
- **Primary Conversion Goal**: ${p.target_conversion || "Organic retrieval, entity authority, and user engagement"}
- **Supported Languages**: ${(p.languages || ["en"]).join(", ")}

## 2. Entity SEO & Machine Retrieval Principles
When assisting with, reviewing, or writing content for this project, Claude must strictly enforce these retrieval standards:
1. **Answer-First Definition**: State the primary central entity ("${p.central_entity || p.name}") and its primary attribute in the opening sentence.
2. **Explicit Knowledge Triples**: Structure paragraphs with clear subject-predicate-object relationships so search crawlers and AI answer engines extract clear facts without ambiguity.
3. **Question-Based Headings (AEO)**: Include H2 headings formulated as search queries (e.g. "What is...", "How does... work?", "Why is... required?") to optimize for direct passage citations in AI search engines (Perplexity, ChatGPT Search, Gemini, Google AI Overviews).
4. **Passage Retrievability**: Ensure key explanatory passages are standalone and make sense when extracted independently.

## 3. Brand Compliance & Publication Guardrails
Zero tolerance for unverified claims or prohibited phrasing:
- Do NOT use absolute security or outcome claims (e.g. "100% unhackable", "unhackable", "miracle", "foolproof", "guaranteed #1 ranking").
- Ensure all quantitative statistics cite explicit benchmarks or operational contexts.
- Maintain professional, objective, high-clarity technical prose.

## 4. Calling EntityGraph Auditor Tools
When integrated via MCP or tool calling, invoke:
- \`run_content_audit\`: Submit the markdown draft to receive EOS (Entity Salience), ERS (Relations), KGR (Knowledge Graph Readiness), FCS (Fan-out), and PRS (Passage Retrieval) scores.
- \`analyze_entities\`: Extract candidate entities, triples, and missing EAV attributes.
- \`check_brand_compliance\`: Verify compliance against banned words and publication gates.
`;
  }, [selectedProject]);

  // Claude Desktop Config JSON
  const claudeDesktopConfig = useMemo(() => {
    return JSON.stringify(
      {
        mcpServers: {
          "entitygraph-auditor": {
            command: "/Users/sami/Desktop/Entity Scoring System/.venv/bin/python",
            args: ["-m", "ega_mcp.server"],
            env: {
              PYTHONPATH:
                "/Users/sami/Desktop/Entity Scoring System/packages/mcp:/Users/sami/Desktop/Entity Scoring System/packages/schemas:/Users/sami/Desktop/Entity Scoring System/packages/parsers:/Users/sami/Desktop/Entity Scoring System/packages/scoring:/Users/sami/Desktop/Entity Scoring System/auditor",
            },
          },
        },
      },
      null,
      2,
    );
  }, []);

  // Cursor MCP Config JSON
  const cursorMcpConfig = useMemo(() => {
    return JSON.stringify(
      {
        mcpServers: {
          "entitygraph-auditor": {
            command: "/Users/sami/Desktop/Entity Scoring System/.venv/bin/python",
            args: ["-m", "ega_mcp.server"],
          },
        },
      },
      null,
      2,
    );
  }, []);

  // OpenAI Custom GPT Actions Schema snippet
  const openApiActionSchema = useMemo(() => {
    return JSON.stringify(
      {
        openapi: "3.1.0",
        info: {
          title: "EntityGraph Auditor API",
          description: "Entity SEO, AEO and AI search retrieval auditor",
          version: "0.1.0",
        },
        servers: [{ url: `${API_BASE}/api/v1` }],
        paths: {
          "/audits": {
            post: {
              operationId: "runContentAudit",
              summary: "Execute an entity and machine retrieval audit",
              requestBody: {
                required: true,
                content: {
                  "application/json": {
                    schema: {
                      type: "object",
                      required: ["project_id", "primary_query"],
                      properties: {
                        project_id: { type: "string" },
                        primary_query: { type: "string" },
                        content_text: { type: "string" },
                        page_type: { type: "string" },
                      },
                    },
                  },
                },
              },
              responses: {
                "201": {
                  description: "Audit created and queued",
                  content: {
                    "application/json": {
                      schema: {
                        type: "object",
                        properties: {
                          audit_id: { type: "string" },
                          status: { type: "string" },
                        },
                      },
                    },
                  },
                },
              },
            },
          },
        },
      },
      null,
      2,
    );
  }, []);

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-xl font-bold tracking-tight">Settings &amp; AI Connectors</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Connect your Claude Pro, ChatGPT, Grok, and IDE workflows to EntityGraph, manage local runtime status, and clean database garbage.
        </p>
      </div>

      {isMockMode() ? <SampleDataBanner /> : null}

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid grid-cols-5 w-full max-w-3xl h-9">
          <TabsTrigger value="connectors" className="flex items-center gap-1.5 text-xs">
            <Plug className="h-3.5 w-3.5" /> AI Connectors
          </TabsTrigger>
          <TabsTrigger value="branding" className="flex items-center gap-1.5 text-xs">
            <Sparkles className="h-3.5 w-3.5" /> Brand &amp; Identity
          </TabsTrigger>
          <TabsTrigger value="maintenance" className="flex items-center gap-1.5 text-xs">
            <Trash2 className="h-3.5 w-3.5" /> Maintenance
          </TabsTrigger>
          <TabsTrigger value="status" className="flex items-center gap-1.5 text-xs">
            <RefreshCw className="h-3.5 w-3.5" /> System Status
          </TabsTrigger>
          <TabsTrigger value="disclaimers" className="flex items-center gap-1.5 text-xs">
            <Info className="h-3.5 w-3.5" /> Rubric Disclaimers
          </TabsTrigger>
        </TabsList>

        {/* ------------------------------------------------ TAB 1: CONNECTORS */}
        <TabsContent value="connectors" className="space-y-5">
          {/* Claude Pro Integration Card */}
          <Card className="border shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <div>
                    <CardTitle className="text-base font-semibold">Claude Pro Connector (Desktop &amp; Projects)</CardTitle>
                    <CardDescription className="text-xs">
                      Equip Claude with your project context, brand boundaries, and tool-calling capabilities.
                    </CardDescription>
                  </div>
                </div>
                <Badge variant="outline" className="text-xs font-semibold text-amber-600 border-amber-500/30">
                  Anthropic Claude
                </Badge>
              </div>
            </CardHeader>

            <CardContent className="space-y-5 text-xs">
              {/* Option A: Claude Projects & Chat Windows */}
              <div className="p-4 rounded-lg border bg-card/60 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                      <FolderOpen className="h-4 w-4 text-primary" />
                      Method 1: Claude Projects &amp; Chat Windows (Project Knowledge Pack)
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Select any project from your workspace. We format an optimized Project Context Pack ready to paste directly into your Claude Project instructions or chat window.
                    </p>
                  </div>

                  {/* Project Selector */}
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-muted-foreground">Active Project:</span>
                    <select
                      value={resolvedProjectId}
                      onChange={(e) => setSelectedProjectId(e.target.value)}
                      className="h-8 text-xs rounded-md border border-input bg-background px-2 font-medium"
                    >
                      {projects.data?.map((p: ProjectRead) => (
                        <option key={p.project_id} value={p.project_id}>
                          {p.name} {p.brand ? `(${p.brand})` : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Prompt Preview Box */}
                <div className="relative">
                  <pre className="p-3 rounded-md bg-muted/40 border font-mono text-[11px] leading-relaxed max-h-48 overflow-y-auto whitespace-pre-wrap">
                    {claudeProjectContext}
                  </pre>
                  <div className="absolute top-2 right-2 flex gap-1.5">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleCopy("claude-project", claudeProjectContext)}
                      className="h-7 text-xs bg-background/90 backdrop-blur shadow-xs"
                    >
                      {copiedKey === "claude-project" ? (
                        <>
                          <CheckCircle2 className="h-3 w-3 mr-1 text-emerald-500" /> Copied!
                        </>
                      ) : (
                        <>
                          <Copy className="h-3 w-3 mr-1" /> Copy Project Context
                        </>
                      )}
                    </Button>
                  </div>
                </div>

                <div className="text-[11px] text-muted-foreground bg-muted/20 p-2.5 rounded border flex items-start gap-2">
                  <Info className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>
                    <strong>How to use in Claude:</strong> Open Claude.ai &gt; Projects &gt; Your Project &gt; Click <em>Set Custom Instructions</em> &gt; Paste this text. Claude will immediately adhere to this project&apos;s central entity, brand facts, banned words, and passage retrievability standards.
                  </span>
                </div>
              </div>

              {/* Option B: Claude Desktop MCP Integration */}
              <div className="p-4 rounded-lg border bg-card/60 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                      <Cpu className="h-4 w-4 text-primary" />
                      Method 2: Claude Desktop (Model Context Protocol / MCP)
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Run the local-first MCP server so Claude Desktop can natively call <code className="font-mono text-[10px]">run_content_audit</code>, <code className="font-mono text-[10px]">analyze_entities</code>, and <code className="font-mono text-[10px]">check_brand_compliance</code>.
                    </p>
                  </div>

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleCopy("claude-mcp", claudeDesktopConfig)}
                    className="h-7 text-xs"
                  >
                    {copiedKey === "claude-mcp" ? (
                      <>
                        <CheckCircle2 className="h-3 w-3 mr-1 text-emerald-500" /> Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3 mr-1" /> Copy MCP Config
                      </>
                    )}
                  </Button>
                </div>

                <pre className="p-3 rounded-md bg-muted/40 border font-mono text-[11px] leading-relaxed max-h-36 overflow-y-auto">
                  {claudeDesktopConfig}
                </pre>

                <p className="text-[11px] text-muted-foreground">
                  Paste this into <code className="font-mono bg-muted px-1 py-0.5 rounded">~/Library/Application Support/Claude/claude_desktop_config.json</code> and restart Claude Desktop. The hammer icon in Claude will reveal the 4 official EntityGraph audit tools.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* ChatGPT, Grok & IDE Integrations */}
          <div className="grid gap-4 lg:grid-cols-2">
            {/* ChatGPT Custom GPT Action */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
                    <Zap className="h-4 w-4 text-emerald-500" />
                    ChatGPT (Custom GPT Actions)
                  </CardTitle>
                  <Badge variant="outline" className="text-xs">OpenAI</Badge>
                </div>
                <CardDescription className="text-xs">
                  Connect ChatGPT Plus/Team to your self-hosted API via OpenAPI Actions.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                <p className="text-muted-foreground">
                  Create a custom GPT in ChatGPT and import the OpenAPI schema to let ChatGPT trigger audits directly from your chats.
                </p>

                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[11px] truncate text-muted-foreground">
                    {API_BASE}/api/v1/openapi.json
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleCopy("chatgpt-schema", openApiActionSchema)}
                    className="h-7 text-xs"
                  >
                    {copiedKey === "chatgpt-schema" ? (
                      <>
                        <CheckCircle2 className="h-3 w-3 mr-1 text-emerald-500" /> Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3 mr-1" /> Copy OpenAPI Spec
                      </>
                    )}
                  </Button>
                </div>

                <ol className="list-decimal list-inside space-y-1 text-muted-foreground text-[11px]">
                  <li>In ChatGPT, navigate to <strong>Explore GPTs &gt; Create</strong>.</li>
                  <li>Under <strong>Configure &gt; Actions</strong>, choose <em>Create new action</em>.</li>
                  <li>Paste the OpenAPI JSON and save your Custom GPT.</li>
                </ol>
              </CardContent>
            </Card>

            {/* Cursor / Windsurf / Claude Code */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
                    <Boxes className="h-4 w-4 text-cyan-500" />
                    Cursor, Windsurf &amp; Claude Code
                  </CardTitle>
                  <Badge variant="outline" className="text-xs">IDE MCP</Badge>
                </div>
                <CardDescription className="text-xs">
                  Run entity &amp; retrieval checks inside your IDE agent workflows.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                <p className="text-muted-foreground">
                  Add EntityGraph Auditor to <code className="font-mono text-[10px]">~/.cursor/mcp.json</code> or your Windsurf/Claude Code config:
                </p>

                <div className="relative">
                  <pre className="p-2.5 rounded-md bg-muted/40 border font-mono text-[11px] overflow-x-auto">
                    {cursorMcpConfig}
                  </pre>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleCopy("cursor-mcp", cursorMcpConfig)}
                    className="absolute top-2 right-2 h-6 text-[10px]"
                  >
                    {copiedKey === "cursor-mcp" ? "Copied!" : "Copy"}
                  </Button>
                </div>

                <p className="text-[11px] text-muted-foreground">
                  Or via CLI: <code className="font-mono bg-muted px-1 py-0.5 rounded">claude mcp add entitygraph python -m ega_mcp.server</code>
                </p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ------------------------------------------------ TAB 2: BRAND & IDENTITY */}
        <TabsContent value="branding" className="space-y-5">
          <Card className="border shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-md bg-primary/10 text-primary">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <div>
                    <CardTitle className="text-base font-semibold">Brand Identity &amp; Aesthetic Engine</CardTitle>
                    <CardDescription className="text-xs">
                      Customize your workspace color palette, typography accents, and vector emblem marks.
                    </CardDescription>
                  </div>
                </div>
                <Badge variant="outline" className="text-xs font-semibold text-primary border-primary/30">
                  {activeTheme.name}
                </Badge>
              </div>
            </CardHeader>

            <CardContent className="space-y-6 text-xs">
              {/* Active Brand Live Preview Card */}
              <div className="p-4 rounded-xl border bg-muted/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <AentioLogo size={36} showText={true} />
                  <div className="h-8 w-px bg-border hidden sm:block" />
                  <div className="flex flex-col">
                    <span className="font-semibold text-foreground text-xs">{activeTheme.name} Palette</span>
                    <span className="text-[11px] text-muted-foreground">{activeTheme.tagline}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 self-end sm:self-center">
                  <span className="px-2 py-1 rounded bg-background border font-mono text-[11px] font-semibold text-foreground">
                    Primary: {activeTheme.primary}
                  </span>
                  <span className="w-5 h-5 rounded-full border shadow-xs" style={{ backgroundColor: activeTheme.primary }} />
                </div>
              </div>

              {/* 1. Color Palettes Selection */}
              <div className="space-y-3">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    1. Brand Color Palettes
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Select a color scheme that aligns with your brand. Changes take effect across buttons, active tabs, scores, and badges.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {(Object.keys(BRAND_THEMES) as BrandThemeId[]).map((key) => {
                    const theme = BRAND_THEMES[key];
                    const isSelected = themeId === key;
                    return (
                      <div
                        key={key}
                        onClick={() => setThemeId(key)}
                        className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-start gap-3 relative ${
                          isSelected
                            ? "bg-card border-primary ring-2 ring-primary/20 shadow-xs"
                            : "bg-card/60 hover:bg-card border-border hover:border-primary/40"
                        }`}
                      >
                        <span
                          className="w-8 h-8 rounded-lg shrink-0 mt-0.5 shadow-xs flex items-center justify-center text-white"
                          style={{ backgroundColor: theme.primary }}
                        >
                          {isSelected ? <CheckCircle2 className="h-4 w-4" /> : null}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-semibold text-foreground text-xs">{theme.name}</span>
                            <span className="font-mono text-[10px] text-muted-foreground">{theme.primary}</span>
                          </div>
                          <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">
                            {theme.tagline}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 2. Emblem Mark Selection */}
              <div className="space-y-3 pt-2">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    2. Vector Emblem &amp; Logo Marks
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Select the architectural emblem used in the topbar header and documentation exports.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {(Object.keys(LOGO_VARIANTS) as LogoVariantId[]).map((vKey) => {
                    const variant = LOGO_VARIANTS[vKey];
                    const isSelected = logoVariant === vKey;
                    return (
                      <div
                        key={vKey}
                        onClick={() => setLogoVariant(vKey)}
                        className={`p-3.5 rounded-xl border cursor-pointer transition-all flex flex-col gap-2.5 relative ${
                          isSelected
                            ? "bg-card border-primary ring-2 ring-primary/20 shadow-xs"
                            : "bg-card/60 hover:bg-card border-border hover:border-primary/40"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <AentioLogo size={28} showText={false} variant={vKey} />
                          {isSelected ? (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-primary/10 text-primary">
                              Active
                            </span>
                          ) : null}
                        </div>
                        <div>
                          <span className="font-semibold text-foreground text-xs block">{variant.name}</span>
                          <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">
                            {variant.description}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ------------------------------------------------ TAB 3: MAINTENANCE */}
        <TabsContent value="maintenance" className="space-y-4">
          <Card className="border shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-red-500/10 text-red-500">
                  <Trash2 className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle className="text-base font-semibold">Database Maintenance &amp; Cleanup</CardTitle>
                  <CardDescription className="text-xs">
                    Purge automated smoke test runs, sample artifacts, and reclaim SQLite database storage.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4 text-xs">
              <div className="p-3 rounded-lg border bg-muted/20 space-y-2">
                <p className="text-sm font-medium text-foreground">Purge Test Workspaces &amp; Garbage Data</p>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  During development and automated test sweeps, test projects (prefixed with <code>smoke-</code>, <code>test-</code>, <code>demo-</code>, or <code>fixture-</code>) accumulate along with their audit runs, content versions, and logs. Clicking below will purge all test workspaces and run SQLite <code>VACUUM</code> to shrink database file size.
                </p>
              </div>

              {maintenanceFeedback ? (
                <Alert variant="default" title="Maintenance Result">
                  {maintenanceFeedback}
                </Alert>
              ) : null}

              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => purgeMutation.mutate()}
                  disabled={purgeMutation.isPending}
                >
                  {purgeMutation.isPending ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Purging…
                    </>
                  ) : (
                    <>
                      <Trash2 className="h-3.5 w-3.5 mr-1" /> Purge Test Garbage &amp; Vacuum DB
                    </>
                  )}
                </Button>

                <span className="text-xs text-muted-foreground">
                  Active projects: <strong>{projects.data?.length ?? 0}</strong> · Packs: <strong>{packs.data?.length ?? 0}</strong> · MCP tools: <strong>{mcpTools.data?.tools?.length ?? 0}</strong>
                </span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ------------------------------------------------ TAB 3: SYSTEM STATUS */}
        <TabsContent value="status" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <RefreshCw className="h-4 w-4 text-muted-foreground" aria-hidden />
                  API status
                </CardTitle>
                <CardDescription>Live health and readiness of the backend.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <QueryView query={health} loadingLabel="Checking health…" errorTitle="Health check failed">
                  {(status) => (
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      <Badge variant={status.status === "ok" ? "success" : "warning"}>
                        <span aria-hidden="true">{status.status === "ok" ? "✓" : "!"}</span>
                        {status.status === "ok" ? "Healthy" : status.status}
                      </Badge>
                      <span className="text-muted-foreground">version {status.version}</span>
                    </div>
                  )}
                </QueryView>

                <QueryView query={readiness} loadingLabel="Checking readiness…" errorTitle="Readiness check failed">
                  {(status) => (
                    <div className="space-y-2">
                      <Badge variant={status.status === "ready" ? "success" : "warning"}>
                        <span aria-hidden="true">{status.status === "ready" ? "✓" : "!"}</span>
                        {status.status === "ready" ? "Ready" : status.status}
                      </Badge>
                      <dl className="grid grid-cols-3 gap-2 text-sm">
                        {Object.entries(status.checks).map(([key, value]) => {
                          const check = value as { ok?: boolean; detail?: string; status?: string };
                          const display =
                            typeof value === "object" && value !== null
                              ? `${check.ok ? "✓" : "✕"} ${check.detail ?? check.status ?? "ok"}`
                              : String(value);
                          return (
                            <div key={key}>
                              <dt className="text-xs capitalize text-muted-foreground">{key}</dt>
                              <dd className="text-xs">{display}</dd>
                            </div>
                          );
                        })}
                      </dl>
                    </div>
                  )}
                </QueryView>

                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => recheck.mutate()}
                    disabled={recheck.isPending}
                  >
                    <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                    {recheck.isPending ? "Checking…" : "Re-check"}
                  </Button>
                  {lastChecked ? (
                    <span className="text-xs text-muted-foreground">
                      Last checked {formatDateTime(lastChecked)}
                    </span>
                  ) : null}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <ShieldCheck className="h-4 w-4 text-muted-foreground" aria-hidden />
                  Data handling &amp; Privacy
                </CardTitle>
                <CardDescription>What is stored, where it goes, and how to remove it.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <dl className="space-y-3">
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">API base</dt>
                    <dd className="font-mono text-xs break-all">{API_BASE}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Mode</dt>
                    <dd className="text-sm">
                      {MOCK_MODE ? (
                        <Badge variant="sample">
                          <span aria-hidden="true">◆</span> Mock fixtures — no backend required
                        </Badge>
                      ) : (
                        <Badge variant="secondary">Live backend</Badge>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      What leaves your machine
                    </dt>
                    <dd className="text-sm text-muted-foreground">
                      Only when you choose an optional cloud provider. Local and deterministic providers keep page text on this machine.
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Retention &amp; Deletion
                    </dt>
                    <dd className="text-sm text-muted-foreground">
                      Audits and projects are stored server-side until you delete them. Deleting a project cascades all associated audits and snapshots.
                    </dd>
                  </div>
                </dl>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ------------------------------------------------ TAB 4: RUBRIC DISCLAIMERS */}
        <TabsContent value="disclaimers" className="space-y-4">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">
                What this tool does and does not claim
              </h2>
              <p className="text-sm text-muted-foreground">
                Read this before quoting a score to a client or stakeholder.
              </p>
            </div>
            <HeuristicDisclaimer />
          </div>

          <ul className="grid gap-3 md:grid-cols-2">
            {LIMITATIONS.map((item) => (
              <li key={item.title}>
                <Card className="h-full">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <Info className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                      {item.title}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-sm text-muted-foreground">{item.body}</CardContent>
                </Card>
              </li>
            ))}
          </ul>

          <Alert variant="default" title="Scoring profile">
            Scores are produced by the weighted rubric in the PRD (§9) under the profile recorded on
            each audit. Changing weights requires a new score profile version — existing reports keep
            the profile they were generated with, and the compare page warns when two runs used
            different profiles.
          </Alert>
        </TabsContent>
      </Tabs>
    </div>
  );
}
