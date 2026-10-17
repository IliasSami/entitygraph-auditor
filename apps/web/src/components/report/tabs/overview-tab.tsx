"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, Info, Link2, Target } from "@/components/icons";
import Link from "next/link";
import { ScoreCard, ScoreDrawer } from "@/components/report/score-card";
import { HeuristicDisclaimer, SeverityBadge } from "@/components/status";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { AuditReport, ComponentScore } from "@/lib/types";
import {
  INTENT_LABELS,
  PAGE_TYPE_LABELS,
  SCORE_KEYS,
  SCORE_LABELS,
  type ScoreKey,
} from "@/lib/types";

function orderedScores(report: AuditReport): ComponentScore[] {
  const present = new Set(Object.keys(report.scores));
  const ordered: ComponentScore[] = [];
  const push = (key: string, score: ComponentScore) => {
    // AVR is the weighted composite of the other components, surfaced in the
    // gate summary; the flat PRD §22 map carries it without component fields.
    if (key === "AVR") return;
    ordered.push(score.score_key ? score : { ...score, score_key: key as ScoreKey });
  };
  for (const key of SCORE_KEYS) {
    if (present.has(key)) {
      push(key, report.scores[key]);
      present.delete(key);
    }
  }
  for (const [key, score] of Object.entries(report.scores)) {
    if (present.has(key)) push(key, score);
  }
  return ordered;
}

