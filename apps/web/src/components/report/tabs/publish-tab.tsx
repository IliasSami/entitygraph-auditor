"use client";

import * as React from "react";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { AuditReport, GateIssue } from "@/lib/types";

/**
 * Publish / export tab.
 *
 * Everything rendered here is derived from the audit `report` — the central
 * entity, its facts, the gate issues, the best passage and the entity graph.
 * Nothing is hard-coded: when the report does not contain a value (a site URL,
 * a price, an FAQ pair, a publish destination) this tab says so instead of
 * inventing one. The only live action is the real Markdown export and copying
 * the derived JSON-LD.
 */

function issueText(issue: string | GateIssue): string {
  if (typeof issue === "string") return issue;
  return issue.message || issue.title || issue.detail || issue.rule_id || "Gate issue";
}

function firstMatching(rows: AuditReport["eav_rows"], pattern: RegExp): string | null {
  const row = rows?.find((r) => pattern.test(r.attribute) && r.value);
  return row?.value ?? null;
}

export function PublishTab({ report }: { report: AuditReport }) {
  const [activePreview, setActivePreview] = useState<"ai" | "serp" | "social">("ai");
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [notice, setNotice] = useState("");

  const [schemaTypes, setSchemaTypes] = useState({
    article: true,
    service: true,
    organization: true,
    faq: true,
  });

  const meta = report.audit_metadata;
  const centralEntity = meta.central_entity?.trim() || "Unnamed entity";
  const primaryQuery = meta.primary_query?.trim() || null;
  const pageTitle = primaryQuery ? `${centralEntity}: ${primaryQuery}` : centralEntity;
  const auditId = meta.run_id;

  // -------- real gate data (no fabrication) ---------------------------------
  const criticalIssues = report.gate?.critical_issues ?? [];
  const noncriticalIssues = report.gate?.noncritical_issues ?? [];
  const gateStatus = report.gate?.status ?? "unknown";

  // -------- real entity facts ----------------------------------------------
  const location = firstMatching(report.eav_rows, /service_area|location|area_served|address|city|region/i);
  const price = firstMatching(report.eav_rows, /price|pricing|cost|fee|rate|starting/i);
  const phone = firstMatching(report.eav_rows, /phone|contact/i);
  const service = firstMatching(report.eav_rows, /primary_service|service|category/i);

  // -------- best passage for the AI-answer preview --------------------------
  const topPassage = React.useMemo(() => {
    const list = report.passages ?? [];
    if (!list.length) return null;
    return [...list].sort(
      (a, b) => Number(b.answer_first) - Number(a.answer_first) || b.word_count - a.word_count,
    )[0];
  }, [report.passages]);

  const questionPassage = React.useMemo(
    () => (report.passages ?? []).find((p) => p.text.trim().endsWith("?")) ?? null,
    [report.passages],
  );

  // -------- JSON-LD derived from the report ---------------------------------
  const jsonLdGraph = [
    schemaTypes.organization && {
      "@type": "Organization",
      "@id": "#organization",
      name: centralEntity,
      ...(phone ? { telephone: phone } : {}),
    },
    schemaTypes.service && {
      "@type": "Service",
      "@id": "#service",
      name: service || pageTitle,
      provider: { "@id": "#organization" },
      ...(location ? { areaServed: { "@type": "Place", name: location } } : {}),
      ...(price ? { offers: { "@type": "Offer", description: price } } : {}),
    },
    schemaTypes.article &&
      topPassage && {
        "@type": "Article",
        "@id": "#article",
        headline: pageTitle,
        description: topPassage.text.slice(0, 200),
        about: { "@id": "#organization" },
      },
    schemaTypes.faq &&
      questionPassage && {
        "@type": "FAQPage",
        "@id": "#faq",
        mainEntity: [
          {
            "@type": "Question",
            name: questionPassage.text.trim(),
            acceptedAnswer: {
              "@type": "Answer",
              text: (report.passages ?? []).find(
                (p) => p.section_id === questionPassage.section_id && p.passage_id !== questionPassage.passage_id,
              )?.text.slice(0, 300) || "No grounded answer passage found in this audit.",
            },
          },
        ],
      },
  ].filter(Boolean);

  const jsonLdContent = JSON.stringify({ "@context": "https://schema.org", "@graph": jsonLdGraph }, null, 2);

  const handleCopyJsonLd = () => {
    void navigator.clipboard.writeText(jsonLdContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExport = async (format: "markdown" | "json") => {
    setExporting(true);
    try {
      const { blob, filename } = await api.exportAudit(auditId, format);
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(href);
      setNotice(`Exported ${format} via the audit export endpoint.`);
    } catch {
      setNotice("Export failed — the audit export endpoint was not reachable.");
    } finally {
      setExporting(false);
      setTimeout(() => setNotice(""), 4000);
    }
  };

  // `not_configured` is not a failure: without a brand pack there is no brand rule
  // to evaluate, so it must not be rendered as an unresolved-issue state.
  const gateTone =
    gateStatus === "pass"
      ? "bg-emerald-500"
      : gateStatus === "pass_with_fixes"
        ? "bg-amber-500"
        : gateStatus === "fail"
          ? "bg-rose-500"
          : "bg-slate-400";

  return (
    <div className="space-y-6 pt-2">
      {/* ------------------------------------------------------------- VALIDATION GATE BANNER */}
      <div className="w-full bg-surface rounded-xl border border-border-hairline shadow-xs p-4 relative overflow-hidden">
        <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${gateTone}`} />
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pl-2">
          <div className="flex items-start gap-3">
            <div
              className={`w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 mt-0.5 ${
                gateStatus === "fail"
                  ? "bg-rose-50 text-rose-700 border-rose-200"
                  : gateStatus === "not_configured"
                    ? "bg-surface-subtle text-muted-foreground border-border-hairline"
                    : "bg-amber-50 text-amber-700 border-amber-200"
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">verified_user</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-foreground">
                  Publication gate: {criticalIssues.length} critical · {noncriticalIssues.length} non-critical
                </span>
                <span className="px-2 py-0.5 rounded-full bg-surface-subtle text-muted-foreground font-code-data text-[10px] font-semibold border border-border-hairline">
                  Score profile v{meta.score_profile_version}
                </span>
                {meta.deterministic_only && (
                  <span className="px-2 py-0.5 rounded-full bg-surface-subtle text-muted-foreground font-code-data text-[10px] font-semibold border border-border-hairline">
                    Deterministic-only
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                {gateStatus === "pass"
                  ? "Every publication gate passed for this run."
                  : gateStatus === "pass_with_fixes"
                    ? "This run passes with recommended fixes — review the issues below."
                    : gateStatus === "fail"
                      ? "This run has unresolved gate issues. Resolve them before publishing."
                      : "No brand pack configured — the gate was not evaluated. Fabrication checks still apply."}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end lg:self-center shrink-0">
            <Link
              href="/optimizer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-subtle hover:bg-surface border border-border-hairline text-foreground text-xs font-medium transition-colors"
            >
              <span className="material-symbols-outlined text-[15px] text-muted-foreground">tune</span>
              <span>Open in Optimizer</span>
            </Link>
            <button
              type="button"
              onClick={handleCopyJsonLd}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-primary hover:bg-primary-hover text-white text-xs font-medium transition-colors shadow-xs"
            >
              <span className="material-symbols-outlined text-[15px]">
                {copied ? "check" : "content_copy"}
              </span>
              <span>{copied ? "Copied" : "Copy JSON-LD"}</span>
            </button>
          </div>
        </div>

        {/* Checklist Items Grid — real gate issues */}
        <div className="mt-3.5 pt-3 pl-2 grid grid-cols-1 md:grid-cols-2 gap-3 bg-surface-subtle/50 rounded-lg p-3 text-xs border border-border-hairline">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-1 text-rose-700 font-semibold uppercase tracking-wider text-[10px]">
              <span className="material-symbols-outlined text-[13px]">error</span>
              <span>Critical ({criticalIssues.length})</span>
            </div>
            {criticalIssues.length ? (
              criticalIssues.slice(0, 4).map((issue, i) => (
                <div key={i} className="flex items-start justify-between gap-2 bg-surface p-2 rounded-lg border border-border-hairline">
                  <span className="font-medium text-foreground">{issueText(issue)}</span>
                  <span className="px-1.5 py-0.2 rounded-full bg-rose-50 text-rose-700 font-code-data text-[10px] font-semibold shrink-0">
                    Blocker
                  </span>
                </div>
              ))
            ) : (
              <p className="text-muted-foreground">No critical issues recorded.</p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-1 text-amber-700 font-semibold uppercase tracking-wider text-[10px]">
              <span className="material-symbols-outlined text-[13px]">warning</span>
              <span>Non-critical ({noncriticalIssues.length})</span>
            </div>
            {noncriticalIssues.length ? (
              noncriticalIssues.slice(0, 4).map((issue, i) => (
                <div key={i} className="flex items-start justify-between gap-2 bg-surface p-2 rounded-lg border border-border-hairline">
                  <span className="text-foreground">{issueText(issue)}</span>
                </div>
              ))
            ) : (
              <p className="text-muted-foreground">No non-critical issues recorded.</p>
            )}
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------- THREE-COLUMN ARCHITECTURE */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN: Previews */}
        <section className="xl:col-span-4 flex flex-col gap-4">
          <div className="bg-surface rounded-xl border border-border-hairline shadow-xs p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold text-foreground uppercase tracking-wider">
                Surfacing Previews
              </h2>
              <span className="text-muted-foreground material-symbols-outlined text-[16px]">devices</span>
            </div>

            <div className="flex items-center p-1 bg-surface-subtle rounded-lg text-xs font-medium">
              {(["ai", "serp", "social"] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActivePreview(tab)}
                  className={`flex-1 py-1 rounded text-center transition-all ${
                    activePreview === tab
                      ? "bg-surface shadow-xs text-primary font-bold"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {tab === "ai" ? "AI Answer" : tab === "serp" ? "Search SERP" : "Social Card"}
                </button>
              ))}
            </div>

            {/* AI Answer Preview */}
            {activePreview === "ai" && (
              <div className="flex flex-col gap-3">
                {topPassage ? (
                  <>
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-foreground">Strongest extractable passage</span>
                      {topPassage.answer_first && (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 font-code-data text-[10px] font-bold flex items-center gap-1 border border-emerald-200">
                          <span className="material-symbols-outlined text-[12px]">check</span> answer-first
                        </span>
                      )}
                    </div>
                    <div className="p-3.5 rounded-xl bg-indigo-50/50 border border-indigo-100 flex flex-col gap-2">
                      <div className="flex items-center gap-1.5 text-indigo-700 text-xs font-semibold">
                        <span className="material-symbols-outlined text-[14px]">auto_awesome</span>
                        <span>Passage from audited content</span>
                      </div>
                      <blockquote className="font-serif text-xs leading-relaxed text-foreground bg-surface p-2.5 rounded-lg border border-border-hairline shadow-xs">
                        {topPassage.text}
                      </blockquote>
                      <span className="font-code-data text-[10px] text-muted-foreground">
                        {topPassage.word_count} words · passage {topPassage.passage_id}
                      </span>
                    </div>

                    <div className="flex flex-col gap-1.5 bg-surface-subtle p-3 rounded-lg text-xs">
                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                        Passage extraction factors
                      </span>
                      {[
                        { label: "Answer-first sentence pattern", ok: topPassage.answer_first },
                        { label: "Explicit named subject", ok: topPassage.named_subject },
                        { label: `Within length budget (${topPassage.word_count} words)`, ok: topPassage.word_count <= 320 },
                      ].map(({ label, ok }, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-foreground">
                          <span
                            className={`material-symbols-outlined text-[14px] ${ok ? "text-emerald-700" : "text-amber-600"}`}
                          >
                            {ok ? "check_circle" : "warning"}
                          </span>
                          <span>{label}</span>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-muted-foreground py-4">
                    No passage was extracted from this run&apos;s content.
                  </p>
                )}
              </div>
            )}

            {/* SERP Snippet Preview */}
            {activePreview === "serp" && (
              <div className="p-3 rounded-xl bg-surface-subtle border border-border-hairline flex flex-col gap-1 text-xs">
                <span className="font-code-data text-[10px] text-muted-foreground">
                  Site URL not recorded in this audit
                </span>
                <span className="font-semibold text-sm text-indigo-700">{pageTitle}</span>
                <p className="text-muted-foreground leading-relaxed line-clamp-2">
                  {topPassage?.text.slice(0, 160) || "No audited passage available for a snippet."}
                </p>
                <div className="flex items-center gap-2 mt-1 font-code-data text-[10px] text-muted-foreground">
                  <span>{report.scores ? Object.keys(report.scores).length : 0} scored dimensions</span>
                  <span>·</span>
                  <span>Composite {report.composite_avr != null ? report.composite_avr.toFixed(1) : "—"} / 10</span>
                </div>
              </div>
            )}

            {/* Social Card Preview */}
            {activePreview === "social" && (
              <div className="rounded-xl overflow-hidden border border-border-hairline bg-surface shadow-xs text-xs">
                <div className="bg-gradient-to-br from-indigo-900 to-primary p-4 text-white h-28 flex flex-col justify-end">
                  <span className="font-code-data text-[9px] bg-white/20 px-1.5 py-0.5 rounded w-fit uppercase font-semibold">
                    {meta.page_type}
                  </span>
                  <span className="font-bold text-xs mt-1 truncate">{pageTitle}</span>
                </div>
                <div className="p-2.5 bg-surface-subtle">
                  <span className="font-code-data text-[9px] text-muted-foreground uppercase block">
                    {centralEntity}
                  </span>
                  <span className="font-semibold text-xs text-foreground line-clamp-2">
                    {topPassage?.text.slice(0, 90) || "No audited passage available."}
                  </span>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* CENTER COLUMN: JSON-LD */}
        <section className="xl:col-span-5 flex flex-col gap-4">
          <div className="bg-surface rounded-xl border border-border-hairline shadow-xs p-4 flex flex-col gap-3">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-[18px]">account_tree</span>
                  <h2 className="text-xs font-bold text-foreground uppercase tracking-wider">
                    Schema Generator
                  </h2>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Derived from this audit&apos;s entities and facts · preview only, not injected anywhere
                </p>
              </div>
              <a
                href="https://search.google.com/test/rich-results"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline text-xs font-medium inline-flex items-center gap-0.5"
              >
                <span>Google Rich Test</span>
                <span className="material-symbols-outlined text-[13px]">open_in_new</span>
              </a>
            </div>

            <div className="flex flex-wrap gap-1.5 p-2 bg-surface-subtle rounded-lg text-xs">
              {[
                { key: "article", label: "Article" },
                { key: "service", label: "Service" },
                { key: "organization", label: "Organization" },
                { key: "faq", label: "FAQPage" },
              ].map(({ key, label }) => (
                <label
                  key={key}
                  className="flex items-center gap-1.5 px-2 py-1 rounded bg-surface border border-border-hairline text-xs font-medium cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={schemaTypes[key as keyof typeof schemaTypes]}
                    onChange={(e) => setSchemaTypes({ ...schemaTypes, [key]: e.target.checked })}
                    className="rounded border-border-hairline text-primary focus:ring-0 w-3 h-3"
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>

            <div className="rounded-xl overflow-hidden bg-stone-950 text-stone-100 shadow-xs flex flex-col border border-stone-800">
              <div className="px-3 py-2 bg-stone-900 border-b border-stone-800 flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="font-code-data text-[10px] text-emerald-400 font-semibold">
                    Derived JSON-LD · {jsonLdGraph.length} node{jsonLdGraph.length === 1 ? "" : "s"}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleCopyJsonLd}
                  className="flex items-center gap-1 px-2 py-0.5 rounded bg-stone-800 hover:bg-stone-700 font-code-data text-[10px] text-stone-200 transition-colors"
                >
                  <span className="material-symbols-outlined text-[12px]">
                    {copied ? "check" : "content_copy"}
                  </span>
                  <span>{copied ? "Copied!" : "Copy JSON-LD"}</span>
                </button>
              </div>
              <pre className="p-3 text-[11px] font-code-data overflow-x-auto max-h-[360px] text-emerald-200/90 leading-relaxed">
                {jsonLdContent}
              </pre>
            </div>
          </div>
        </section>

        {/* RIGHT COLUMN: Export destinations */}
        <section className="xl:col-span-3 flex flex-col gap-4">
          <div className="bg-surface rounded-xl border border-border-hairline shadow-xs p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold text-foreground uppercase tracking-wider">
                Export
              </h2>
              <span className="px-1.5 py-0.2 rounded-full bg-surface-subtle text-muted-foreground font-code-data text-[10px] font-bold border border-border-hairline">
                Local
              </span>
            </div>

            <div className="flex flex-col gap-2.5 text-xs">
              <div className="p-3 rounded-lg bg-surface-subtle border border-border-hairline flex flex-col gap-2">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary text-[18px]">description</span>
                    <div className="flex flex-col">
                      <span className="font-semibold text-foreground">Markdown report</span>
                      <span className="text-[10px] text-muted-foreground">Self-contained · 10 sections</span>
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleExport("markdown")}
                  disabled={exporting}
                  className="w-full py-1.5 rounded-lg bg-primary hover:bg-primary-hover text-white font-medium text-xs shadow-xs transition-colors flex items-center justify-center gap-1.5 disabled:opacity-60"
                >
                  <span className="material-symbols-outlined text-[14px]">download</span>
                  <span>{exporting ? "Exporting..." : "Download Markdown"}</span>
                </button>
              </div>

              <div className="p-3 rounded-lg bg-surface-subtle border border-border-hairline flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-muted-foreground text-[18px]">data_object</span>
                  <div className="flex flex-col">
                    <span className="font-semibold text-foreground">JSON export</span>
                    <span className="text-[10px] text-muted-foreground">Full audit report</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleExport("json")}
                  disabled={exporting}
                  className="p-1 rounded hover:bg-surface text-muted-foreground hover:text-foreground disabled:opacity-60"
                >
                  <span className="material-symbols-outlined text-[16px]">file_download</span>
                </button>
              </div>

              <div className="p-3 rounded-lg bg-surface-subtle border border-border-hairline flex items-start gap-2 text-[11px] text-muted-foreground">
                <span className="material-symbols-outlined text-[16px]">info</span>
                <span>
                  No CMS or webhook destination is configured for this workspace, so nothing is pushed
                  automatically. Use Copy JSON-LD or download an export.
                </span>
              </div>
            </div>
          </div>
        </section>
      </div>

      {notice && (
        <div
          role="status"
          className="fixed bottom-4 right-4 z-50 px-3 py-2 rounded-lg bg-surface border border-border-hairline shadow-lg text-xs text-foreground"
        >
          {notice}
        </div>
      )}
    </div>
  );
}
