"use client";

import * as React from "react";
import { useState, useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CompareResponse, EntityChangeItem, ScoreDelta } from "@/lib/types";
import { HeuristicDisclaimer } from "@/components/status";

interface GeoApiResponse {
  success: boolean;
  availableBrands: Array<{ id: string; name: string; domain: string }>;
  data: {
    brand: { id: string; name: string; domain: string; aliases: string[] };
    summary: {
      totalPrompts: number;
      totalRuns: number;
      totalCitations: number;
      brandCitations: number;
      avgMentionRate: number;
      citationProbability: number;
      wilsonInterval: [number, number];
      effectiveVisibilityIndex: number;
      netStanceScore: number;
      volatility: number;
    };
    csov: {
      targetBrand: string;
      totalMarketCitations: number;
      totalCompetitiveCitations: number;
      editorialCitations: number;
      editorialDilutionRate: number;
      brandMarketShare: number;
      brandCompetitiveCSoV: number;
      smoothedBrandCompetitiveCSoV: number;
      brandProminenceWeightedCSoV: number;
      credenceWeight: number;
      entities: Array<{
        name: string;
        citations: number;
        marketSharePercentage: number;
        competitiveCSoVPercentage: number;
        smoothedCompetitiveCSoVPercentage: number;
        prominenceWeightedCSoVPercentage: number;
        topDomains?: string[];
        netStanceScore?: number;
      }>;
    };
    prompts: Array<{
      id: string;
      query: string;
      intent: string;
      persona: string;
      runsCount: number;
      citationProbability: number;
      wilsonInterval: [number, number];
      evi: number;
      netStance: number;
      volatility: number;
      sampleAnswer: string;
      engines: string[];
      subQueries: string[];
    }>;
    alignments: Array<{
      id: string;
      passageText: string;
      heading: string;
      similarityScore: number;
      citationId: string;
      rank: number;
    }>;
    runs: Array<{
      id: string;
      engine: string;
      promptId: string;
      responseText: string;
      subQueries: string[];
      executionMs: number;
      createdAt: string;
    }>;
  };
}

/** Human-readable label for an entity change that may be a bare id or a rich item. */
function entityChangeLabel(item: string | EntityChangeItem): string {
  if (typeof item === "string") return item;
  const parts = [item.label ?? item.id, item.field, item.kind].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : JSON.stringify(item);
}

/** Signed delta with a direction glyph; `null` baseline/candidate means n/a. */
function DeltaValue({ delta }: { delta: number | null | undefined }) {
  if (delta === null || delta === undefined) {
    return <span className="text-muted-foreground">n/a</span>;
  }
  const tone = delta > 0 ? "text-emerald-700" : delta < 0 ? "text-rose-700" : "text-muted-foreground";
  const glyph = delta > 0 ? "▲" : delta < 0 ? "▼" : "—";
  return (
    <span className={`font-code-data font-semibold ${tone}`}>
      {glyph} {delta > 0 ? "+" : ""}
      {delta.toFixed(1)}
    </span>
  );
}

