"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useWorkspace } from "@/lib/workspace-context";
import { api } from "@/lib/api";
import { analyzeContent, type OptimizerMetrics } from "@/lib/optimizer";
import { usePageTitle } from "@/lib/use-page-title";
import type { PageType } from "@/lib/types";

/** Brand-rule terms the inspector checks the draft against (deterministic). */
const ANALYZER_BANNED_TERMS = [
  "100% unhackable",
  "unhackable",
  "guaranteed",
  "miracle",
  "foolproof",
];

const DEFAULT_STARTER_DRAFT = `# Optimizing Content for Machine Retrieval and Entity SEO

Search engines and modern AI answer engines evaluate content for factual clarity, entity salience, and direct answer readiness. When structuring articles, documentation, or service offerings, directness is essential.

## How do AI answer engines extract information?

AI search crawlers and generative engines scan for concise definition passages immediately following question headings. Grounding claims with verified facts and canonical entity names ensures reliable citation.

## Core Best Practices

1. Direct Answers: Provide immediate answers under H2 question headings.
2. Canonical Entities: State clear proper nouns rather than ambiguous pronouns.
3. Fact Consistency: Align numeric claims and pricing with verified Entity Hub records.
4. Clean Hierarchy: Maintain a single H1 heading and clear H2/H3 subsections.
`;

const PAGE_TYPES = ["Service", "Article", "Guide", "Product", "Documentation", "FAQ"];
const INTENT_TYPES = ["Commercial", "Informational", "Transactional", "Navigational"];

const titleCase = (value: string) =>
  value ? value.charAt(0).toUpperCase() + value.slice(1) : value;

const bandTextClass = (band: string) =>
  band === "strong"
    ? "text-emerald-600"
    : band === "weak"
      ? "text-destructive"
      : "text-warning";

const bandBarClass = (band: string) =>
  band === "strong"
    ? "bg-emerald-600"
    : band === "weak"
      ? "bg-destructive"
      : "bg-amber-500";