function CountCard({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div className="rounded-md border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function OverviewTab({ report }: { report: AuditReport }) {
  const [selected, setSelected] = useState<ComponentScore | null>(null);
  const scores = useMemo(() => orderedScores(report), [report]);
  const meta = report.audit_metadata;

  const coverage = useMemo(() => {
    const counts = { covered: 0, partial: 0, missing: 0, excluded: 0 };
    for (const row of report.coverage_rows) counts[row.status] += 1;
    return counts;
  }, [report.coverage_rows]);

  const claims = useMemo(() => {
    const counts = { verified: 0, unverified: 0, conflicting: 0, not_assessed: 0 };
    for (const claim of report.claims) counts[claim.verification_state] += 1;
    return counts;
  }, [report.claims]);

  return (
    <div className="space-y-6">
      <section aria-labelledby="scores-heading">
        <h2 id="scores-heading" className="mb-3 text-base font-semibold">
          Component scores
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {scores.map((score) => (
            <ScoreCard key={score.score_key} score={score} onSelect={setSelected} />
          ))}
        </div>
        <div className="mt-3 space-y-1 text-xs text-muted-foreground">
          <p>Select a score to open its rubric, lost points, and confidence.</p>
          <HeuristicDisclaimer className="mt-0" />
        </div>
        <ScoreDrawer score={selected} onOpenChange={setSelected} />
      </section>

      <section aria-labelledby="summary-heading" className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle id="summary-heading" className="flex items-center gap-2 text-base">
              <Target className="h-4 w-4 text-primary" aria-hidden /> What this audit saw
            </CardTitle>
            <CardDescription>
              Central entity: {meta.central_entity || "not identified"} · primary intent:{" "}
              {INTENT_LABELS[meta.primary_intent] ?? meta.primary_intent}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <CountCard label="Entities" value={report.entities.length} />
            <CountCard label="Attribute rows" value={report.eav_rows.length} />
            <CountCard label="Relationships" value={report.triples.length} />
            <CountCard label="Fan-out queries" value={report.fanout.length} />
            <CountCard
              label="Coverage gaps"
              value={coverage.missing + coverage.partial}
              hint={`${coverage.covered} covered`}
            />
            <CountCard
              label="Passage findings"
              value={report.passage_findings.length}
            />
            <CountCard label="Claims" value={report.claims.length} />
            <CountCard label="Recommendations" value={report.recommendations.length} />
            <CountCard label="Evidence sources" value={report.sources.length} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Link2 className="h-4 w-4 text-primary" aria-hidden /> Verification &amp;
              coverage at a glance
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Fan-out coverage
              </p>
              <div className="grid grid-cols-4 gap-2 text-center text-sm">
                <div className="rounded-md border p-2">
                  <p className="font-semibold tabular-nums text-success">
                    {coverage.covered}
                  </p>
                  <p className="text-xs text-muted-foreground">Covered</p>
                </div>
                <div className="rounded-md border p-2">
                  <p className="font-semibold tabular-nums text-warning">
                    {coverage.partial}
                  </p>
                  <p className="text-xs text-muted-foreground">Partial</p>
                </div>
                <div className="rounded-md border p-2">
                  <p className="font-semibold tabular-nums text-destructive">
                    {coverage.missing}
                  </p>
                  <p className="text-xs text-muted-foreground">Missing</p>
                </div>
                <div className="rounded-md border p-2">
                  <p className="font-semibold tabular-nums text-muted-foreground">
                    {coverage.excluded}
                  </p>
                  <p className="text-xs text-muted-foreground">Excluded</p>
                </div>
              </div>
            </div>
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Claims verification
              </p>
              <div className="grid grid-cols-4 gap-2 text-center text-sm">
                <div className="rounded-md border p-2">
                  <p className="font-semibold tabular-nums text-success">
                    {claims.verified}
                  </p>
                  <p className="text-xs text-muted-foreground">Verified</p>
                </div>
                <div className="rounded-md border p-2">
                  <p className="font-semibold tabular-nums text-destructive">
                    {claims.unverified}
                  </p>
                  <p className="text-xs text-muted-foreground">Unverified</p>
                </div>
                <div className="rounded-md border p-2">
                  <p className="font-semibold tabular-nums text-destructive">
                    {claims.conflicting}
                  </p>
                  <p className="text-xs text-muted-foreground">Conflicting</p>
                </div>
                <div className="rounded-md border p-2">
                  <p className="font-semibold tabular-nums text-muted-foreground">
                    {claims.not_assessed}
                  </p>
                  <p className="text-xs text-muted-foreground">Not assessed</p>
                </div>
              </div>
            </div>
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Recommendations by severity
              </p>
              <div className="flex flex-wrap gap-2">
                {(["critical", "high", "medium", "low", "info"] as const).map((sev) => (
                  <span key={sev} className="flex items-center gap-1.5 text-sm">
                    <SeverityBadge severity={sev} />
                    <span className="tabular-nums">
                      {report.recommendations.filter((r) => r.severity === sev).length}
                    </span>
                  </span>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {(meta.assumptions.length > 0 || meta.warnings.length > 0) && (
        <section aria-labelledby="assumptions-heading" className="grid gap-4 lg:grid-cols-2">
          {meta.assumptions.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle
                  id="assumptions-heading"
                  className="flex items-center gap-2 text-base"
                >
                  <Info className="h-4 w-4 text-info" aria-hidden /> Assumptions
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                  {meta.assumptions.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
          {meta.warnings.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <AlertTriangle className="h-4 w-4 text-warning" aria-hidden /> Warnings
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                  {meta.warnings.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
        </section>
      )}

      <section aria-labelledby="swot-heading">
        <h2 id="swot-heading" className="mb-3 text-base font-semibold">
          SWOT
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {(
            [
              ["Strengths", report.swot.strengths, "text-success"],
              ["Weaknesses", report.swot.weaknesses, "text-destructive"],
              ["Opportunities", report.swot.opportunities, "text-info"],
              ["Threats", report.swot.threats, "text-warning"],
            ] as const
          ).map(([label, items, tone]) => (
            <Card key={label}>
              <CardHeader className="pb-2">
                <CardTitle className={`text-sm ${tone}`}>{label}</CardTitle>
              </CardHeader>
              <CardContent>
                {items.length ? (
                  <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
                    {items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">None identified.</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section aria-labelledby="meta-heading">
        <h2 id="meta-heading" className="mb-3 text-base font-semibold">
          Audit metadata
        </h2>
        <Card>
          <CardContent className="pt-6">
            <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <dt className="text-muted-foreground">Run ID</dt>
                <dd className="break-all font-mono text-xs">{meta.run_id}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Project</dt>
                <dd>
                  <Link
                    href={`/projects/${meta.project_id}`}
                    className="font-mono text-xs text-primary hover:underline"
                  >
                    {meta.project_id}
                  </Link>
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Page type</dt>
                <dd>{PAGE_TYPE_LABELS[meta.page_type] ?? meta.page_type}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Language</dt>
                <dd>{meta.language}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Created</dt>
                <dd>{formatDateTime(meta.created_at)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Provider model</dt>
                <dd>{meta.provider_model || "None (deterministic only)"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Score profile</dt>
                <dd className="font-mono text-xs">{meta.score_profile_version}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Content hash</dt>
                <dd className="break-all font-mono text-xs">{meta.content_hash}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Context packs</dt>
                <dd className="flex flex-wrap gap-1">
                  {meta.context_pack_versions.length ? (
                    meta.context_pack_versions.map((pack) => (
                      <Link
                        key={pack}
                        href="/context-packs"
                        className="rounded bg-secondary px-1.5 py-0.5 font-mono text-xs hover:underline"
                      >
                        {pack}
                      </Link>
                    ))
                  ) : (
                    <span className="text-muted-foreground">None</span>
                  )}
                </dd>
              </div>
            </dl>
          </CardContent>
        </Card>
      </section>

      <p className="text-xs text-muted-foreground">
        Composite scores use{" "}
        {SCORE_LABELS.AVR} as the weighted roll-up of applicable components.
        {formatNumber(report.composite_avr) !== "—"
          ? ` This audit scored ${formatNumber(report.composite_avr)}.`
          : ""}
      </p>
    </div>
  );
}
