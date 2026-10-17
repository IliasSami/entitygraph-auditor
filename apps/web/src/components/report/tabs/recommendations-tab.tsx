"use client";

import { useMemo, useState } from "react";
import { CheckSquare, Info, ListChecks, MapPin, Quote, Wrench } from "@/components/icons";
import { ConfidenceBadge, SeverityBadge } from "@/components/status";
import { EmptyState } from "@/components/states";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { titleCase } from "@/lib/format";
import type { AuditReport, Finding, Severity } from "@/lib/types";
import {
  RECOMMENDATION_STATUS_LABELS,
  SEVERITIES,
  SEVERITY_LABELS,
} from "@/lib/types";

/**
 * One recommendation rendered as what / where / why / how / verification —
 * the five fields required before a writer can act on it.
 */
export function RecommendationCard({ recommendation }: { recommendation: Finding }) {
  const { where, why, how } = recommendation;
  const hasWhere = Boolean(
    where && (where.section_id || where.passage_id || where.excerpt || where.start_offset != null),
  );
  const hasWhy = Boolean(
    why &&
      (why.rule_id ||
        why.entity ||
        why.attribute ||
        why.eav_status ||
        why.intent_or_query ||
        why.layer),
  );
  const hasHow = Boolean(
    how &&
      (how.suggested_rewrite ||
        how.verification_condition ||
        (how.implementation_steps?.length ?? 0) > 0),
  );
  return (
    <li className="rounded-md border p-4" data-testid="recommendation-card">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge severity={recommendation.severity} />
          <h3 className="text-sm font-semibold">{recommendation.title}</h3>
          <span className="rounded-full bg-secondary px-2 py-0.5 text-xs">
            {titleCase(recommendation.category)}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ConfidenceBadge confidence={recommendation.confidence} />
          <span className="text-xs text-muted-foreground" data-testid="rec-status">
            {RECOMMENDATION_STATUS_LABELS[recommendation.status]}
          </span>
        </div>
      </div>

      <p className="mt-2 text-sm">
        <span className="font-semibold uppercase tracking-wide text-muted-foreground">
          What:{" "}
        </span>
        {recommendation.what}
      </p>

      <dl className="mt-3 grid gap-3 text-sm md:grid-cols-2">
        <div className="rounded-md bg-muted/50 p-3">
          <dt className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <MapPin className="h-3.5 w-3.5" aria-hidden /> Where
          </dt>
          <dd className="mt-1" data-testid="rec-where">
            {hasWhere ? (
              <ul className="space-y-0.5 text-muted-foreground">
                {where?.section_id ? <li>Section: {where.section_id}</li> : null}
                {where?.passage_id ? <li>Passage: {where.passage_id}</li> : null}
                {where?.start_offset != null && where?.end_offset != null ? (
                  <li>
                    Characters {where.start_offset}–{where.end_offset}
                  </li>
                ) : null}
                {where?.excerpt ? (
                  <li>
                    <q>{where.excerpt}</q>
                  </li>
                ) : null}
              </ul>
            ) : (
              <span className="text-muted-foreground">
                Applies to the page as a whole.
              </span>
            )}
          </dd>
        </div>

        <div className="rounded-md bg-muted/50 p-3">
          <dt className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Info className="h-3.5 w-3.5" aria-hidden /> Why
          </dt>
          <dd className="mt-1" data-testid="rec-why">
            {hasWhy ? (
              <ul className="space-y-0.5 text-muted-foreground">
                {why?.rule_id ? <li>Rule: {why.rule_id}</li> : null}
                {why?.entity ? <li>Entity: {why.entity}</li> : null}
                {why?.attribute ? <li>Attribute: {why.attribute}</li> : null}
                {why?.eav_status ? <li>Attribute status: {why.eav_status}</li> : null}
                {why?.intent_or_query ? <li>Query/intent: {why.intent_or_query}</li> : null}
                {why?.layer ? <li>Layer: {why.layer}</li> : null}
              </ul>
            ) : (
              <span className="text-muted-foreground">
                See the finding description above.
              </span>
            )}
          </dd>
        </div>
      </dl>

      <div className="mt-3 rounded-md border p-3">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <Wrench className="h-3.5 w-3.5" aria-hidden /> How
        </p>
        <div className="mt-1 space-y-2 text-sm" data-testid="rec-how">
          {how?.suggested_rewrite ? (
            <p className="rounded bg-success/10 p-2">
              <span className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Suggested rewrite
              </span>
              {how.suggested_rewrite}
            </p>
          ) : null}
          {how?.implementation_steps?.length ? (
            <ol className="list-decimal space-y-1 pl-5 text-muted-foreground">
              {how.implementation_steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          ) : null}
          {!hasHow ? (
            <p className="text-muted-foreground">
              No implementation detail was recorded for this finding.
            </p>
          ) : null}
        </div>
      </div>

      {how?.verification_condition ? (
        <div
          className="mt-3 rounded-md border border-info/40 bg-info/5 p-3 text-sm"
          data-testid="rec-verification"
        >
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-info">
            <CheckSquare className="h-3.5 w-3.5" aria-hidden /> Verification
          </p>
          <p className="mt-1">{how.verification_condition}</p>
        </div>
      ) : (
        <p className="mt-3 text-xs text-muted-foreground" data-testid="rec-verification-none">
          No verification condition was recorded — treat the fix as unverified until you
          re-audit.
        </p>
      )}

      {recommendation.evidence.length ? (
        <div className="mt-3">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Quote className="h-3.5 w-3.5" aria-hidden /> Evidence
          </p>
          <ul className="mt-1 space-y-1">
            {recommendation.evidence.map((quote) => (
              <li key={quote}>
                <q className="text-sm text-muted-foreground">{quote}</q>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <dl className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
        <div>
          <dt className="inline">Impact: </dt>
          <dd className="inline font-medium text-foreground tabular-nums">
            {recommendation.impact}
          </dd>
        </div>
        <div>
          <dt className="inline">Effort: </dt>
          <dd className="inline font-medium text-foreground tabular-nums">
            {recommendation.effort}
          </dd>
        </div>
        <div>
          <dt className="inline">Priority: </dt>
          <dd className="inline font-medium text-foreground tabular-nums">
            {recommendation.priority_score.toFixed(1)}
          </dd>
        </div>
        <div>
          <dt className="inline">Confidence: </dt>
          <dd className="inline font-medium text-foreground tabular-nums">
            {recommendation.confidence_numeric.toFixed(2)}
          </dd>
        </div>
      </dl>
    </li>
  );
}

export function RecommendationsTab({ report }: { report: AuditReport }) {
  const [severity, setSeverity] = useState<string>("all");
  const [status, setStatus] = useState<string>("all");

  const filtered = useMemo(() => {
    return report.recommendations
      .filter((rec) => (severity === "all" ? true : rec.severity === severity))
      .filter((rec) => (status === "all" ? true : rec.status === status))
      .sort((a, b) => b.priority_score - a.priority_score);
  }, [report.recommendations, severity, status]);

  if (report.recommendations.length === 0) {
    return (
      <EmptyState
        title="No recommendations"
        description="Nothing needed fixing in this audit. Re-run the audit after your next content change to confirm the result still holds."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label
            htmlFor="rec-severity"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Severity
          </label>
          <Select
            id="rec-severity"
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="w-40"
          >
            <option value="all">All severities</option>
            {SEVERITIES.map((sev: Severity) => (
              <option key={sev} value={sev}>
                {SEVERITY_LABELS[sev]}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <label
            htmlFor="rec-status"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Status
          </label>
          <Select
            id="rec-status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-40"
          >
            <option value="all">All statuses</option>
            {Object.entries(RECOMMENDATION_STATUS_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        <p className="pb-2 text-sm text-muted-foreground">
          {filtered.length} of {report.recommendations.length} recommendations, sorted by
          priority score
        </p>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title="No recommendations match"
          description="Change the severity or status filter to see other recommendations."
        />
      ) : (
        <ul className="space-y-3">
          {filtered.map((rec) => (
            <RecommendationCard key={rec.finding_id} recommendation={rec} />
          ))}
        </ul>
      )}

      {report.measurement_plan.length > 0 ? (
        <section aria-labelledby="measurement-heading" className="pt-2">
          <h3
            id="measurement-heading"
            className="mb-2 flex items-center gap-2 text-base font-semibold"
          >
            <ListChecks className="h-4 w-4 text-primary" aria-hidden /> Measurement plan
          </h3>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-normal text-muted-foreground">
                How to tell whether these fixes worked — check after the next audit run.
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {report.measurement_plan.map((item, index) => (
                  <li key={index} className="rounded-md border p-3 text-sm">
                    <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
                      {Object.entries(item).map(([key, value]) => (
                        <div key={key} className="flex gap-2">
                          <dt className="shrink-0 text-muted-foreground">
                            {titleCase(key)}:
                          </dt>
                          <dd className="min-w-0 break-words">
                            {Array.isArray(value)
                              ? value.join(", ")
                              : typeof value === "object" && value !== null
                                ? JSON.stringify(value)
                                : String(value)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </section>
      ) : null}
    </div>
  );
}
