"use client";

import * as React from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useWorkspace } from "@/lib/workspace-context";
import { api } from "@/lib/api";

interface SourceItem {
  id: string;
  type: "question" | "fact" | "gap";
  title: string;
  source: string;
  tag: string;
  tagColor: string;
}

// Placeholder outline shown before "Auto-assemble" runs. Intentionally
// generic: it asserts no brand, price, source or fact. Assembly replaces it
// with the deterministic generator's output.
const SOURCES: SourceItem[] = [
  {
    id: "src-1",
    type: "question",
    title: "How much does this service typically cost?",
    source: "Query pattern · Pricing",
    tag: "High intent",
    tagColor: "bg-primary-soft text-primary",
  },
  {
    id: "src-2",
    type: "fact",
    title: "No verified fact in the active context pack",
    source: "Unverified placeholder",
    tag: "Needs grounding",
    tagColor: "bg-amber-50 text-amber-800",
  },
  {
    id: "src-3",
    type: "gap",
    title: "Coverage gap between current pages and buyer questions",
    source: "Coverage gap · derived",
    tag: "Coverage gap",
    tagColor: "bg-surface-subtle text-muted-foreground",
  },
  {
    id: "src-4",
    type: "question",
    title: "What is the difference between this and the alternatives?",
    source: "Query pattern · Differentiation",
    tag: "Core intent",
    tagColor: "bg-indigo-50 text-indigo-700",
  },
  {
    id: "src-5",
    type: "fact",
    title: "Import a canonical fact to ground this brief",
    source: "Unverified placeholder",
    tag: "Needs grounding",
    tagColor: "bg-amber-50 text-amber-800",
  },
  {
    id: "src-6",
    type: "gap",
    title: "Common mistakes buyers make when choosing a provider",
    source: "Coverage gap · derived",
    tag: "Coverage gap",
    tagColor: "bg-surface-subtle text-muted-foreground",
  },
];