function OptimizerStudioContent() {
  usePageTitle("Aentio · Content Optimizer");
  const router = useRouter();
  const searchParams = useSearchParams();
  const { activeProject } = useWorkspace();

  const isBrief = searchParams.get("brief") === "true";
  const titleParam = searchParams.get("title");
  const queryParam = searchParams.get("query");

  const [documentTitle, setDocumentTitle] = useState(() => {
    if (typeof window !== "undefined" && isBrief) {
      const stored = sessionStorage.getItem("aentio_optimizer_initial_query");
      if (stored) return stored;
    }
    return titleParam || "Optimizing Content for Machine Retrieval";
  });

  const [targetQuery, setTargetQuery] = useState(() => {
    if (typeof window !== "undefined" && isBrief) {
      const stored = sessionStorage.getItem("aentio_optimizer_initial_query");
      if (stored) return stored;
    }
    return titleParam || queryParam || "Entity SEO & Content Optimization";
  });

  const [content, setContent] = useState(() => {
    if (typeof window !== "undefined" && isBrief) {
      const stored = sessionStorage.getItem("aentio_optimizer_initial_draft");
      if (stored) return stored;
    }
    return DEFAULT_STARTER_DRAFT;
  });

  const [initialContent] = useState(content);
  const [pageType, setPageType] = useState<string>("Service");
  const [intent, setIntent] = useState<string>("Commercial");
  const [customEntities, setCustomEntities] = useState<string[]>([]);
  const [newEntityInput, setNewEntityInput] = useState("");

  const [isDiffMode, setIsDiffMode] = useState(false);
  const [fontFamily, setFontFamily] = useState<"serif" | "sans">("serif");
  const [activeInspectorTab, setActiveInspectorTab] = useState<
    "overview" | "entities" | "answers" | "evidence" | "passages" | "hierarchy"
  >("overview");
  const [leftContextCollapsed, setLeftContextCollapsed] = useState(false);
  const [copiedNotification, setCopiedNotification] = useState(false);

  // Fetch real workspace entities for the active project. The backend requires
  // a project_id, so the query stays disabled until a project is selected.
  const workspaceEntitiesQuery = useQuery({
    queryKey: ["workspace-entities", activeProject?.project_id],
    queryFn: () => api.listEntities(activeProject!.project_id),
    enabled: !!activeProject?.project_id,
    staleTime: 60_000,
  });

  // Calculate real-time metrics using deterministic engine
  const metrics: OptimizerMetrics = useMemo(
    () => analyzeContent(content, targetQuery, ANALYZER_BANNED_TERMS, 900),
    [content, targetQuery],
  );

  // Debounce the draft so the inspector calls POST /workspace/analyze at most
  // once per 500ms while typing instead of once per keystroke.
  const [debouncedContent, setDebouncedContent] = useState(content);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedContent(content), 500);
    return () => clearTimeout(timer);
  }, [content]);

  // Combined list of tracked entities: from project registry + user added + target query
  const trackedEntitiesList = useMemo(() => {
    const set = new Set<string>();
    if (targetQuery.trim()) set.add(targetQuery.trim());
    if (activeProject?.brand) set.add(activeProject.brand);
    if (activeProject?.central_entity) set.add(activeProject.central_entity);
    for (const e of customEntities) set.add(e);
    for (const we of workspaceEntitiesQuery.data?.entities ?? []) {
      set.add(we.name);
    }
    return Array.from(set);
  }, [targetQuery, activeProject, customEntities, workspaceEntitiesQuery.data]);

  // Server-computed analysis driving the inspector bands and recommendations.
  const analysis = useQuery({
    queryKey: ["optimizer-analyze", debouncedContent, targetQuery, trackedEntitiesList],
    queryFn: () =>
      api.analyzeContent({
        text: debouncedContent,
        primary_query: targetQuery,
        target_entities: trackedEntitiesList,
        banned_terms: ANALYZER_BANNED_TERMS,
        word_target: 900,
      }),
    enabled: debouncedContent.trim().length > 0,
    staleTime: 30_000,
    placeholderData: (previous) => previous,
  });

  const pendingSuggestions = analysis.data?.recommendations.length ?? 0;
  const dimensions = analysis.data?.dimensions ?? [];

  // Deep Audit Mutation to backend
  const publishMutation = useMutation({
    mutationFn: async () => {
      if (!activeProject?.project_id) {
        throw new Error("Please select an active project in the top bar.");
      }
      // 1. Import text to backend
      const imp = await api.importContent({
        project_id: activeProject.project_id,
        text: content,
        format: "markdown",
      });

      // 2. Dispatch audit run
      const audit = await api.createAudit({
        project_id: activeProject.project_id,
        content_version_id: imp.content_version_id,
        primary_query: targetQuery,
        page_type: (pageType.toLowerCase() as PageType) || "service",
        depth: "deep",
        source_profile: "offline",
        sensitivity: "ordinary",
      });

      return audit.audit_id;
    },
    onSuccess: (auditId) => {
      router.push(`/audits/${auditId}`);
    },
  });

  // Action helpers that work on any content
  const handleAddCustomEntity = (e: React.FormEvent) => {
    e.preventDefault();
    const val = newEntityInput.trim();
    if (!val || customEntities.includes(val)) return;
    setCustomEntities((prev) => [...prev, val]);
    setNewEntityInput("");
  };

  const handleMakeAnswerFirst = () => {
    const brandName = activeProject?.brand || "This service";
    const prefix = `**${brandName}** provides comprehensive ${targetQuery} designed to deliver immediate results.\n\n`;
    if (!content.includes(prefix)) {
      setContent(prefix + content);
    }
  };

  const handleAddQuestionH2 = () => {
    const h2Text = `\n\n## How does ${targetQuery} work?\n\nProvide a direct 2-3 sentence explanation here answering the user's primary intent.\n`;
    setContent((prev) => prev + h2Text);
  };

  const handleAddFaq = () => {
    const faq = `\n\n## Frequently Asked Questions\n\n### What is ${targetQuery}?\n${targetQuery} represents structured solutions optimized for modern search engines.\n\n### How quickly does it take effect?\nImplementation typically produces observable indexing improvements within standard crawl cycles.\n`;
    setContent((prev) => prev + faq);
  };

  const handleDemoteExtraH1 = () => {
    let count = 0;
    const updated = content
      .split("\n")
      .map((line) => {
        if (/^#\s+/.test(line)) {
          count++;
          if (count > 1) return line.replace(/^#\s+/, "## ");
        }
        return line;
      })
      .join("\n");
    setContent(updated);
  };

  const handleRemoveBannedTerms = () => {
    let updated = content;
    for (const term of ANALYZER_BANNED_TERMS) {
      const reg = new RegExp(`\\b${term}\\b`, "gi");
      updated = updated.replace(reg, "verified");
    }
    setContent(updated);
  };

  const handleClearContent = () => {
    if (content.length > 50) {
      if (!confirm("Clear the editor to start a fresh draft?")) return;
    }
    setContent("");
    setDocumentTitle("");
  };

  const handlePasteClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setContent(text);
      }
    } catch {
      // ignore
    }
  };

  const handleCopyText = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedNotification(true);
      setTimeout(() => setCopiedNotification(false), 2000);
    } catch {
      // ignore
    }
  };

  // Facts collected from real workspace entities
  const realFacts = useMemo(() => {
    const list: Array<{ text: string; date: string }> = [];
    for (const ent of workspaceEntitiesQuery.data?.entities ?? []) {
      for (const fact of ent.facts ?? []) {
        list.push({
          text: `${ent.name}: ${fact.property} is ${fact.value}`,
          date: fact.date ?? "Verified",
        });
      }
    }
    return list;
  }, [workspaceEntitiesQuery.data]);

  return (
    <div className="flex flex-col w-full h-[calc(100vh-52px)] overflow-hidden bg-background-canvas text-foreground select-none">
      {/* ------------------------------------------------------------- SUB-BAR */}
      <div className="h-10 w-full bg-surface border-b border-border-hairline px-4 flex items-center justify-between shrink-0 z-20">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block animate-pulse" />
            Deterministic analyzer
          </span>
          <span className="text-border-hairline">|</span>
          <span className="text-xs font-code-data text-muted-foreground">
            {analysis.isFetching
              ? "analyzing…"
              : analysis.data
                ? `${analysis.data.dimensions.length} dimensions · ${pendingSuggestions} suggestion${pendingSuggestions === 1 ? "" : "s"}`
                : "idle — add content"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Quick Actions */}
          <button
            onClick={handleClearContent}
            className="h-7 px-2.5 rounded text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-surface-subtle border border-border-hairline transition-colors flex items-center gap-1"
            title="Clear current text to start fresh"
          >
            <span className="material-symbols-outlined text-[14px]">delete</span>
            <span>Clear</span>
          </button>

          <button
            onClick={handlePasteClipboard}
            className="h-7 px-2.5 rounded text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-surface-subtle border border-border-hairline transition-colors flex items-center gap-1"
            title="Paste text from clipboard"
          >
            <span className="material-symbols-outlined text-[14px]">content_paste</span>
            <span>Paste</span>
          </button>

          <span className="text-border-hairline">|</span>

          {/* Toggle Diff / Review Mode Button */}
          <button
            onClick={() => setIsDiffMode(!isDiffMode)}
            className={`h-7 px-2.5 rounded text-xs font-medium flex items-center gap-1 transition-colors ${
              isDiffMode
                ? "bg-amber-500 text-white font-semibold shadow-xs"
                : "bg-surface hover:bg-surface-subtle text-muted-foreground hover:text-foreground border border-border-hairline"
            }`}
          >
            <span className="material-symbols-outlined text-[15px]">difference</span>
            <span>{isDiffMode ? "Editing Mode" : "Show Diff"}</span>
          </button>

          {/* Re-scan Button */}
          <button
            onClick={() => {
              setContent((prev) => prev + " ");
            }}
            className="h-7 px-2.5 rounded bg-primary-soft hover:bg-primary/20 text-xs font-medium text-primary flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-[15px]">bolt</span>
            <span>Re-scan</span>
          </button>

          <span className="text-border-hairline">|</span>

          {/* Publish / Deep Audit Button */}
          <button
            onClick={() => publishMutation.mutate()}
            disabled={publishMutation.isPending}
            className="h-7 px-3 rounded bg-primary hover:bg-primary-hover text-white text-xs font-medium flex items-center gap-1 transition-colors shadow-xs"
          >
            {publishMutation.isPending ? (
              <span>Queueing…</span>
            ) : (
              <>
                <span className="material-symbols-outlined text-[15px]">publish</span>
                <span>Run Audit</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Review Mode Banner */}
      {isDiffMode && (
        <div className="w-full bg-surface-subtle px-4 py-2 border-b border-border-hairline flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-warning-soft text-warning text-xs font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-warning animate-pulse" />
              <span>Diff View</span>
            </div>
            <p className="text-xs text-foreground truncate">
              Comparing current draft with initial baseline ({content.length} chars vs {initialContent.length} chars).
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => {
                setContent(initialContent);
                setIsDiffMode(false);
              }}
              className="h-6 px-2.5 rounded bg-surface hover:bg-surface-subtle text-destructive text-xs font-medium border border-border-hairline transition shadow-xs"
            >
              Revert to Initial
            </button>
            <button
              onClick={() => setIsDiffMode(false)}
              className="h-6 px-3 rounded bg-primary hover:bg-primary-hover text-white text-xs font-medium transition flex items-center gap-1 shadow-xs"
            >
              <span>Keep Current</span>
            </button>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- 3-ZONE MAIN BODY */}
      <div className="flex-1 flex flex-row w-full overflow-hidden min-h-0">
        {/* ========================================================= ZONE 1: LEFT CONTEXT (280px) */}
        {!leftContextCollapsed ? (
          <aside className="w-[280px] shrink-0 border-r border-border-hairline bg-surface flex flex-col h-full overflow-hidden select-none">
            {/* Header */}
            <div className="h-10 px-4 flex items-center justify-between border-b border-border-hairline shrink-0">
              <div className="flex items-center gap-1.5">
                <span className="material-symbols-outlined text-[16px] text-muted-foreground">tune</span>
                <span className="font-semibold text-xs tracking-tight text-foreground">Target &amp; Entities</span>
              </div>
              <button
                onClick={() => setLeftContextCollapsed(true)}
                className="w-6 h-6 rounded flex items-center justify-center hover:bg-surface-subtle text-muted-foreground hover:text-foreground transition-colors"
                title="Collapse Context Panel"
              >
                <span className="material-symbols-outlined text-[16px]">first_page</span>
              </button>
            </div>

            {/* Scrollable Context Body */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 text-xs">
              {/* Target Query Card */}
              <div className="p-2.5 rounded-lg bg-surface-subtle border border-border-hairline space-y-1.5">
                <span className="text-[10px] uppercase tracking-wider font-code-data font-semibold text-muted-foreground">
                  Target Search Query
                </span>
                <input
                  type="text"
                  value={targetQuery}
                  onChange={(e) => setTargetQuery(e.target.value)}
                  placeholder="e.g. Entity SEO Strategy"
                  className="w-full bg-surface border border-border-hairline rounded px-2 py-1 text-xs font-semibold text-foreground focus:outline-none focus:border-primary"
                />
              </div>

              {/* Page Type & Intent Selectors */}
              <div className="space-y-2">
                <span className="text-[10px] uppercase tracking-wider font-code-data text-muted-foreground font-semibold">
                  Page Type
                </span>
                <div className="flex flex-wrap gap-1">
                  {PAGE_TYPES.map((pt) => (
                    <button
                      key={pt}
                      onClick={() => setPageType(pt)}
                      className={`px-2 py-0.5 rounded text-[11px] font-medium transition ${
                        pageType === pt
                          ? "bg-primary-soft text-primary font-semibold border border-primary/30"
                          : "bg-surface hover:bg-surface-subtle border border-border-hairline text-muted-foreground"
                      }`}
                    >
                      {pt}
                    </button>
                  ))}
                </div>

                <span className="text-[10px] uppercase tracking-wider font-code-data text-muted-foreground font-semibold block pt-1">
                  Search Intent
                </span>
                <div className="flex flex-wrap gap-1">
                  {INTENT_TYPES.map((it) => (
                    <button
                      key={it}
                      onClick={() => setIntent(it)}
                      className={`px-2 py-0.5 rounded text-[11px] font-medium transition ${
                        intent === it
                          ? "bg-primary-soft text-primary font-semibold border border-primary/30"
                          : "bg-surface hover:bg-surface-subtle border border-border-hairline text-muted-foreground"
                      }`}
                    >
                      {it}
                    </button>
                  ))}
                </div>
              </div>

              <div className="h-[1px] bg-border-hairline" />

              {/* Business Entities in Use */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-[15px] text-primary">hub</span>
                    <span className="text-xs font-semibold text-foreground">Target Entities</span>
                    <span className="text-[10px] font-code-data px-1.5 rounded-full bg-surface-subtle text-muted-foreground">
                      {trackedEntitiesList.length}
                    </span>
                  </div>
                </div>

                {/* Add Entity Form */}
                <form onSubmit={handleAddCustomEntity} className="flex gap-1">
                  <input
                    type="text"
                    value={newEntityInput}
                    onChange={(e) => setNewEntityInput(e.target.value)}
                    placeholder="+ Add entity..."
                    className="flex-1 bg-surface border border-border-hairline rounded px-2 py-0.5 text-[11px] text-foreground focus:outline-none focus:border-primary"
                  />
                  <button
                    type="submit"
                    className="px-2 py-0.5 rounded bg-surface hover:bg-surface-subtle border border-border-hairline text-[11px] text-foreground font-medium"
                  >
                    Add
                  </button>
                </form>

                <div className="space-y-1 pl-0.5 pt-1">
                  {trackedEntitiesList.map((entName) => {
                    const count = (content.match(new RegExp(entName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi")) || []).length;
                    return (
                      <div
                        key={entName}
                        className="flex items-center justify-between py-1 px-1.5 rounded hover:bg-surface-subtle transition-colors group cursor-pointer"
                        onClick={() => setContent((prev) => prev + ` ${entName}`)}
                        title={`Click to insert "${entName}"`}
                      >
                        <span className="text-foreground font-medium flex items-center gap-1.5 truncate text-[11px]">
                          <span className={`w-1.5 h-1.5 rounded-full ${count > 0 ? "bg-emerald-600" : "bg-muted-foreground/50"}`} />
                          {entName}
                        </span>
                        <span className="font-code-data text-[10px] text-muted-foreground shrink-0">
                          {count}×
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="h-[1px] bg-border-hairline" />

              {/* Verified Facts from Entity Hub */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-[15px] text-emerald-600">verified</span>
                    Verified Facts ({realFacts.length})
                  </span>
                  <Link href="/context-packs" className="text-[10px] font-code-data text-primary hover:underline">
                    Entity Hub
                  </Link>
                </div>

                {realFacts.length === 0 ? (
                  <p className="text-[11px] text-muted-foreground py-1">
                    No verified facts in active pack. Add facts in Entity Hub to track claims.
                  </p>
                ) : (
                  <div className="space-y-1.5">
                    {realFacts.slice(0, 5).map((fact, i) => (
                      <div
                        key={i}
                        className="p-2 rounded bg-surface-subtle border border-border-hairline cursor-pointer hover:border-primary/40 transition"
                        onClick={() => setContent((prev) => prev + `\n\n> Verified Fact: ${fact.text}\n`)}
                        title="Click to insert fact"
                      >
                        <div className="flex items-center justify-between text-foreground font-medium text-xs leading-snug">
                          <span className="text-[11px]">{fact.text}</span>
                          <span className="material-symbols-outlined text-[13px] text-emerald-600 shrink-0 ml-1">check_circle</span>
                        </div>
                        <div className="text-[10px] font-code-data text-muted-foreground mt-0.5">{fact.date}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </aside>
        ) : (
          <button
            onClick={() => setLeftContextCollapsed(false)}
            className="w-8 border-r border-border-hairline bg-surface hover:bg-surface-subtle flex flex-col items-center py-3 text-muted-foreground hover:text-foreground transition"
            title="Expand Context Panel"
          >
            <span className="material-symbols-outlined text-[16px]">last_page</span>
          </button>
        )}

        {/* ========================================================= ZONE 2: CENTER PROSE VIEWPORT */}
        <main className="flex-1 flex flex-col h-full bg-background-canvas overflow-hidden min-w-0">
          {/* Editor Sticky Layer Toolbar */}
          <div className="h-11 w-full bg-surface border-b border-border-hairline px-6 flex items-center justify-between shrink-0 z-10 shadow-xs">
            {/* Quick Actions Micro Toolbar */}
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleMakeAnswerFirst}
                className="h-7 px-2.5 rounded bg-primary-soft text-primary text-xs font-medium flex items-center gap-1 hover:bg-primary/20 transition-colors"
                title="Add a concise answer-first definition lead"
              >
                <span className="material-symbols-outlined text-[14px]">bolt</span>
                <span>Answer Lead</span>
              </button>
              <button
                type="button"
                onClick={handleAddQuestionH2}
                className="h-7 px-2.5 rounded bg-surface border border-border-hairline text-foreground text-xs font-medium flex items-center gap-1 hover:bg-surface-subtle transition-colors"
                title="Add an H2 heading phrased as a question"
              >
                <span className="material-symbols-outlined text-[14px]">help</span>
                <span>Question H2</span>
              </button>
              <button
                type="button"
                onClick={handleAddFaq}
                className="h-7 px-2.5 rounded bg-surface border border-border-hairline text-foreground text-xs font-medium flex items-center gap-1 hover:bg-surface-subtle transition-colors"
                title="Add an FAQ section"
              >
                <span className="material-symbols-outlined text-[14px]">quiz</span>
                <span>+ FAQ</span>
              </button>
              {metrics.bannedViolations.length > 0 && (
                <button
                  type="button"
                  onClick={handleRemoveBannedTerms}
                  className="h-7 px-2.5 rounded bg-danger-soft text-destructive text-xs font-medium flex items-center gap-1 hover:bg-destructive/20 transition-colors"
                  title="Remove unverified claims"
                >
                  <span className="material-symbols-outlined text-[14px]">cleaning_services</span>
                  <span>Fix {metrics.bannedViolations.length} Issue{metrics.bannedViolations.length === 1 ? "" : "s"}</span>
                </button>
              )}
            </div>

            {/* Typography & View Toggles */}
            <div className="flex items-center gap-2 text-xs">
              <div className="flex items-center bg-surface-subtle p-0.5 rounded border border-border-hairline">
                <button
                  onClick={() => setFontFamily("serif")}
                  className={`px-2 py-0.5 rounded text-xs font-medium transition ${
                    fontFamily === "serif" ? "bg-surface shadow-xs text-foreground font-semibold" : "text-muted-foreground"
                  }`}
                >
                  Serif
                </button>
                <button
                  onClick={() => setFontFamily("sans")}
                  className={`px-2 py-0.5 rounded text-xs font-medium transition ${
                    fontFamily === "sans" ? "bg-surface shadow-xs text-foreground font-semibold" : "text-muted-foreground"
                  }`}
                >
                  Sans
                </button>
              </div>

              <button
                onClick={handleCopyText}
                className="h-7 px-2.5 rounded hover:bg-surface-subtle text-muted-foreground hover:text-foreground border border-border-hairline flex items-center gap-1 text-xs font-medium"
                title="Copy Markdown Draft"
              >
                <span className="material-symbols-outlined text-[15px]">content_copy</span>
                <span>{copiedNotification ? "Copied!" : "Copy"}</span>
              </button>
            </div>
          </div>

          {/* Prose Document Scrollport */}
          <div className="flex-1 overflow-y-auto px-6 py-8 flex justify-center">
            {/* 720px Enforced Typographic Column with Margin Gutters */}
            <div className="w-full max-w-[720px] bg-surface rounded-lg shadow-sm border border-border-hairline min-h-[850px] p-10 relative flex flex-col justify-between">
              <div className="space-y-5">
                {/* Document Title Header */}
                <div className="space-y-1 pb-4 border-b border-border-hairline">
                  <input
                    type="text"
                    value={documentTitle}
                    onChange={(e) => setDocumentTitle(e.target.value)}
                    className="w-full bg-transparent font-bold text-2xl tracking-tight text-foreground focus:outline-none placeholder:text-muted-foreground font-sans"
                    placeholder="Document Title…"
                  />
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>Target: <strong>{targetQuery}</strong></span>
                    <span>·</span>
                    <span>{pageType}</span>
                    <span>·</span>
                    <span>{intent} Intent</span>
                  </div>
                </div>

                {/* Diff Mode View vs Interactive Editor */}
                {isDiffMode ? (
                  <div className="space-y-4 font-editor-prose text-[16px] leading-relaxed text-foreground">
                    <div className="p-4 rounded-lg bg-surface-subtle border border-border-hairline space-y-3">
                      <span className="font-code-data text-xs text-primary font-semibold uppercase tracking-wider block">
                        Draft Differences (Current vs Initial)
                      </span>
                      <p className="text-xs text-muted-foreground">
                        Current draft has {content.split(/\s+/).length} words. Baseline draft has {initialContent.split(/\s+/).length} words.
                      </p>
                      <pre className="p-3 bg-surface rounded border border-border-hairline font-code-data text-xs text-foreground overflow-x-auto whitespace-pre-wrap max-h-96">
                        {content}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <div className="relative">
                    {/* Rich Markdown Prose Textarea */}
                    <textarea
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      rows={24}
                      className={`w-full resize-none bg-transparent ${
                        fontFamily === "serif" ? "font-editor-prose text-[17px]" : "font-sans text-[15px]"
                      } leading-[1.8] text-foreground focus:outline-none placeholder:text-muted-foreground select-text`}
                      placeholder="Write or paste your machine-efficient, entity-optimized content here..."
                      spellCheck={false}
                    />
                  </div>
                )}
              </div>

              {/* Bottom In-Editor Status */}
              <div className="pt-6 mt-8 border-t border-border-hairline flex items-center justify-between text-xs text-muted-foreground font-sans">
                <span className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[15px] text-emerald-600">verified_user</span>
                  Machine retrieval ready: <strong>{metrics.wordCount >= 300 ? "Valid length" : "Needs expansion"}</strong>
                </span>
                <span className="font-code-data text-[11px]">{metrics.headings.length} headings structured</span>
              </div>
            </div>
          </div>

          {/* Bottom Telemetry Status Bar */}
          <footer className="h-10 border-t border-border-hairline bg-surface/95 px-6 flex items-center justify-between text-xs text-muted-foreground font-code-data shrink-0 z-10 select-none">
            <div className="flex items-center gap-3">
              <span>{metrics.wordCount} words</span>
              <span>·</span>
              <span>~{metrics.readingTimeMinutes} min read</span>
              <span>·</span>
              <span>Grade {metrics.fleschKincaidGrade} (FK Grade)</span>
              <span>·</span>
              <span>{metrics.sentenceCount} sentences</span>
            </div>

            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
              <span className="text-foreground font-sans font-medium">Ready in editor</span>
            </div>
          </footer>
        </main>

        {/* ========================================================= ZONE 3: RIGHT INTELLIGENCE (380px) */}
        <aside className="w-[380px] shrink-0 border-l border-border-hairline bg-background-canvas flex flex-row h-full overflow-hidden select-none">
          {/* Slim 44px Vertical Icon Rail */}
          <nav className="w-11 shrink-0 border-r border-border-hairline bg-surface-subtle py-3 flex flex-col items-center justify-between">
            <div className="flex flex-col items-center gap-2 w-full">
              <button
                onClick={() => setActiveInspectorTab("overview")}
                className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                  activeInspectorTab === "overview"
                    ? "bg-surface text-primary shadow-xs font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                title="Overview & Diagnostics"
              >
                <span className="material-symbols-outlined text-[18px]">speed</span>
              </button>

              <button
                onClick={() => setActiveInspectorTab("entities")}
                className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                  activeInspectorTab === "entities"
                    ? "bg-surface text-primary shadow-xs font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                title="Entities Map"
              >
                <span className="material-symbols-outlined text-[18px]">category</span>
              </button>

              <button
                onClick={() => setActiveInspectorTab("answers")}
                className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                  activeInspectorTab === "answers"
                    ? "bg-surface text-primary shadow-xs font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                title="Direct Answer Engine"
              >
                <span className="material-symbols-outlined text-[18px]">format_quote</span>
              </button>

              <button
                onClick={() => setActiveInspectorTab("evidence")}
                className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                  activeInspectorTab === "evidence"
                    ? "bg-surface text-primary shadow-xs font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                title="Evidence & Facts"
              >
                <span className="material-symbols-outlined text-[18px]">verified</span>
              </button>

              <button
                onClick={() => setActiveInspectorTab("passages")}
                className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                  activeInspectorTab === "passages"
                    ? "bg-surface text-primary shadow-xs font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                title="Passage Readiness"
              >
                <span className="material-symbols-outlined text-[18px]">format_align_left</span>
              </button>

              <button
                onClick={() => setActiveInspectorTab("hierarchy")}
                className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                  activeInspectorTab === "hierarchy"
                    ? "bg-surface text-primary shadow-xs font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                title="Heading Hierarchy"
              >
                <span className="material-symbols-outlined text-[18px]">account_tree</span>
              </button>
            </div>

            <Link
              href="/settings"
              className="w-8 h-8 rounded-lg text-muted-foreground hover:text-foreground flex items-center justify-center"
              title="Inspector Settings"
            >
              <span className="material-symbols-outlined text-[18px]">settings</span>
            </Link>
          </nav>

          {/* Active Tab Content Area (336px) */}
          <div className="flex-1 h-full overflow-y-auto p-4 space-y-4 font-sans">
            {/* Answer Readiness Score Card */}
            <div className="p-3.5 rounded-xl bg-surface border border-border-hairline shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                  Answer Readiness
                </span>
                <div className="flex items-center gap-1.5">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                    (analysis.data?.overall_score ?? metrics.overallScore) >= 70
                      ? "bg-success-soft text-emerald-800"
                      : "bg-warning-soft text-warning"
                  }`}>
                    <span className="w-1.5 h-1.5 rounded-full bg-current" />
                    {(analysis.data?.overall_score ?? metrics.overallScore) >= 70 ? "Ready" : "In Progress"}
                  </span>
                </div>
              </div>

              <div className="flex items-baseline justify-between pt-1">
                <div className="flex items-baseline gap-2">
                  <span className="font-code-data text-3xl font-bold tracking-tight text-foreground">
                    {analysis.data?.overall_score ?? metrics.overallScore}
                  </span>
                  <span className="text-xs text-muted-foreground font-code-data">/ 100</span>
                </div>
                <div className="flex items-center gap-1 text-[11px] text-muted-foreground" title="Directional index derived from entity grounding, answer conciseness, and citation readiness. Not a search engine rank prediction.">
                  <span>Directional index</span>
                  <span className="material-symbols-outlined text-[14px]">info</span>
                </div>
              </div>

              {/* 5 Dimension Bands — server-computed via POST /workspace/analyze */}
              <div className="space-y-2 pt-2 border-t border-border-hairline text-xs">
                {dimensions.map((dimension) => (
                  <div key={dimension.key} className="space-y-1">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-muted-foreground">{dimension.label}</span>
                      <span className={`${bandTextClass(dimension.band)} font-medium`}>
                        {titleCase(dimension.band)} · {dimension.score}%
                      </span>
                    </div>
                    <div className="w-full h-1.5 bg-surface-subtle rounded-full overflow-hidden">
                      <div
                        className={`h-full ${bandBarClass(dimension.band)} rounded-full`}
                        style={{ width: `${dimension.score}%` }}
                      />
                    </div>
                  </div>
                ))}

                {!dimensions.length && (
                  <div className="py-2 text-[11px] text-muted-foreground">
                    {analysis.isFetching
                      ? "Computing dimension scores from the draft…"
                      : "No analysis yet — add content to compute scores."}
                  </div>
                )}

                {analysis.data?.disclaimer && (
                  <p className="pt-1 text-[10px] leading-snug text-muted-foreground">
                    {analysis.data.disclaimer}
                  </p>
                )}
              </div>
            </div>

            {/* Top Recommendations Stack — server-computed via POST /workspace/analyze */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-xs text-foreground uppercase tracking-wider">
                  Top Recommendations
                </span>
                <span className="w-4 h-4 rounded-full bg-primary-soft text-primary font-code-data text-[10px] flex items-center justify-center font-bold">
                  {pendingSuggestions}
                </span>
              </div>

              {(analysis.data?.recommendations ?? []).slice(0, 4).map((recommendation) => {
                const isHigh = recommendation.impact === "high";
                const isMedium = recommendation.impact === "medium";
                return (
                  <div
                    key={recommendation.id}
                    className={`p-3.5 rounded-xl bg-surface border shadow-xs space-y-2 transition ${
                      isHigh
                        ? "border-destructive/30 hover:border-destructive"
                        : isMedium
                          ? "border-warning/40 hover:border-warning"
                          : "border-border-hairline hover:border-primary"
                    }`}
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`px-2 py-0.5 rounded-full font-semibold ${
                            isHigh
                              ? "bg-danger-soft text-destructive"
                              : isMedium
                                ? "bg-warning-soft text-warning"
                                : "bg-surface-subtle text-muted-foreground"
                          }`}
                        >
                          {isHigh ? "High impact" : isMedium ? "Medium impact" : "Low impact"}
                        </span>
                        <span className="font-code-data font-bold tracking-widest text-[10px] text-muted-foreground">
                          {isHigh ? "●●●" : isMedium ? "●●○" : "●○○"}
                        </span>
                      </div>
                      <span className="font-code-data text-muted-foreground text-[10px]">
                        {recommendation.dimension}
                      </span>
                    </div>

                    <h4 className="font-semibold text-xs text-foreground leading-tight">
                      {recommendation.title}
                    </h4>
                    <p className="text-[12px] text-muted-foreground leading-relaxed">
                      {recommendation.detail}
                    </p>

                    {recommendation.action && (
                      <div className="flex items-center justify-between gap-2 pt-1 border-t border-border-hairline/60">
                        <p className="text-[11px] text-foreground/80 leading-relaxed font-code-data truncate">
                          {recommendation.action}
                        </p>
                        {recommendation.id === "single_h1" && (
                          <button
                            type="button"
                            onClick={handleDemoteExtraH1}
                            className="h-6 px-2 rounded bg-primary text-white text-[11px] font-medium shrink-0 hover:bg-primary-hover transition"
                          >
                            Fix H1
                          </button>
                        )}
                        {recommendation.id === "add_question_heading" && (
                          <button
                            type="button"
                            onClick={handleAddQuestionH2}
                            className="h-6 px-2 rounded bg-primary text-white text-[11px] font-medium shrink-0 hover:bg-primary-hover transition"
                          >
                            Add Question
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

              {!analysis.data && (
                <div className="p-3.5 rounded-xl bg-surface border border-border-hairline text-[12px] text-muted-foreground">
                  {analysis.isFetching
                    ? "Deriving recommendations from the draft…"
                    : "No analysis yet — add content to get recommendations."}
                </div>
              )}

              {analysis.data && analysis.data.recommendations.length === 0 && (
                <div className="p-3.5 rounded-xl bg-surface border border-emerald-500/30 text-[12px] text-emerald-700">
                  No structural issues detected in the deterministic analysis.
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

export default function OptimizerStudioPage() {
  return (
    <Suspense
      fallback={
        <div className="h-[calc(100vh-52px)] flex items-center justify-center text-xs text-muted-foreground font-code-data">
          Loading Aentio Optimizer Studio…
        </div>
      }
    >
      <OptimizerStudioContent />
    </Suspense>
  );
}