export default function AiVisibilityPrismGeoPage() {
  const [activeTab, setActiveTab] = useState<"visibility" | "csov" | "citations" | "transcripts" | "compare">("visibility");
  const [selectedBrandId, setSelectedBrandId] = useState<string>("");
  const [selectedQueryId, setSelectedQueryId] = useState<string>("");
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [intentFilter, setIntentFilter] = useState<string>("All Intents");
  const [runningCrawl, setRunningCrawl] = useState<boolean>(false);
  const [showAddPromptModal, setShowAddPromptModal] = useState<boolean>(false);
  const [crawlNotice, setCrawlNotice] = useState<string>("");
  const [newPromptDraft, setNewPromptDraft] = useState<{ query: string; intent: string; persona: string }>({
    query: "",
    intent: "Commercial",
    persona: "agency_executive",
  });
  const [localPromptDrafts, setLocalPromptDrafts] = useState<
    Array<{ id: string; query: string; intent: string; persona: string }>
  >([]);

  // Audits query for the Compare tab
  const auditsQuery = useQuery({
    queryKey: ["audits"],
    queryFn: () => api.listAudits(),
  });

  const [baselineAuditId, setBaselineAuditId] = useState<string>("");
  const [candidateAuditId, setCandidateAuditId] = useState<string>("");

  // Real audit-comparison call (POST /api/v1/audits/compare). Only runs once
  // both runs are chosen, so the tab never shows a fabricated delta.
  const compareQuery = useQuery<CompareResponse>({
    queryKey: ["audit-compare", baselineAuditId, candidateAuditId],
    enabled: Boolean(baselineAuditId && candidateAuditId),
    queryFn: () => api.compareAudits(baselineAuditId, candidateAuditId),
  });

  // Live query from Next.js PrismGEO API route
  const geoQuery = useQuery<GeoApiResponse>({
    queryKey: ["prism-geo-visibility", selectedBrandId],
    queryFn: async () => {
      const url = selectedBrandId
        ? `/api/visibility?brandId=${encodeURIComponent(selectedBrandId)}`
        : "/api/visibility";
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to fetch PrismGEO data");
      return res.json();
    },
  });

  const availableBrands = geoQuery.data?.availableBrands ?? [];
  const geoData = geoQuery.data?.data;

  // Derive active prompt without setState in effect
  const activePromptId = selectedQueryId || geoData?.prompts?.[0]?.id || "";

  const selectedPrompt = useMemo(() => {
    if (!geoData?.prompts?.length) return null;
    return geoData.prompts.find((p) => p.id === activePromptId) ?? geoData.prompts[0];
  }, [geoData, activePromptId]);

  const filteredPrompts = useMemo(() => {
    if (!geoData?.prompts) return [];
    return geoData.prompts.filter((p) => {
      const matchIntent = intentFilter === "All Intents" || p.intent.toLowerCase() === intentFilter.toLowerCase();
      const matchSearch =
        !searchFilter ||
        p.query.toLowerCase().includes(searchFilter.toLowerCase()) ||
        p.persona.toLowerCase().includes(searchFilter.toLowerCase());
      return matchIntent && matchSearch;
    });
  }, [geoData, intentFilter, searchFilter]);

  const handleTriggerCrawl = async () => {
    setRunningCrawl(true);
    try {
      await fetch("/api/visibility", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "crawl", brandId: selectedBrandId }),
      });
      // Re-read the visibility query and report only what actually came back.
      const result = await geoQuery.refetch();
      const prompts = result.data?.data?.prompts ?? [];
      setCrawlNotice(
        `Reloaded ${prompts.length} prompt${prompts.length === 1 ? "" : "s"} from the local dataset — no live engine runs were executed.`
      );
    } catch {
      setCrawlNotice("Reload failed — could not re-read the local visibility dataset.");
    } finally {
      setRunningCrawl(false);
    }
  };

  const handleAddPrompt = (e: React.FormEvent) => {
    e.preventDefault();
    const query = newPromptDraft.query.trim();
    if (!query) return;
    setLocalPromptDrafts((prev) => [
      ...prev,
      {
        id: `local-prompt-${Date.now()}`,
        query,
        intent: newPromptDraft.intent,
        persona: newPromptDraft.persona,
      },
    ]);
    setNewPromptDraft({ query: "", intent: "Commercial", persona: "agency_executive" });
    setShowAddPromptModal(false);
  };

  const handleExportCsv = () => {
    if (!geoData) return;
    const rows = [
      ["Prompt Query", "Intent", "Persona", "Citation Probability", "Wilson 95% CI Lower", "Wilson 95% CI Upper", "EVI", "Net Stance Score"],
      ...geoData.prompts.map((p) => [
        `"${p.query.replace(/"/g, '""')}"`,
        p.intent,
        p.persona,
        p.citationProbability,
        p.wilsonInterval[0],
        p.wilsonInterval[1],
        p.evi,
        p.netStance,
      ]),
    ];
    const csvContent = "data:text/csv;charset=utf-8," + rows.map((e) => e.join(",")).join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `prismgeo-visibility-${geoData.brand.name.toLowerCase().replace(/\s+/g, "-")}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="flex flex-col w-full min-h-[calc(100vh-52px)] bg-background-canvas">
      {/* ------------------------------------------------------------- TOP COMMAND & BRAND SELECTOR */}
      <div className="px-6 py-4 bg-surface border-b border-border-hairline select-none">
        <div className="flex items-center justify-between w-full mb-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>Workspace</span>
            <span className="material-symbols-outlined text-[13px]">chevron_right</span>
            <span className="text-foreground font-medium">AI Visibility</span>
            <span className="h-3 w-px bg-border-hairline mx-1" />

            {/* Brand Switcher connected to PrismGEO */}
            <div className="relative flex items-center">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse mr-1.5" />
              <select
                value={selectedBrandId || geoData?.brand?.id || ""}
                onChange={(e) => setSelectedBrandId(e.target.value)}
                className="h-7 text-xs font-semibold rounded px-2 pr-6 bg-surface-subtle border border-border-hairline text-foreground hover:bg-surface transition-colors cursor-pointer focus:outline-none focus:ring-1 focus:ring-primary"
              >
                {availableBrands.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name} ({b.domain})
                  </option>
                ))}
              </select>
              <span className="material-symbols-outlined text-[14px] text-muted-foreground absolute right-1.5 pointer-events-none">
                expand_more
              </span>
            </div>

            <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 font-code-data text-[10px] font-bold">
              PrismGEO Engine Active
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleExportCsv}
              className="inline-flex items-center gap-1.5 px-3 h-8 rounded-lg border border-border-hairline bg-surface hover:bg-surface-subtle text-foreground text-xs font-medium transition-colors shadow-xs"
              title="Export RFC 4180 CSV"
            >
              <span className="material-symbols-outlined text-[15px] text-muted-foreground">file_download</span>
              <span className="hidden sm:inline">Export CSV</span>
            </button>
            <button
              type="button"
              onClick={handleTriggerCrawl}
              disabled={runningCrawl}
              className="inline-flex items-center gap-1.5 px-3 h-8 rounded-lg border border-border-hairline bg-surface hover:bg-surface-subtle text-foreground text-xs font-medium transition-colors shadow-xs"
            >
              <span className={`material-symbols-outlined text-[15px] ${runningCrawl ? "animate-spin text-primary" : "text-muted-foreground"}`}>
                refresh
              </span>
              <span>{runningCrawl ? "Reloading metrics..." : "Reload metrics"}</span>
            </button>
            <button
              type="button"
              onClick={() => setShowAddPromptModal(true)}
              className="inline-flex items-center gap-1.5 px-3 h-8 rounded-lg bg-primary hover:bg-primary-hover text-white text-xs font-medium transition-colors shadow-xs"
            >
              <span className="material-symbols-outlined text-[16px]">add</span>
              <span>Add prompt</span>
            </button>
          </div>
        </div>

        {crawlNotice && (
          <div
            role="status"
            className="mb-3 inline-flex items-start gap-1.5 rounded-lg border border-border-hairline bg-surface-subtle px-3 py-1.5 text-xs text-foreground shadow-xs"
          >
            <span className="material-symbols-outlined text-[14px] text-muted-foreground mt-px">info</span>
            <span>{crawlNotice}</span>
          </div>
        )}

        {/* Title and Subtitle Block */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-2 pb-2">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="font-sans text-xl font-bold tracking-tight text-foreground">
                AI Visibility & Reverse-RAG Observability
              </h1>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] bg-primary-soft text-primary font-bold uppercase tracking-wider border border-primary/20">
                PrismGEO Suite
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5 max-w-3xl">
              Probabilistic Monte Carlo sampling ($N \ge 10$) across Perplexity, ChatGPT Search, Claude 3.5, Google AI Overviews & Microsoft Copilot.
              Calibrated exponential prominence decay ($\lambda = 1.189$), Yates-corrected Wilson 95% confidence intervals, and Cosine TF-IDF reverse-RAG matching.
            </p>
          </div>
        </div>

        {/* Sub-Tabs: Visibility Matrix, Share of Voice, Citations, Transcripts, Audit Diff */}
        <div className="flex items-center gap-1 mt-3 overflow-x-auto text-xs border-t border-border-hairline pt-2">
          {[
            { id: "visibility", label: "Visibility & EVI Matrix", icon: "layers", count: geoData?.prompts?.length },
            { id: "csov", label: "Share of Voice (CSoV)", icon: "pie_chart", count: geoData?.csov?.entities?.length },
            { id: "citations", label: "Reverse-RAG Citations", icon: "link", count: geoData?.summary?.totalCitations },
            { id: "transcripts", label: "Responses & Fan-Out Trees", icon: "account_tree", count: geoData?.runs?.length },
            { id: "compare", label: "Audit Run Diff", icon: "compare_arrows" },
          ].map((tab) => {
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all whitespace-nowrap ${
                  active
                    ? "bg-foreground text-background-canvas font-semibold shadow-xs"
                    : "text-muted-foreground hover:bg-surface-subtle hover:text-foreground"
                }`}
              >
                <span className="material-symbols-outlined text-[16px]">{tab.icon}</span>
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span
                    className={`font-code-data text-[10px] px-1 py-0.2 rounded ${
                      active ? "bg-white/20 text-white" : "bg-surface-subtle text-muted-foreground border border-border-hairline"
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ------------------------------------------------------------- LOCAL PROMPT DRAFTS (in-memory only) */}
      {localPromptDrafts.length > 0 && (
        <div className="px-6 pt-3" data-testid="local-prompt-drafts">
          <div className="rounded-xl border border-dashed border-border-hairline bg-surface-subtle/50 p-3 space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
              <span className="material-symbols-outlined text-[15px] text-muted-foreground">edit_note</span>
              <span>
                {localPromptDrafts.length} local prompt draft
                {localPromptDrafts.length === 1 ? "" : "s"} · session only
              </span>
            </div>
            <ul className="space-y-1">
              {localPromptDrafts.map((draft) => (
                <li key={draft.id} className="text-xs font-code-data text-muted-foreground truncate">
                  {draft.query}
                  <span className="text-[10px]">
                    {" "}
                    · {draft.intent} · {draft.persona.replace(/_/g, " ")}
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-[10px] text-muted-foreground">
              Held in this page&apos;s memory only — not saved to a provider, queue, or database.
            </p>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- ENTERPRISE METRICS CARDS */}
      <div className="px-6 py-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* Card 1: Mention Rate & Wilson 95% Interval */}
          <div className="bg-surface border border-border-hairline rounded-xl p-3 flex flex-col justify-between shadow-xs">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
              Mention Rate & Wilson 95% CI
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold font-code-data text-foreground">
                {geoData ? Math.round(geoData.summary.avgMentionRate * 100) : 0}%
              </span>
              <span className="text-[11px] font-code-data text-muted-foreground">
                [{geoData ? Math.round(geoData.summary.wilsonInterval[0] * 100) : 0}%,{" "}
                {geoData ? Math.round(geoData.summary.wilsonInterval[1] * 100) : 0}%]
              </span>
            </div>
            <div className="w-full bg-surface-subtle h-1.5 rounded-full overflow-hidden mt-2">
              <div
                className="bg-primary h-1.5 rounded-full"
                style={{ width: `${Math.round((geoData?.summary?.avgMentionRate || 0) * 100)}%` }}
              />
            </div>
          </div>

          {/* Card 2: Effective Visibility Index (EVI) */}
          <div className="bg-surface border border-border-hairline rounded-xl p-3 flex flex-col justify-between shadow-xs">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
              Effective Visibility Index (EVI)
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold font-code-data text-primary">
                {geoData?.summary?.effectiveVisibilityIndex.toFixed(2) || "0.00"}
              </span>
              <span className="text-[11px] font-code-data text-muted-foreground">
                P(M) × Prominence
              </span>
            </div>
            <span className="text-[10px] text-muted-foreground mt-1">
              Unconditional expected user prominence
            </span>
          </div>

          {/* Card 3: Competitive CSoV */}
          <div className="bg-surface border border-border-hairline rounded-xl p-3 flex flex-col justify-between shadow-xs">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
              Competitive CSoV
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold font-code-data text-emerald-700">
                {geoData?.csov?.brandCompetitiveCSoV.toFixed(1) || "0.0"}%
              </span>
              <span className="text-[11px] font-code-data text-muted-foreground">
                (Smoothed {geoData?.csov?.smoothedBrandCompetitiveCSoV.toFixed(1)}%)
              </span>
            </div>
            <span className="text-[10px] text-emerald-800 bg-emerald-50 px-1 py-0.5 rounded border border-emerald-200 w-fit mt-1">
              Vs. Direct Market Rivals
            </span>
          </div>

          {/* Card 4: Editorial Dilution Rate */}
          <div className="bg-surface border border-border-hairline rounded-xl p-3 flex flex-col justify-between shadow-xs">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
              Editorial Dilution Rate
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold font-code-data text-amber-700">
                {geoData?.csov?.editorialDilutionRate.toFixed(1) || "0.0"}%
              </span>
              <span className="text-[11px] text-muted-foreground">
                {geoData?.csov?.editorialCitations || 0} citations
              </span>
            </div>
            <span className="text-[10px] text-muted-foreground mt-1 truncate">
              G2, Capterra, Reddit, Forbes, Directory
            </span>
          </div>

          {/* Card 5: Sample Runs Analyzed */}
          <div className="bg-surface border border-border-hairline rounded-xl p-3 flex flex-col justify-between shadow-xs">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
              Analyzed Monte Carlo Runs
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold font-code-data text-foreground">
                {geoData?.summary?.totalRuns || 0}
              </span>
              <span className="text-[11px] text-muted-foreground">
                across {geoData?.summary?.totalPrompts || 0} prompts
              </span>
            </div>
            <span className="text-[10px] text-muted-foreground mt-1 font-code-data">
              5 Generative Search Engines
            </span>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------- TAB 1: VISIBILITY & EVI MATRIX */}
      {activeTab === "visibility" && (
        <div className="px-6 pb-8 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Main Table Column (8 cols) */}
          <div className="lg:col-span-7 xl:col-span-8 flex flex-col gap-2 w-full">
            {/* Filter controls */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 bg-surface p-2.5 rounded-t-xl border border-border-hairline">
              <div className="relative w-full sm:w-80">
                <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[15px] text-muted-foreground">
                  search
                </span>
                <input
                  type="text"
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  placeholder="Filter buyer dilemma prompts..."
                  className="w-full h-8 pl-8 pr-3 rounded bg-surface-subtle border border-border-hairline text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:bg-surface focus:border-primary transition-all"
                />
              </div>

              <div className="flex items-center gap-1.5 overflow-x-auto text-xs">
                {["All Intents", "Commercial", "Pricing", "Alternative", "Direct"].map((int) => (
                  <button
                    key={int}
                    type="button"
                    onClick={() => setIntentFilter(int)}
                    className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                      intentFilter === int
                        ? "bg-surface text-foreground shadow-xs border border-border-hairline font-bold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {int}
                  </button>
                ))}
              </div>
            </div>

            {/* Table */}
            <div className="w-full overflow-x-auto bg-surface border-x border-b border-border-hairline rounded-b-xl shadow-xs">
              <table className="w-full text-left border-collapse text-xs min-w-[720px]">
                <thead>
                  <tr className="bg-surface-subtle text-muted-foreground border-b border-border-hairline font-medium text-[10px] uppercase select-none">
                    <th className="py-2.5 px-3">ICP Dilemma Prompt</th>
                    <th className="py-2.5 px-2">Intent</th>
                    <th className="py-2.5 px-2">Persona</th>
                    <th className="py-2.5 px-2 text-center">Citation Prob P(C)</th>
                    <th className="py-2.5 px-2 text-center">Wilson 95% Band</th>
                    <th className="py-2.5 px-2 text-center">EVI</th>
                    <th className="py-2.5 px-2 text-center">Net Stance</th>
                    <th className="py-2.5 px-2 text-center">Volatility SE</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-hairline">
                  {filteredPrompts.map((p) => {
                    const isSelected = p.id === selectedPrompt?.id;
                    const probPercent = Math.round(p.citationProbability * 100);
                    const nss = p.netStance;
                    return (
                      <tr
                        key={p.id}
                        onClick={() => setSelectedQueryId(p.id)}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? "bg-primary-soft/50 border-l-4 border-l-primary"
                            : "hover:bg-surface-subtle"
                        }`}
                      >
                        <td className="py-2.5 px-3 font-medium text-foreground max-w-xs truncate">
                          {p.query}
                        </td>
                        <td className="py-2.5 px-2">
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-code-data font-bold uppercase bg-surface-subtle border border-border-hairline text-foreground">
                            {p.intent}
                          </span>
                        </td>
                        <td className="py-2.5 px-2 text-muted-foreground capitalize text-[11px]">
                          {p.persona.replace(/_/g, " ")}
                        </td>
                        <td className="py-2.5 px-2 text-center font-code-data font-bold text-foreground">
                          <div className="flex items-center justify-center gap-1.5">
                            <span>{probPercent}%</span>
                            <div className="w-12 bg-surface-subtle h-1 rounded-full overflow-hidden">
                              <div
                                className="bg-primary h-1 rounded-full"
                                style={{ width: `${probPercent}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="py-2.5 px-2 text-center font-code-data text-muted-foreground text-[11px]">
                          [{Math.round(p.wilsonInterval[0] * 100)}%, {Math.round(p.wilsonInterval[1] * 100)}%]
                        </td>
                        <td className="py-2.5 px-2 text-center font-code-data text-primary font-bold">
                          {p.evi.toFixed(2)}
                        </td>
                        <td className="py-2.5 px-2 text-center">
                          <span
                            className={`px-1.5 py-0.2 rounded text-[10px] font-code-data font-bold ${
                              nss > 0.2
                                ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                                : nss < -0.2
                                ? "bg-rose-50 text-rose-800 border border-rose-200"
                                : "bg-surface-subtle text-muted-foreground border border-border-hairline"
                            }`}
                          >
                            {nss > 0 ? `+${nss.toFixed(2)}` : nss.toFixed(2)}
                          </span>
                        </td>
                        <td className="py-2.5 px-2 text-center font-code-data text-muted-foreground text-[11px]">
                          ±{p.volatility.toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Detail Inspector Column (4 cols) */}
          <div className="lg:col-span-5 xl:col-span-4 flex flex-col gap-4 bg-surface border border-border-hairline rounded-xl p-4 shadow-xs">
            {selectedPrompt ? (
              <>
                <div className="flex flex-col gap-1.5 border-b border-border-hairline pb-3">
                  <div className="flex items-center justify-between">
                    <span className="font-code-data text-[10px] text-muted-foreground uppercase tracking-wider">
                      Buyer Dilemma Inspector
                    </span>
                    <span className="font-code-data text-[10px] text-primary font-bold">
                      EVI: {selectedPrompt.evi.toFixed(2)}
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-foreground leading-snug">
                    &ldquo;{selectedPrompt.query}&rdquo;
                  </h2>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="px-2 py-0.5 rounded text-[10px] font-code-data font-bold uppercase bg-surface-subtle border border-border-hairline">
                      Intent: {selectedPrompt.intent}
                    </span>
                    <span className="text-[11px] text-muted-foreground capitalize">
                      Persona: {selectedPrompt.persona.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>

                {/* Generative Synthesis Transcript */}
                <div className="flex flex-col gap-1.5">
                  <span className="text-xs font-bold text-foreground uppercase tracking-wider flex items-center gap-1">
                    <span className="material-symbols-outlined text-[16px] text-primary">psychology</span>
                    Generative Model Synthesis
                  </span>
                  <div className="p-3 bg-surface-subtle border border-border-hairline rounded-lg font-serif italic text-xs text-foreground leading-relaxed">
                    <p>{selectedPrompt.sampleAnswer || "No text transcript recorded for this run index."}</p>
                  </div>
                </div>

                {/* Sub-Queries Fan-Out Interception */}
                {selectedPrompt.subQueries.length > 0 && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs font-bold text-foreground uppercase tracking-wider flex items-center gap-1">
                      <span className="material-symbols-outlined text-[16px] text-indigo-600">account_tree</span>
                      Intercepted Query Fan-Out
                    </span>
                    <div className="space-y-1">
                      {selectedPrompt.subQueries.map((sub, i) => (
                        <div
                          key={i}
                          className="px-2.5 py-1.5 rounded bg-surface border border-border-hairline text-xs font-code-data text-foreground"
                        >
                          ↳ {sub}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Direct Action Handoff into Content Optimizer */}
                <div className="pt-2 border-t border-border-hairline flex flex-col gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                    Action Plan in Optimizer
                  </span>
                  <Link
                    href={`/optimizer?query=${encodeURIComponent(selectedPrompt.query)}&intent=${selectedPrompt.intent}`}
                    className="h-8 px-3 rounded-lg bg-primary hover:bg-primary-hover text-white text-xs font-medium inline-flex items-center justify-center gap-1.5 shadow-xs transition-colors"
                  >
                    <span>Fix Coverage in Optimizer Studio</span>
                    <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
                  </Link>
                </div>
              </>
            ) : (
              <div className="text-center py-10 text-xs text-muted-foreground">
                Select a query from the table to inspect details.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- TAB 2: SHARE OF VOICE (CSOV) */}
      {activeTab === "csov" && (
        <div className="px-6 pb-8 space-y-6">
          <div className="bg-surface rounded-xl border border-border-hairline shadow-xs p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-foreground">
                  Competitive Share of Voice (CSoV) Leaderboard
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Dirichlet/Laplace smoothed competitive share ($\alpha = 1.0$) eliminating low-sample denominator bias.
                </p>
              </div>
              <span className="font-code-data text-xs text-muted-foreground">
                Sample Credence Weight: {geoData?.csov?.credenceWeight.toFixed(2) || "0.00"}
              </span>
            </div>

            {/* Competitive Share Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-surface-subtle text-muted-foreground font-medium text-[10px] uppercase border-b border-border-hairline">
                    <th className="py-2.5 px-3">Entity / Brand</th>
                    <th className="py-2.5 px-2 text-center">Grounded Citations</th>
                    <th className="py-2.5 px-2 text-center">Empirical CSoV</th>
                    <th className="py-2.5 px-2 text-center">Smoothed CSoV (Laplace)</th>
                    <th className="py-2.5 px-2 text-center">Prominence Weighted</th>
                    <th className="py-2.5 px-2 text-center">Market Share (w/ Editorial)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-hairline">
                  {geoData?.csov?.entities?.map((ent, i) => {
                    const isBrand = i === 0;
                    return (
                      <tr
                        key={ent.name}
                        className={`transition-colors ${
                          isBrand ? "bg-primary-soft/40 font-semibold" : "hover:bg-surface-subtle"
                        }`}
                      >
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2">
                            {isBrand ? (
                              <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-primary text-white">
                                Target Brand
                              </span>
                            ) : (
                              <span className="font-code-data text-[10px] text-muted-foreground">#{i}</span>
                            )}
                            <span className="text-foreground">{ent.name}</span>
                          </div>
                        </td>
                        <td className="py-3 px-2 text-center font-code-data font-bold text-foreground">
                          {ent.citations}
                        </td>
                        <td className="py-3 px-2 text-center font-code-data">
                          <div className="flex items-center justify-center gap-2">
                            <span>{ent.competitiveCSoVPercentage.toFixed(1)}%</span>
                            <div className="w-16 bg-surface-subtle h-1.5 rounded-full overflow-hidden">
                              <div
                                className={isBrand ? "bg-primary h-1.5 rounded-full" : "bg-muted-foreground h-1.5 rounded-full"}
                                style={{ width: `${Math.min(100, ent.competitiveCSoVPercentage)}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-2 text-center font-code-data font-bold text-foreground">
                          {ent.smoothedCompetitiveCSoVPercentage.toFixed(1)}%
                        </td>
                        <td className="py-3 px-2 text-center font-code-data text-emerald-700 font-bold">
                          {ent.prominenceWeightedCSoVPercentage.toFixed(1)}%
                        </td>
                        <td className="py-3 px-2 text-center font-code-data text-muted-foreground">
                          {ent.marketSharePercentage.toFixed(1)}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- TAB 3: REVERSE-RAG CITATIONS */}
      {activeTab === "citations" && (
        <div className="px-6 pb-8 space-y-6">
          <div className="bg-surface rounded-xl border border-border-hairline shadow-xs p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-foreground">
                  Reverse-RAG Passage Matching & Vector Attribution
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Exact text chunks extracted from cited web pages aligned with AI generated answers using tokenized Cosine TF-IDF similarity.
                </p>
              </div>
              <span className="font-code-data text-xs text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                Cosine TF-IDF Vector Alignment Active
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {geoData?.alignments?.map((chunk) => (
                <div
                  key={chunk.id}
                  className="p-4 rounded-xl border border-border-hairline bg-surface-subtle/50 space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-code-data font-bold text-primary text-[11px]">
                      {chunk.heading}
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 font-code-data font-bold text-[10px] border border-emerald-200">
                      Similarity: {(chunk.similarityScore * 100).toFixed(0)}%
                    </span>
                  </div>
                  <blockquote className="font-serif italic text-foreground leading-relaxed p-2.5 bg-surface rounded border border-border-hairline">
                    &ldquo;{chunk.passageText}&rdquo;
                  </blockquote>
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
                    <span>Rank: #{chunk.rank}</span>
                    <Link
                      href={`/optimizer?matchChunk=${encodeURIComponent(chunk.passageText.slice(0, 40))}`}
                      className="text-primary hover:underline font-medium inline-flex items-center gap-0.5"
                    >
                      <span>Inject into Optimizer draft</span>
                      <span className="material-symbols-outlined text-[13px]">arrow_forward</span>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- TAB 4: RESPONSES & FAN-OUT TREES */}
      {activeTab === "transcripts" && (
        <div className="px-6 pb-8 space-y-4">
          <div className="bg-surface rounded-xl border border-border-hairline shadow-xs p-5">
            <h2 className="text-base font-bold text-foreground mb-1">
              Multi-Turn Generative Transcripts & Sub-Query Interceptor
            </h2>
            <p className="text-xs text-muted-foreground mb-4">
              Raw conversational output and agentic RAG exploration sub-queries captured across headless stealth crawl sessions.
            </p>

            <div className="space-y-3">
              {geoData?.runs?.map((r) => (
                <div key={r.id} className="p-4 rounded-xl border border-border-hairline bg-surface text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-surface-subtle border border-border-hairline font-code-data font-bold text-[10px] uppercase">
                        {r.engine}
                      </span>
                      <span className="font-code-data text-muted-foreground text-[11px]">
                        Latency: {r.executionMs}ms
                      </span>
                    </div>
                    <span className="text-[11px] text-muted-foreground font-code-data">
                      {new Date(r.createdAt).toLocaleDateString()}
                    </span>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-subtle/70 font-serif italic text-foreground leading-relaxed">
                    {r.responseText}
                  </div>

                  {r.subQueries?.length > 0 && (
                    <div className="pt-1">
                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block mb-1">
                        Intercepted Agentic Sub-Queries:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {r.subQueries.map((sub, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 font-code-data text-[10px] border border-indigo-200"
                          >
                            ↳ {sub}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- TAB 5: AUDIT RUN DIFF (COMPARE) */}
      {activeTab === "compare" && (
        <div className="px-6 pb-8 space-y-6">
          <div className="bg-surface rounded-xl border border-border-hairline shadow-xs p-5 space-y-4">
            <h2 className="text-base font-bold text-foreground">
              Audit Run Comparison (Baseline vs. Candidate)
            </h2>
            <p className="text-xs text-muted-foreground">
              Select two audit runs to compare Answer Vector Readiness (AVR) deltas, resolved blockers, and entity coverage shifts.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="compare-baseline" className="block text-xs font-semibold text-foreground mb-1">
                  Baseline Audit
                </label>
                <select
                  id="compare-baseline"
                  value={baselineAuditId}
                  onChange={(e) => setBaselineAuditId(e.target.value)}
                  className="w-full h-9 px-2 rounded-lg bg-surface-subtle border border-border-hairline text-xs text-foreground focus:outline-none focus:border-primary"
                >
                  <option value="">Select baseline audit run...</option>
                  {auditsQuery.data?.map((a) => (
                    <option key={a.audit_id} value={a.audit_id}>
                      {new Date(a.created_at).toLocaleDateString()} · {a.central_entity || "Content"} (AVR: {a.composite ?? "N/A"})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="compare-candidate" className="block text-xs font-semibold text-foreground mb-1">
                  Candidate Audit
                </label>
                <select
                  id="compare-candidate"
                  value={candidateAuditId}
                  onChange={(e) => setCandidateAuditId(e.target.value)}
                  className="w-full h-9 px-2 rounded-lg bg-surface-subtle border border-border-hairline text-xs text-foreground focus:outline-none focus:border-primary"
                >
                  <option value="">Select candidate audit run...</option>
                  {auditsQuery.data?.map((a) => (
                    <option key={a.audit_id} value={a.audit_id}>
                      {new Date(a.created_at).toLocaleDateString()} · {a.central_entity || "Content"} (AVR: {a.composite ?? "N/A"})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {baselineAuditId && candidateAuditId ? (
              <div className="space-y-4" data-testid="compare-result">
                {compareQuery.isLoading ? (
                  <div className="p-4 rounded-xl bg-surface-subtle border border-border-hairline text-xs text-muted-foreground">
                    Comparing runs…
                  </div>
                ) : compareQuery.isError ? (
                  <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800">
                    Comparison failed: {(compareQuery.error as Error)?.message ?? "unknown error"}
                  </div>
                ) : compareQuery.data ? (
                  (() => {
                    const result = compareQuery.data;
                    const changes: Array<[string, Array<string | EntityChangeItem>]> = [
                      ["Added", result.entity_changes?.added ?? []],
                      ["Removed", result.entity_changes?.removed ?? []],
                      ["Changed", result.entity_changes?.changed ?? []],
                    ];
                    return (
                      <>
                        <HeuristicDisclaimer />

                        {/* Score movement */}
                        <div className="rounded-xl border border-border-hairline overflow-hidden">
                          <div className="px-4 py-2 bg-surface-subtle border-b border-border-hairline flex items-center justify-between">
                            <span className="text-xs font-bold text-foreground">Score movement</span>
                            <span className="text-[11px] text-muted-foreground">
                              {baselineAuditId.slice(0, 8)} → {candidateAuditId.slice(0, 8)}
                            </span>
                          </div>
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
                                <th className="text-left font-semibold px-4 py-2">Dimension</th>
                                <th className="text-right font-semibold px-4 py-2">Baseline</th>
                                <th className="text-right font-semibold px-4 py-2">Candidate</th>
                                <th className="text-right font-semibold px-4 py-2">Δ</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(result.score_delta ?? []).map((row: ScoreDelta, index: number) => (
                                <tr
                                  key={row.key || index}
                                  className="border-t border-border-hairline"
                                  data-testid="compare-score-delta"
                                >
                                  <td className="px-4 py-2 font-medium text-foreground">{row.key}</td>
                                  <td className="px-4 py-2 text-right font-code-data text-muted-foreground">
                                    {row.baseline ?? "—"}
                                  </td>
                                  <td className="px-4 py-2 text-right font-code-data text-muted-foreground">
                                    {row.candidate ?? "—"}
                                  </td>
                                  <td className="px-4 py-2 text-right">
                                    <DeltaValue delta={row.delta} />
                                  </td>
                                </tr>
                              ))}
                              {(result.score_delta ?? []).length === 0 && (
                                <tr>
                                  <td colSpan={4} className="px-4 py-3 text-muted-foreground">
                                    No scored dimensions were returned for this pair.
                                  </td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                        </div>

                        {/* Entity + coverage shifts */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="rounded-xl border border-border-hairline p-4 space-y-2">
                            <h3 className="text-xs font-bold text-foreground">Entity changes</h3>
                            {changes.map(([label, items]) => (
                              <div key={label} className="text-xs">
                                <span className="text-muted-foreground font-semibold">{label} ({items.length}):</span>
                                {items.length === 0 ? (
                                  <span className="ml-1 text-muted-foreground">none</span>
                                ) : (
                                  <ul className="mt-1 space-y-0.5 pl-4 list-disc text-foreground">
                                    {items.slice(0, 12).map((item, i) => (
                                      <li key={`${label}-${i}`}>{entityChangeLabel(item)}</li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            ))}
                          </div>
                          <div className="rounded-xl border border-border-hairline p-4 space-y-2">
                            <h3 className="text-xs font-bold text-foreground">Coverage</h3>
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">Questions covered</span>
                              <span className="font-code-data">
                                {result.coverage_delta?.baseline_covered ?? "—"} →{" "}
                                {result.coverage_delta?.candidate_covered ?? "—"}
                                {result.coverage_delta?.total != null ? ` / ${result.coverage_delta.total}` : ""}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">FCS</span>
                              <span className="font-code-data">
                                {result.coverage_delta?.baseline_fcs ?? "—"} →{" "}
                                {result.coverage_delta?.candidate_fcs ?? "—"}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Findings */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="rounded-xl border border-border-hairline p-4 space-y-2">
                            <h3 className="text-xs font-bold text-foreground">
                              Resolved findings ({result.resolved_findings?.length ?? 0})
                            </h3>
                            <ul className="text-xs space-y-1">
                              {(result.resolved_findings ?? []).slice(0, 8).map((finding, i) => (
                                <li key={finding.finding_id ?? i} className="text-foreground">
                                  {finding.title}
                                </li>
                              ))}
                              {(result.resolved_findings ?? []).length === 0 && (
                                <li className="text-muted-foreground">None resolved.</li>
                              )}
                            </ul>
                          </div>
                          <div className="rounded-xl border border-border-hairline p-4 space-y-2">
                            <h3 className="text-xs font-bold text-foreground">
                              New findings ({result.new_findings?.length ?? 0})
                            </h3>
                            <ul className="text-xs space-y-1">
                              {(result.new_findings ?? []).slice(0, 8).map((finding, i) => (
                                <li key={finding.finding_id ?? i} className="text-foreground">
                                  {finding.title}
                                </li>
                              ))}
                              {(result.new_findings ?? []).length === 0 && (
                                <li className="text-muted-foreground">No new findings.</li>
                              )}
                            </ul>
                          </div>
                        </div>

                        {(result.warnings ?? []).length > 0 && (
                          <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-[11px] text-amber-900 space-y-1">
                            {result.warnings.map((warning, i) => (
                              <div key={i}>{warning}</div>
                            ))}
                          </div>
                        )}
                      </>
                    );
                  })()
                ) : null}
              </div>
            ) : (
              <div className="p-6 text-center text-xs text-muted-foreground border border-dashed border-border-hairline rounded-xl">
                Select both a baseline and a candidate audit run above to inspect regression deltas.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- ADD PROMPT MODAL */}
      {showAddPromptModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-surface rounded-xl border border-border-hairline shadow-lg max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-foreground">Add Buyer Dilemma Prompt</h3>
              <button
                type="button"
                onClick={() => setShowAddPromptModal(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <span className="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              Stage a search query as a local draft for this session. Nothing is queued against a
              provider or saved to the monitoring database.
            </p>
            <form onSubmit={handleAddPrompt} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-foreground mb-1">Search Query / Prompt</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. best automated bookkeeping service for design studios"
                  value={newPromptDraft.query}
                  onChange={(e) => setNewPromptDraft({ ...newPromptDraft, query: e.target.value })}
                  className="w-full h-8 px-2.5 rounded bg-surface-subtle border border-border-hairline text-xs text-foreground focus:outline-none focus:border-primary"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-medium text-foreground mb-1">Intent Class</label>
                  <select
                    value={newPromptDraft.intent}
                    onChange={(e) => setNewPromptDraft({ ...newPromptDraft, intent: e.target.value })}
                    className="w-full h-8 px-2 rounded bg-surface-subtle border border-border-hairline text-xs text-foreground focus:outline-none focus:border-primary"
                  >
                    <option>Commercial</option>
                    <option>Pricing</option>
                    <option>Alternative</option>
                    <option>Direct</option>
                  </select>
                </div>
                <div>
                  <label className="block font-medium text-foreground mb-1">Persona Dimension</label>
                  <select
                    value={newPromptDraft.persona}
                    onChange={(e) => setNewPromptDraft({ ...newPromptDraft, persona: e.target.value })}
                    className="w-full h-8 px-2 rounded bg-surface-subtle border border-border-hairline text-xs text-foreground focus:outline-none focus:border-primary"
                  >
                    <option value="agency_executive">Agency Executive</option>
                    <option value="finance_director">Finance Director</option>
                    <option value="operations_lead">Operations Lead</option>
                    <option value="technical_founder">Technical Founder</option>
                  </select>
                </div>
              </div>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddPromptModal(false)}
                  className="h-8 px-3 rounded bg-surface border border-border-hairline text-xs font-medium text-foreground hover:bg-surface-subtle"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="h-8 px-3 rounded bg-primary text-white text-xs font-medium hover:bg-primary-hover shadow-xs"
                >
                  Add Prompt
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