interface OutlineSection {
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

// Placeholder outline sections shown before "Auto-assemble". Generic titles
// and directives only — every fact is an explicit "not grounded" placeholder,
// never an invented claim. Assembly replaces these with generated sections.
const DEFAULT_SECTIONS: OutlineSection[] = [
  {
    id: "sec-1",
    h2Number: 1,
    title: "Why Buyers Need a Specialized Provider",
    badge: "Answer",
    badgeColor: "bg-emerald-50 text-emerald-800",
    entities: [
      { name: "Your brand", type: "Org" },
      { name: "Target service", type: "Service" },
      { name: "Target market", type: "Place" },
    ],
    facts: ["No verified fact in the active context pack — run Auto-assemble"],
    directive:
      "Open with an answer-first definition of the service and who it is for, using the target query and market resolved by the brief generator.",
    wordRange: "120–180 words",
  },
  {
    id: "sec-2",
    h2Number: 2,
    title: "How This Compares to the Alternatives",
    badge: "Compare",
    badgeColor: "bg-primary-soft text-primary",
    entities: [
      { name: "Alternative option", type: "Service" },
      { name: "Comparison dimension", type: "Concept" },
    ],
    facts: ["No verified fact in the active context pack — run Auto-assemble"],
    directive:
      "Contrast the service with the alternatives a buyer is weighing, grounded in canonical facts from the active context pack.",
    wordRange: "250–350 words",
  },
  {
    id: "sec-3",
    h2Number: 3,
    title: "How the Engagement Works in Practice",
    badge: "Explain",
    badgeColor: "bg-amber-50 text-amber-800",
    entities: [
      { name: "Engagement process", type: "Concept" },
      { name: "Delivery cadence", type: "Metric" },
    ],
    facts: ["No verified fact in the active context pack — run Auto-assemble"],
    directive:
      "Walk through the operating process step by step so a buyer can picture what the first engagement looks like.",
    wordRange: "180–240 words",
  },
  {
    id: "sec-4",
    h2Number: 4,
    title: "Pricing Architecture and What Is Included",
    badge: "Pricing",
    badgeColor: "bg-indigo-50 text-indigo-700",
    entities: [
      { name: "Pricing tier", type: "Offer" },
      { name: "Included platform", type: "Platform" },
    ],
    facts: ["No verified fact in the active context pack — run Auto-assemble"],
    directive:
      "State the pricing model and exactly what is included, using canonical fee facts verbatim once they are imported.",
    wordRange: "180–240 words",
  },
  {
    id: "sec-5",
    h2Number: 5,
    title: "Common Mistakes to Avoid",
    badge: "Prove",
    badgeColor: "bg-emerald-50 text-emerald-800",
    entities: [
      { name: "Your brand", type: "Org" },
      { name: "Target market", type: "Place" },
    ],
    facts: ["No verified fact in the active context pack — run Auto-assemble"],
    directive:
      "Review the pitfalls buyers hit in this category, citing approved claims and canonical facts only.",
    wordRange: "200–260 words",
  },
];

export default function BriefBuilderPage() {
  const router = useRouter();
  const { activeProject } = useWorkspace();
  const [sourceFilter, setSourceFilter] = useState<string>("All");
  const [sourcesList, setSourcesList] = useState<SourceItem[]>(SOURCES);
  const [sections, setSections] = useState<OutlineSection[]>(DEFAULT_SECTIONS);
  const [sourceSearch, setSourceSearch] = useState("");
  const [targetQuery, setTargetQuery] = useState(
    activeProject?.brand ? `${activeProject.brand} Strategy Guide` : "AI Search Optimization Strategy"
  );
  const [notice, setNotice] = useState("");
  const [stagedSources, setStagedSources] = useState<SourceItem[]>([]);
  const [showPreview, setShowPreview] = useState(false);
  const [isAssembling, setIsAssembling] = useState(false);
  const [isSampleData, setIsSampleData] = useState(true);
  const [briefDisclaimer, setBriefDisclaimer] = useState("");
  // Constraint labels that come from the backend brief generator once assembled.
  const [wordTarget, setWordTarget] = useState("1,400 – 1,800 words");
  const [readingLevel, setReadingLevel] = useState("Grade 8–9 (FK)");
  const [intentLabel, setIntentLabel] = useState("Commercial Investigation");
  const [infoGainDirectives, setInfoGainDirectives] = useState<string[]>([
    "Lead with a direct answer to the target query in the first two sentences",
    "Do NOT repeat generic checklists or definition lists",
    "Anchor every claim to a verified fact in the active context pack",
  ]);

  // Honest reading-time estimate derived from the word target (≈225 wpm).
  const estimatedReadMinutes = React.useMemo(() => {
    const nums = (wordTarget.match(/\d[\d,]*/g) ?? [])
      .map((n) => parseInt(n.replace(/,/g, ""), 10))
      .filter((n) => Number.isFinite(n));
    if (!nums.length) return null;
    const avg = nums.reduce((a, b) => a + b, 0) / nums.length;
    return Math.max(1, Math.round(avg / 225));
  }, [wordTarget]);

  const showNotice = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(""), 5000);
  };

  const filteredSources = React.useMemo(() => {
    return sourcesList.filter((s) => {
      const matchFilter =
        sourceFilter === "All" ||
        (sourceFilter === "Questions" && s.type === "question") ||
        (sourceFilter === "Facts" && s.type === "fact") ||
        (sourceFilter === "Gaps" && s.type === "gap");
      const matchSearch =
        !sourceSearch || s.title.toLowerCase().includes(sourceSearch.toLowerCase());
      return matchFilter && matchSearch;
    });
  }, [sourcesList, sourceFilter, sourceSearch]);

  const handleAutoAssemble = async () => {
    setIsAssembling(true);
    try {
      const brief = await api.generateContentBrief({
        target_query: targetQuery,
        page_type: "service",
        brand_name: activeProject?.brand || activeProject?.name || "Target Brand",
        location: activeProject?.target_market || "Global / Online",
        project_id: activeProject?.project_id,
      });

      if (brief?.sections?.length) {
        setSections(brief.sections);
      }
      if (brief?.sources?.length) {
        setSourcesList(brief.sources);
      }
      setIsSampleData(false);
      setBriefDisclaimer(brief?.disclaimer ?? "");
      if (brief?.recommended_word_count) setWordTarget(brief.recommended_word_count);
      if (brief?.reading_level) setReadingLevel(brief.reading_level);
      if (brief?.intent) setIntentLabel(brief.intent);
      const directives: string[] = [
        "Lead with a direct answer to the target query in the first two sentences",
      ];
      if (brief?.lexicon?.replace?.length) {
        const r = brief.lexicon.replace[0];
        directives.push(`Replace generic superlatives — e.g. “${r.from}” → “${r.to}”`);
      }
      if (brief?.lexicon?.avoid?.length) {
        directives.push(`Avoid banned terms: ${brief.lexicon.avoid.join(", ")}`);
      }
      directives.push("Anchor every claim to a verified fact in the active context pack");
      setInfoGainDirectives(directives);
      showNotice(
        `Assembled ${brief.sections?.length || 4} strategic outline sections & ${brief.sources?.length || 4} research sources from backend engine.`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to assemble brief";
      showNotice(`Brief assembly error: ${msg}`);
    } finally {
      setIsAssembling(false);
    }
  };

  const handleSendToEditor = () => {
    const draftMarkdown = [
      `# ${targetQuery}`,
      "",
      `*A comprehensive, structured guide for ${activeProject?.brand || "modern operations"}.*`,
      "",
      ...sections.flatMap((s) => [
        `## ${s.title}`,
        "",
        s.directive,
        "",
        `> **Key Entities**: ${s.entities.map((e) => e.name).join(", ")}`,
        `> **Verified Proof**: ${s.facts.join("; ")}`,
        "",
      ]),
    ].join("\n");

    if (typeof window !== "undefined") {
      sessionStorage.setItem("aentio_optimizer_initial_draft", draftMarkdown);
      sessionStorage.setItem("aentio_optimizer_initial_query", targetQuery);
    }

    router.push(
      `/optimizer?brief=true&title=${encodeURIComponent(targetQuery)}`
    );
  };

  const handleAddSection = () => {
    const nextNum = sections.length + 1;
    const newSec: OutlineSection = {
      id: `sec-${Date.now()}`,
      h2Number: nextNum,
      title: "New Strategic Section",
      badge: "Structure",
      badgeColor: "bg-surface-subtle text-foreground",
      entities: [{ name: "Core Entity", type: "Concept" }],
      facts: ["Canonical fact pending verification"],
      directive: "Answer the searcher's core question in the first 2-3 sentences...",
      wordRange: "150–250 words",
    };
    setSections([...sections, newSec]);
  };

  const handleStageSource = (item: SourceItem) => {
    if (stagedSources.some((s) => s.id === item.id)) {
      showNotice(`"${item.title}" is already staged — local draft, session only.`);
      return;
    }
    setStagedSources((prev) => [...prev, item]);
    showNotice(`Staged "${item.title}" to the outline — local draft, session only.`);
  };

  return (
    <div className="flex flex-col w-full min-h-[calc(100vh-52px)] bg-background-canvas">
      {/* ------------------------------------------------------------- TOP COMMAND / BREADCRUMB BAR */}
      <div className="w-full bg-surface border-b border-border-hairline px-6 py-2.5 flex items-center justify-between select-none">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-muted-foreground font-medium">Briefs</span>
            <span className="text-muted-foreground text-[10px] font-code-data">/</span>
            <input
              type="text"
              value={targetQuery}
              onChange={(e) => setTargetQuery(e.target.value)}
              placeholder="Target Query..."
              className="text-foreground font-bold bg-transparent border-b border-dashed border-border-hairline hover:border-primary focus:border-primary focus:outline-hidden px-1 py-0.5 max-w-[280px]"
            />
          </div>
          <div className="h-4 w-px bg-border-hairline hidden sm:block" />
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-800 font-medium text-xs border border-amber-200">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
            <span>Outline in progress · {sections.length} sections planned</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleAutoAssemble}
            disabled={isAssembling}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-primary bg-primary-soft hover:bg-surface-subtle transition-colors rounded-lg border border-border-hairline disabled:opacity-50"
          >
            <span className="material-symbols-outlined text-[15px] text-primary">
              {isAssembling ? "refresh" : "auto_awesome"}
            </span>
            <span className="hidden sm:inline">
              {isAssembling ? "Assembling…" : "Auto-assemble from Research"}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setShowPreview(true)}
            className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface-subtle transition-colors rounded-lg border border-border-hairline"
          >
            <span className="material-symbols-outlined text-[15px] text-muted-foreground">visibility</span>
            <span>Preview Brief</span>
          </button>
          <button
            type="button"
            onClick={handleSendToEditor}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium text-white bg-primary hover:bg-primary-hover shadow-xs transition-all rounded-lg"
          >
            <span>Send to editor</span>
            <span className="material-symbols-outlined text-[15px]">arrow_forward</span>
          </button>
        </div>
      </div>

      {isSampleData ? (
        <div className="w-full border-b border-amber-200 bg-amber-50 px-6 py-2 text-xs text-amber-900 flex items-center gap-2">
          <span className="material-symbols-outlined text-[15px]">info</span>
          <span>
            Showing a <strong>sample outline</strong> with placeholder sources and facts. Click{" "}
            <strong>Auto-assemble from Research</strong> to build a brief from your project&rsquo;s
            real audit coverage and context-pack facts.
          </span>
        </div>
      ) : briefDisclaimer ? (
        <div className="w-full border-b border-border-hairline bg-surface-subtle px-6 py-2 text-[11px] text-muted-foreground flex items-center gap-2">
          <span className="material-symbols-outlined text-[15px]">verified</span>
          <span>{briefDisclaimer}</span>
        </div>
      ) : null}

      {/* ------------------------------------------------------------- 3-COLUMN WORKSPACE */}
      <div className="w-full grid grid-cols-1 xl:grid-cols-[330px_minmax(640px,760px)_340px] justify-center gap-6 px-6 py-4 max-w-[1720px] mx-auto items-start">
        {/* LEFT PANEL: Source Pool (330px) */}
        <section className="bg-surface rounded-xl border border-border-hairline shadow-xs flex flex-col overflow-hidden sticky top-[72px] max-h-[calc(100vh-90px)]">
          <div className="p-3.5 border-b border-border-hairline flex flex-col gap-2 bg-surface">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="material-symbols-outlined text-primary text-[17px]">inventory_2</span>
                <h2 className="text-xs font-bold text-foreground uppercase tracking-wider">Source Pool</h2>
              </div>
              <span className="font-code-data text-[10px] px-1.5 py-0.5 rounded bg-surface-subtle text-muted-foreground border border-border-hairline">
                {sourcesList.length} sources
              </span>
            </div>

            {/* Filter Tabs */}
            <div className="flex items-center gap-1 overflow-x-auto pb-0.5 text-xs">
              {["All", "Questions", "Facts", "Gaps"].map((tab) => {
                const active = sourceFilter === tab;
                return (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setSourceFilter(tab)}
                    className={`px-2 py-0.5 rounded text-[11px] font-medium whitespace-nowrap transition-colors ${
                      active
                        ? "text-primary bg-primary-soft font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {tab}
                  </button>
                );
              })}
            </div>

            {/* Search Filter */}
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-2.5 text-muted-foreground text-[15px]">
                filter_list
              </span>
              <input
                type="text"
                value={sourceSearch}
                onChange={(e) => setSourceSearch(e.target.value)}
                placeholder="Filter mined sources..."
                className="w-full h-7 pl-8 pr-3 text-xs bg-surface-subtle rounded-lg border border-border-hairline text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:bg-surface transition-colors"
              />
            </div>
          </div>

          {/* Draggable Source List */}
          <div className="flex-1 overflow-y-auto p-2.5 space-y-2 max-h-[560px]">
            {filteredSources.map((item) => (
              <div
                key={item.id}
                draggable
                className="group p-2.5 rounded-lg border border-border-hairline bg-surface hover:border-primary/40 hover:shadow-xs cursor-grab active:cursor-grabbing transition-all text-xs"
              >
                <div className="flex items-start gap-2">
                  <span className="material-symbols-outlined text-muted-foreground text-[15px] mt-0.5 opacity-50 group-hover:opacity-100 select-none">
                    drag_indicator
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-foreground leading-snug">{item.title}</p>
                    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                      <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-code-data bg-surface-subtle text-muted-foreground border border-border-hairline">
                        {item.source}
                      </span>
                      <span className={`inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-medium ${item.tagColor}`}>
                        {item.tag}
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleStageSource(item)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-muted-foreground hover:text-primary rounded transition-all"
                    title="Stage in outline (local draft, session only)"
                  >
                    <span className="material-symbols-outlined text-[16px]">
                      {stagedSources.some((s) => s.id === item.id) ? "check_circle" : "add_circle"}
                    </span>
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Staged sources — in-memory only */}
          {stagedSources.length > 0 && (
            <div
              className="border-t border-border-hairline bg-surface-subtle/60 p-2.5 space-y-1.5"
              data-testid="staged-sources"
            >
              <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                <span>Staged for outline</span>
                <span className="font-code-data normal-case tracking-normal text-primary">
                  local draft · session only
                </span>
              </div>
              <ul className="space-y-1">
                {stagedSources.map((s) => (
                  <li key={s.id} className="flex items-center gap-1 text-[11px] text-foreground">
                    <span className="material-symbols-outlined text-[13px] text-primary">check_circle</span>
                    <span className="truncate">{s.title}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="p-2.5 bg-surface-subtle border-t border-border-hairline text-center text-xs text-muted-foreground">
            <p className="flex items-center justify-center gap-1 text-[11px]">
              <span className="material-symbols-outlined text-[13px]">touch_app</span>
              Drag cards to outline sections or drop to create H2
            </p>
          </div>
        </section>

        {/* CENTER ZONE: Document Outline (680px-720px max) */}
        <main className="flex flex-col gap-3 w-full">
          {/* Target Summary Strip */}
          <div className="flex items-center justify-between px-4 py-2.5 rounded-xl bg-surface border border-border-hairline text-xs">
            <div className="flex items-center gap-3 divide-x divide-border-hairline">
              <div className="flex items-center gap-1.5 font-medium text-foreground">
                <span className="material-symbols-outlined text-[15px] text-muted-foreground">tune</span>
                <span>Target: <strong className="font-bold text-foreground">{wordTarget}</strong></span>
              </div>
              <div className="pl-3 text-muted-foreground flex items-center gap-1 font-code-data text-[11px]">
                <span className="material-symbols-outlined text-[13px]">schedule</span>
                <span>Est. {estimatedReadMinutes ?? "—"} min read</span>
              </div>
              <div className="pl-3 text-muted-foreground flex items-center gap-1 font-code-data text-[11px]">
                <span className="material-symbols-outlined text-[13px]">format_list_numbered</span>
                <span>{sections.length} structured H2s</span>
              </div>
            </div>
            <button
              type="button"
              onClick={handleAddSection}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-foreground hover:bg-surface-subtle rounded-lg border border-border-hairline transition-colors"
            >
              <span className="material-symbols-outlined text-[15px]">add</span>
              <span>Add section</span>
            </button>
          </div>

          {/* Outline Section Cards Stack */}
          <div className="space-y-3">
            {sections.map((sec) => (
              <article
                key={sec.id}
                className="bg-surface rounded-xl border border-border-hairline p-4 hover:shadow-xs transition-all relative group"
              >
                <div className="flex items-start justify-between gap-2 pb-2.5 border-b border-border-hairline">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-muted-foreground text-[16px] cursor-grab select-none">
                      drag_indicator
                    </span>
                    <span className="font-code-data text-[10px] font-bold text-muted-foreground bg-surface-subtle px-1.5 py-0.5 rounded border border-border-hairline">
                      H2 #{sec.h2Number}
                    </span>
                    <h3 className="text-sm font-bold text-foreground">{sec.title}</h3>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${sec.badgeColor}`}>
                      {sec.badge}
                    </span>
                    <button type="button" className="p-1 text-muted-foreground hover:text-foreground rounded">
                      <span className="material-symbols-outlined text-[15px]">more_vert</span>
                    </button>
                  </div>
                </div>

                <div className="mt-2.5 space-y-2 text-xs">
                  {/* Entities Row */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-muted-foreground font-medium text-[11px]">Target Entities:</span>
                    {sec.entities.map((ent, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-code-data bg-primary-soft text-primary"
                      >
                        {ent.name} <span className="text-[9px] opacity-75">· {ent.type}</span>
                      </span>
                    ))}
                  </div>

                  {/* Required Facts */}
                  <div className="flex items-center gap-1.5 text-foreground flex-wrap">
                    <span className="text-[11px] text-muted-foreground font-medium">Required Facts:</span>
                    {sec.facts.map((fact, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 text-[11px] text-emerald-800 font-code-data bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200"
                      >
                        ✓ {fact}
                      </span>
                    ))}
                  </div>

                  {/* Answer-first Stub */}
                  <div className="p-2.5 rounded-lg bg-surface-subtle border border-border-hairline">
                    <div className="flex items-center justify-between text-[10px] text-muted-foreground font-semibold uppercase tracking-wider mb-1">
                      <span>Answer-First Lead Directive</span>
                      <span className="font-code-data">{sec.wordRange}</span>
                    </div>
                    <p className="font-serif italic text-xs text-foreground leading-relaxed">
                      &ldquo;{sec.directive}&rdquo;
                    </p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </main>

        {/* RIGHT PANEL: Content Constraints & Writer Notes (340px) */}
        <aside className="flex flex-col gap-3 sticky top-[72px] max-h-[calc(100vh-90px)] overflow-y-auto">
          {/* Section 1: Content Constraints */}
          <div className="bg-surface rounded-xl border border-border-hairline p-4 shadow-xs">
            <h3 className="text-xs font-bold text-foreground uppercase tracking-wider mb-3 flex items-center justify-between">
              <span>Content Constraints</span>
              <span className="material-symbols-outlined text-muted-foreground text-[16px]">tune</span>
            </h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-muted-foreground font-medium text-[10px] uppercase tracking-wider mb-1">
                  Target Audience
                </label>
                <div className="p-2 rounded-lg bg-surface-subtle border border-border-hairline text-foreground font-medium text-xs">
                  {activeProject?.target_market ? `Operational decision makers · ${activeProject.target_market}` : "Commercial decision makers & practitioners"}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-muted-foreground font-medium text-[10px] uppercase tracking-wider mb-1">
                    Tone Profile
                  </label>
                  <div className="p-2 rounded-lg bg-surface-subtle border border-border-hairline text-foreground truncate text-xs">
                    Authoritative, practical
                  </div>
                </div>
                <div>
                  <label className="block text-muted-foreground font-medium text-[10px] uppercase tracking-wider mb-1">
                    Reading Level
                  </label>
                  <div className="p-2 rounded-lg bg-surface-subtle border border-border-hairline text-foreground font-code-data text-xs">
                    {readingLevel}
                  </div>
                </div>
              </div>
              <div>
                <label className="block text-muted-foreground font-medium text-[10px] uppercase tracking-wider mb-1">
                  Primary Search Intent
                </label>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-primary-soft text-primary font-medium text-xs">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                  {intentLabel}
                </span>
              </div>
            </div>
          </div>

          {/* Section 2: Information Gain Directives */}
          <div className="bg-primary-soft/40 rounded-xl border border-primary/20 p-4 shadow-xs">
            <div className="flex items-center gap-1.5 text-primary mb-2">
              <span className="material-symbols-outlined text-[16px]">verified</span>
              <h3 className="text-xs font-bold uppercase tracking-wider">Information Gain Directives</h3>
            </div>
            <ul className="space-y-2 text-xs text-foreground">
              {infoGainDirectives.map((directive, i) => {
                const isAvoid = /^(Do NOT|Avoid)/i.test(directive);
                return (
                  <li key={i} className="flex items-start gap-1.5 leading-snug">
                    <span className={isAvoid ? "text-rose-700 font-bold" : "text-primary font-bold"}>
                      •
                    </span>
                    <span className={isAvoid ? "font-semibold text-rose-700" : ""}>
                      {directive}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Send to Editor CTA */}
          <button
            type="button"
            onClick={handleSendToEditor}
            className="w-full py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-white text-xs font-medium shadow-xs transition-colors flex items-center justify-center gap-2"
          >
            <span>Open in Optimizer Studio</span>
            <span className="material-symbols-outlined text-[15px]">arrow_forward</span>
          </button>
        </aside>
      </div>

      {/* Inline, non-blocking notice for actions that cannot be completed locally */}
      {notice && (
        <div
          role="status"
          className="fixed bottom-4 right-4 z-50 max-w-sm rounded-lg border border-border-hairline bg-surface px-3 py-2 text-xs text-foreground shadow-lg"
        >
          {notice}
        </div>
      )}

      {/* Writer brief preview — renders the real in-memory outline, nothing is generated */}
      {showPreview && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-surface rounded-xl border border-border-hairline shadow-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto p-5 space-y-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h3 className="text-base font-bold text-foreground">Writer brief preview</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {targetQuery} · {sections.length} section{sections.length === 1 ? "" : "s"} in this
                  session&apos;s outline
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowPreview(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <span className="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>

            <div className="space-y-3">
              {sections.map((sec) => (
                <div key={sec.id} className="rounded-lg border border-border-hairline p-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="font-code-data text-[10px] font-bold text-muted-foreground bg-surface-subtle px-1.5 py-0.5 rounded border border-border-hairline">
                      H2 #{sec.h2Number}
                    </span>
                    <h4 className="text-sm font-bold text-foreground">{sec.title}</h4>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {sec.entities.map((ent, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-code-data bg-primary-soft text-primary"
                      >
                        {ent.name}
                      </span>
                    ))}
                  </div>
                  <p className="font-serif italic text-xs text-foreground leading-relaxed">
                    &ldquo;{sec.directive}&rdquo;
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {sec.facts.map((fact, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 text-[10px] text-emerald-800 font-code-data bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200"
                      >
                        ✓ {fact}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <p className="text-[10px] text-muted-foreground">
              Preview of the current session outline only. No content has been generated or saved.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
