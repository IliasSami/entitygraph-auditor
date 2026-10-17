"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useWorkspace } from "@/lib/workspace-context";
import { api } from "@/lib/api";
import { formatDateTime, titleCase } from "@/lib/format";
import { usePageTitle } from "@/lib/use-page-title";
import type { AuditListRow } from "@/lib/types";

interface VisibilitySummaryResponse {
  success?: boolean;
  data?: {
    summary?: {
      totalPrompts?: number;
      totalRuns?: number;
      avgMentionRate?: number;
      brandCitations?: number;
      citationProbability?: number;
      effectiveVisibilityIndex?: number;
    };
  };
}

export default function HomeDashboardPage() {
  usePageTitle("Home · Aentio");
  const { activeProject } = useWorkspace();
  const [filterQueue, setFilterQueue] = useState<"all" | "blockers" | "facts" | "mentions">("all");
  const [searchQuery, setSearchQuery] = useState("");

  const auditsQuery = useQuery({
    queryKey: ["audits"],
    queryFn: () => api.listAudits(),
  });

  const visibilityQuery = useQuery<VisibilitySummaryResponse>({
    queryKey: ["visibility-metrics"],
    queryFn: async () => {
      const res = await fetch("/api/visibility");
      if (!res.ok) return {};
      return res.json();
    },
  });

  const audits: AuditListRow[] = useMemo(() => auditsQuery.data ?? [], [auditsQuery.data]);
  const visibilitySummary = visibilityQuery.data?.data?.summary;

  const [referenceTimestamp] = useState(() => Date.now());

  const totalAudits = audits.length;
  const passedAudits = audits.filter(
    (a) => a.gate_status === "pass" || a.gate_status === "pass_with_fixes"
  ).length;
  const blockerAudits = audits.filter((a) => a.gate_status === "fail").length;

  const avgComposite = useMemo(() => {
    const valid = audits.filter((a) => typeof a.composite === "number");
    if (!valid.length) return null;
    return (valid.reduce((acc, a) => acc + (a.composite ?? 0), 0) / valid.length).toFixed(1);
  }, [audits]);

  const recentAuditsCount = useMemo(() => {
    const thirtyDaysAgo = referenceTimestamp - 30 * 24 * 60 * 60 * 1000;
    return audits.filter((a) => new Date(a.created_at).getTime() >= thirtyDaysAgo).length;
  }, [audits, referenceTimestamp]);

  const geoMentionRate =
    visibilitySummary?.avgMentionRate != null
      ? Math.round(visibilitySummary.avgMentionRate * 100)
      : null;

  // Attention Queue items: strictly real failing or evaluated audits
  const attentionItems = useMemo(() => {
    const candidateAudits = audits.filter(
      (a) => a.gate_status === "fail" || a.gate_status === "not_configured" || a.gate_status === "pass_with_fixes"
    );

    const itemsToMap = candidateAudits.length > 0 ? candidateAudits : audits;

    return itemsToMap
      .slice(0, 8)
      .map((a) => ({
        id: a.audit_id,
        title: a.primary_query || a.central_entity || `Audit ${a.audit_id.slice(0, 8)}`,
        path: `/audits/${a.audit_id}`,
        tag: titleCase(a.page_type),
        status:
          a.gate_status === "fail"
            ? "Gate blocker"
            : a.gate_status === "pass_with_fixes"
              ? "Pass with fixes"
              : a.gate_status === "pass"
                ? "Passing"
                : "Pack missing",
        statusType:
          a.gate_status === "fail"
            ? ("danger" as const)
            : a.gate_status === "pass"
              ? ("success" as const)
              : ("warning" as const),
        issue:
          a.gate_status === "fail"
            ? "Editorial and entity validation criteria failed. Review violations in audit workspace."
            : a.gate_status === "pass_with_fixes"
              ? "Passing with recommended fixes. Review score deductions."
              : a.gate_status === "pass"
                ? "All publication gates passed. Ready for distribution."
                : "No active context pack attached to run. Brand facts and claims ungrounded.",
        time: formatDateTime(a.created_at),
        category: a.gate_status === "fail" ? "blockers" : "facts",
        isReal: true,
      }))
      .filter((item) => {
        if (filterQueue !== "all" && item.category !== filterQueue) return false;
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          return item.title.toLowerCase().includes(q) || item.issue.toLowerCase().includes(q);
        }
        return true;
      });
  }, [audits, filterQueue, searchQuery]);

  return (
    <div className="w-full px-6 py-6 flex flex-col gap-6 max-w-[1440px] mx-auto select-none font-sans">
      {/* ------------------------------------------------------------- HEADER AREA */}
      <header className="flex flex-col gap-4 border-b border-border-hairline pb-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground font-sans">
              Good afternoon{activeProject?.brand ? `, ${activeProject.brand}` : ""}
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5 flex items-center gap-2">
              <span>{totalAudits > 0 ? `${blockerAudits} audits need attention` : "Workspace active"}</span>
              <span className="w-1 h-1 rounded-full bg-border-hairline" />
              <span className="text-foreground font-medium">
                {totalAudits > 0 ? `${totalAudits} total recorded audits` : "Ready to optimize content & run audits"}
              </span>
              <span className="w-1 h-1 rounded-full bg-border-hairline" />
              <span>{visibilitySummary ? "PrismGEO engine live" : "Entity knowledge graph active"}</span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Link
              href="/audits/new"
              className="h-9 px-3 rounded-lg bg-surface border border-border-hairline text-foreground text-xs font-medium hover:bg-surface-subtle transition-colors flex items-center gap-1.5 shadow-xs"
            >
              <span className="material-symbols-outlined text-[16px] text-muted-foreground">add_link</span>
              <span>Import URL</span>
            </Link>

            <Link
              href="/briefs"
              className="h-9 px-3 rounded-lg bg-surface border border-border-hairline text-foreground text-xs font-medium hover:bg-surface-subtle transition-colors flex items-center gap-1.5 shadow-xs"
            >
              <span className="material-symbols-outlined text-[16px] text-muted-foreground">note_add</span>
              <span>Create brief</span>
            </Link>

            <Link
              href="/optimizer"
              className="h-9 px-3.5 rounded-lg bg-primary text-white text-xs font-medium hover:bg-primary-hover transition-colors flex items-center gap-1.5 shadow-xs"
            >
              <span className="material-symbols-outlined text-[16px]">auto_awesome</span>
              <span>Optimize a page</span>
            </Link>
          </div>
        </div>

        {/* Quick Finder Command Bar */}
        <div className="relative w-full max-w-xl">
          <span className="material-symbols-outlined absolute left-3 top-2.5 text-muted-foreground text-[18px]">
            search
          </span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search pages, entities, or commands... ⌘K"
            className="w-full h-10 pl-9 pr-12 rounded-lg bg-surface border border-border-hairline text-xs font-medium text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary shadow-xs transition-all"
          />
          <div className="absolute right-2.5 top-2 flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-surface-subtle border border-border-hairline text-[10px] font-code-data text-muted-foreground pointer-events-none">
            <span>⌘</span>K
          </div>
        </div>
      </header>

      {/* ------------------------------------------------------------- 4 METRIC CARDS */}
      <section aria-label="Key Readiness Metrics" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1 */}
        <div className="bg-surface rounded-xl border border-border-hairline p-4 flex flex-col justify-between shadow-xs hover:border-primary/40 transition-colors group">
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="text-xs font-medium text-muted-foreground tracking-tight">Pages ready</span>
            {totalAudits > 0 ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-code-data font-medium px-1.5 py-0.5 rounded bg-success-soft text-emerald-800">
                <span className="material-symbols-outlined text-[12px]">verified</span> live audits
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-[10px] font-code-data font-medium px-1.5 py-0.5 rounded bg-surface-subtle text-muted-foreground border border-border-hairline">
                live
              </span>
            )}
          </div>
          <div className="flex items-baseline justify-between mb-2">
            <div className="flex items-baseline gap-1.5">
              <span className="text-[28px] leading-8 font-bold text-foreground font-code-data tracking-tight">
                {passedAudits}
              </span>
              <span className="text-xs font-code-data text-muted-foreground">
                / {totalAudits}
              </span>
            </div>
            {/* Sparkline Upward Green */}
            <div className="w-20 h-7 text-emerald-600 flex items-center">
              <svg className="w-full h-full overflow-visible" fill="none" viewBox="0 0 80 28">
                <path
                  d="M2 24 C18 22, 28 16, 42 17 C54 18, 62 8, 78 4"
                  stroke="currentColor"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="1.75"
                />
                <circle cx="78" cy="4" fill="currentColor" r="2.5" />
              </svg>
            </div>
          </div>
          <p className="text-[11px] text-muted-foreground pt-2 border-t border-border-hairline leading-snug">
            {totalAudits > 0
              ? `${passedAudits} passed out of ${totalAudits} audits evaluated`
              : "No audits yet — start an audit to track page readiness"}
          </p>
        </div>

        {/* Metric 2 */}
        <div className="bg-surface rounded-xl border border-border-hairline p-4 flex flex-col justify-between shadow-xs hover:border-primary/40 transition-colors group">
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="text-xs font-medium text-muted-foreground tracking-tight">Entity consistency</span>
            {avgComposite ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-code-data font-medium px-1.5 py-0.5 rounded bg-primary-soft text-primary">
                <span className="material-symbols-outlined text-[12px]">calculate</span> {avgComposite}/10 avg
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-[10px] font-code-data font-medium px-1.5 py-0.5 rounded bg-surface-subtle text-muted-foreground border border-border-hairline">
                heuristic
              </span>
            )}
          </div>
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-[28px] leading-8 font-bold text-foreground font-code-data tracking-tight">
              {avgComposite ? `${Math.round((parseFloat(avgComposite) / 10) * 100)}%` : "—"}
            </span>
            {/* Sparkline Indigo Steady */}
            <div className="w-20 h-7 text-primary flex items-center">
              <svg className="w-full h-full overflow-visible" fill="none" viewBox="0 0 80 28">
                <path
                  d="M2 19 C18 20, 30 14, 44 13 C58 12, 66 8, 78 6"
                  stroke="currentColor"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="1.75"
                />
                <circle cx="78" cy="6" fill="currentColor" r="2.5" />
              </svg>
            </div>
          </div>
          <p className="text-[11px] text-muted-foreground pt-2 border-t border-border-hairline leading-snug">
            {avgComposite
              ? "Calculated from average composite audit score"
              : "Evaluated across canonical names and verified claims"}
          </p>
        </div>

        {/* Metric 3 */}
        <div className="bg-surface rounded-xl border border-border-hairline p-4 flex flex-col justify-between shadow-xs hover:border-primary/40 transition-colors group">
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="text-xs font-medium text-muted-foreground tracking-tight">AI mention rate</span>
            {geoMentionRate != null ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-code-data font-medium px-1.5 py-0.5 rounded bg-primary-soft text-primary">
                <span className="material-symbols-outlined text-[12px]">dataset</span> PrismGEO live
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-[10px] font-code-data font-medium px-1.5 py-0.5 rounded bg-surface-subtle text-muted-foreground border border-border-hairline">
                live
              </span>
            )}
          </div>
          <div className="flex items-baseline justify-between mb-2">
            <div className="flex items-baseline gap-1">
              <span className="text-[28px] leading-8 font-bold text-foreground font-code-data tracking-tight">
                {geoMentionRate != null ? `${geoMentionRate}%` : "—"}
              </span>
              {visibilitySummary?.totalRuns ? (
                <span className="text-[11px] font-code-data text-muted-foreground">
                  from {visibilitySummary.totalRuns} runs
                </span>
              ) : null}
            </div>
            {/* Sparkline Indigo Rising */}
            <div className="w-20 h-7 text-primary flex items-center">
              <svg className="w-full h-full overflow-visible" fill="none" viewBox="0 0 80 28">
                <path
                  d="M2 25 C14 24, 26 21, 38 18 C50 14, 64 8, 78 3"
                  stroke="currentColor"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="1.75"
                />
                <circle cx="78" cy="3" fill="currentColor" r="2.5" />
              </svg>
            </div>
          </div>
          <p className="text-[11px] text-muted-foreground pt-2 border-t border-border-hairline leading-snug">
            {visibilitySummary
              ? `Wilson 95% interval on ${visibilitySummary.totalPrompts ?? 0} benchmark prompts`
              : "Simulated brand retrieval across AI answer engines"}
          </p>
        </div>

        {/* Metric 4 */}
        <div className="bg-surface rounded-xl border border-border-hairline p-4 flex flex-col justify-between shadow-xs hover:border-primary/40 transition-colors group">
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="text-xs font-medium text-muted-foreground tracking-tight">Fresh audits</span>
            {totalAudits > 0 ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-code-data font-medium px-1.5 py-0.5 rounded bg-warning-soft text-warning">
                <span className="material-symbols-outlined text-[12px]">schedule</span> {recentAuditsCount} active
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-[10px] font-code-data font-medium px-1.5 py-0.5 rounded bg-surface-subtle text-muted-foreground border border-border-hairline">
                live
              </span>
            )}
          </div>
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-[28px] leading-8 font-bold text-foreground font-code-data tracking-tight">
              {totalAudits > 0 ? `${Math.round((recentAuditsCount / (totalAudits || 1)) * 100)}%` : "—"}
            </span>
            {/* Sparkline Amber Steady */}
            <div className="w-20 h-7 text-warning flex items-center">
              <svg className="w-full h-full overflow-visible" fill="none" viewBox="0 0 80 28">
                <path
                  d="M2 14 C16 12, 28 17, 44 14 C56 12, 66 15, 78 13"
                  stroke="currentColor"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="1.75"
                />
                <circle cx="78" cy="13" fill="currentColor" r="2.5" />
              </svg>
            </div>
          </div>
          <p className="text-[11px] text-muted-foreground pt-2 border-t border-border-hairline leading-snug">
            {totalAudits > 0
              ? `${recentAuditsCount} audits recorded in the last 30 days`
              : "Audit re-verifications in the last 30 days"}
          </p>
        </div>
      </section>

      {/* ------------------------------------------------------------- 8/4 MAIN SECTION */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left 8 Cols: Attention Queue */}
        <section className="lg:col-span-8 flex flex-col bg-surface rounded-xl border border-border-hairline shadow-xs overflow-hidden">
          {/* Header */}
          <div className="px-4 py-3 border-b border-border-hairline flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-foreground tracking-tight">Attention queue</h2>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-code-data font-medium bg-danger-soft text-destructive">
                {attentionItems.length} priority items
              </span>
            </div>

            {/* Filter Pill Group */}
            <div className="inline-flex rounded-lg bg-surface-subtle p-0.5 border border-border-hairline text-xs">
              <button
                onClick={() => setFilterQueue("all")}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition ${
                  filterQueue === "all" ? "bg-surface text-foreground font-semibold shadow-xs" : "text-muted-foreground"
                }`}
              >
                All
              </button>
              <button
                onClick={() => setFilterQueue("blockers")}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition ${
                  filterQueue === "blockers" ? "bg-surface text-foreground font-semibold shadow-xs" : "text-muted-foreground"
                }`}
              >
                Blockers
              </button>
              <button
                onClick={() => setFilterQueue("facts")}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition ${
                  filterQueue === "facts" ? "bg-surface text-foreground font-semibold shadow-xs" : "text-muted-foreground"
                }`}
              >
                Stale facts
              </button>
              <button
                onClick={() => setFilterQueue("mentions")}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition ${
                  filterQueue === "mentions" ? "bg-surface text-foreground font-semibold shadow-xs" : "text-muted-foreground"
                }`}
              >
                Mentions
              </button>
            </div>
          </div>

          {/* Attention Items List */}
          <div className="divide-y divide-border-hairline text-xs">
            {attentionItems.length === 0 ? (
              <div className="p-8 text-center flex flex-col items-center justify-center gap-3">
                <div className="w-10 h-10 rounded-full bg-surface-subtle flex items-center justify-center text-primary">
                  <span className="material-symbols-outlined text-[20px]">check_circle</span>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">
                    {totalAudits > 0 ? "No Active Gate Blockers" : "No Audits Yet"}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
                    {totalAudits > 0
                      ? "All evaluated pages meet entity grounding, publication gates, and search engine readiness criteria."
                      : "Start by optimizing a page, building a content brief, or running an entity audit on any URL."}
                  </p>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-2 mt-2">
                  <Link
                    href="/optimizer"
                    className="h-8 px-3 rounded-lg bg-primary text-white text-xs font-medium hover:bg-primary-hover flex items-center gap-1.5 transition shadow-xs"
                  >
                    <span className="material-symbols-outlined text-[15px]">auto_awesome</span>
                    <span>Open Optimizer</span>
                  </Link>
                  <Link
                    href="/briefs"
                    className="h-8 px-3 rounded-lg bg-surface border border-border-hairline text-foreground text-xs font-medium hover:bg-surface-subtle flex items-center gap-1.5 transition shadow-xs"
                  >
                    <span className="material-symbols-outlined text-[15px]">note_add</span>
                    <span>Create Brief</span>
                  </Link>
                  <Link
                    href="/audits/new"
                    className="h-8 px-3 rounded-lg bg-surface border border-border-hairline text-foreground text-xs font-medium hover:bg-surface-subtle flex items-center gap-1.5 transition shadow-xs"
                  >
                    <span className="material-symbols-outlined text-[15px]">add_link</span>
                    <span>Run Audit</span>
                  </Link>
                </div>
              </div>
            ) : (
              attentionItems.map((item) => (
                <div key={item.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-surface-subtle/50 transition">
                  <div className="space-y-1 min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-foreground text-sm truncate">{item.title}</span>
                      <span className="px-1.5 py-0.2 rounded bg-surface-subtle border border-border-hairline text-[10px] text-muted-foreground font-medium">
                        {item.tag}
                      </span>
                    </div>
                    <p className="text-muted-foreground text-xs leading-relaxed">{item.issue}</p>
                    <div className="flex items-center gap-2 text-[10px] font-code-data text-muted-foreground">
                      <span className="truncate">{item.path}</span>
                      <span>·</span>
                      <span>{item.time}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-medium font-code-data ${
                        item.statusType === "danger"
                          ? "bg-danger-soft text-destructive"
                          : item.statusType === "success"
                            ? "bg-success-soft text-emerald-800"
                            : "bg-warning-soft text-warning"
                      }`}
                    >
                      {item.status}
                    </span>

                    <Link
                      href={item.path}
                      className="h-7 px-2.5 rounded bg-surface border border-border-hairline hover:bg-surface-subtle text-foreground text-xs font-medium transition shadow-xs flex items-center gap-1"
                    >
                      <span>Inspect Audit</span>
                      <span className="material-symbols-outlined text-[13px]">arrow_forward</span>
                    </Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        {/* Right 4 Cols: Knowledge Graph & Activity */}
        <section className="lg:col-span-4 flex flex-col gap-4">
          {/* Active Entity Graph Mini-Card */}
          <div className="bg-surface rounded-xl border border-border-hairline p-4 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-foreground uppercase tracking-wider">
                Grounded Entity Graph
              </span>
              <Link href="/context-packs" className="text-xs text-primary font-medium hover:underline">
                Manage Hub
              </Link>
            </div>

            <div className="w-full h-28 bg-surface-subtle rounded-lg flex items-center justify-center relative overflow-hidden border border-border-hairline">
              <svg className="w-full h-full text-muted-foreground/30" fill="none" viewBox="0 0 240 100">
                <line x1="40" y1="50" x2="120" y2="30" stroke="currentColor" strokeDasharray="2 2" strokeWidth="1.5" />
                <line x1="120" y1="30" x2="200" y2="50" stroke="currentColor" strokeDasharray="2 2" strokeWidth="1.5" />
                <line x1="120" y1="30" x2="120" y2="80" stroke="#4338CA" strokeWidth="1.5" />
                <circle cx="40" cy="50" r="14" fill="#FFFFFF" stroke="#E7E5E4" />
                <circle cx="120" cy="30" r="16" fill="#EEF2FF" stroke="#4338CA" strokeWidth="1.5" />
                <circle cx="200" cy="50" r="14" fill="#FFFFFF" stroke="#E7E5E4" />
                <circle cx="120" cy="80" r="12" fill="#F0FDF4" stroke="#15803D" strokeWidth="1.5" />
                <text x="120" y="34" fill="#4338CA" fontFamily="Inter" fontSize="9" fontWeight="600" textAnchor="middle">
                  {activeProject?.brand || "Brand"}
                </text>
                <text x="40" y="53" fill="#78716C" fontFamily="Inter" fontSize="8" textAnchor="middle">
                  Service
                </text>
                <text x="200" y="53" fill="#78716C" fontFamily="Inter" fontSize="8" textAnchor="middle">
                  Place
                </text>
                <text x="120" y="83" fill="#15803D" fontFamily="Inter" fontSize="8" textAnchor="middle">
                  Facts
                </text>
              </svg>
            </div>

            <div className="text-[11px] text-muted-foreground flex items-center justify-between font-code-data">
              <span>{activeProject?.central_entity || "Active Business Entity"}</span>
              <span className="text-muted-foreground font-medium">JSON-LD generated on export</span>
            </div>
          </div>

          {/* Recent Backend Audits Mini-List */}
          <div className="bg-surface rounded-xl border border-border-hairline p-4 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-foreground uppercase tracking-wider">
                Recent Audits
              </span>
              <Link href="/audits" className="text-xs text-primary font-medium hover:underline">
                View all ({audits.length})
              </Link>
            </div>

            {audits.length === 0 ? (
              <p className="text-xs text-muted-foreground py-2">No audits recorded yet.</p>
            ) : (
              <div className="space-y-2 text-xs">
                {audits.slice(0, 3).map((a) => (
                  <Link
                    key={a.audit_id}
                    href={`/audits/${a.audit_id}`}
                    className="p-2.5 rounded-lg border border-border-hairline bg-surface hover:bg-surface-subtle transition flex items-center justify-between block"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-foreground truncate">
                        {a.central_entity ?? titleCase(a.page_type)}
                      </p>
                      <p className="text-[10px] text-muted-foreground font-code-data truncate">
                        {formatDateTime(a.created_at)}
                      </p>
                    </div>
                    <span className="font-code-data font-bold text-xs tabular-nums text-foreground ml-2">
                      {a.composite != null ? Math.round(a.composite) : "—"}
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
