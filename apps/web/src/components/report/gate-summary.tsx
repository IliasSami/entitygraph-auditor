"use client";

import { AlertTriangle, ArrowRight, Ban, Download, ShieldCheck } from "@/components/icons";
import {
  ConfidenceBadge,
  GateBadge,
  HeuristicDisclaimer,
  SeverityBadge,
} from "@/components/status";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatNumber } from "@/lib/format";
import type { AuditReport, ExportFormat, GateIssue } from "@/lib/types";
import { SCORE_LABELS } from "@/lib/types";

/** Gate issues are `string | GateIssue` depending on the run; render readable text. */
function gateIssueText(issue: string | GateIssue): string {
  if (typeof issue === "string") return issue;
  return issue.title?.trim() || issue.message?.trim() || issue.detail?.trim() || "Gate issue";
}

export function GateSummary({
  report,
  onExport,
  exporting,
  onOpenRecommendations,
}: {
  report: AuditReport;
  onExport: (fmt: ExportFormat) => void;
  exporting: boolean;
  onOpenRecommendations: () => void;
}) {
  const topIssues = report.recommendations.slice(0, 3);
  const critical = report.gate.critical_issues;
  const noncritical = report.gate.noncritical_issues;
  const failed = report.gate.status === "fail";
  const composite = report.composite_avr;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardDescription>Publication gate</CardDescription>
            <CardTitle className="mt-1 flex flex-wrap items-center gap-3 text-2xl">
              <GateBadge status={report.gate.status} />
              {composite != null ? (
                <span className="text-base font-normal text-muted-foreground">
                  Composite{" "}
                  <strong className="text-foreground tabular-nums">
                    {formatNumber(composite)}
                  </strong>{" "}
                  (AVR)
                </span>
              ) : null}
            </CardTitle>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onExport("markdown")}
              disabled={exporting}
            >
              <Download className="h-4 w-4" aria-hidden /> Markdown
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onExport("html")}
              disabled={exporting}
            >
              <Download className="h-4 w-4" aria-hidden /> HTML
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onExport("json")}
              disabled={exporting}
            >
              <Download className="h-4 w-4" aria-hidden /> JSON
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onExport("csv")}
              disabled={exporting}
            >
              <Download className="h-4 w-4" aria-hidden /> CSV
            </Button>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          {report.gate.status === "pass"
            ? "No blocking issues were found. The content met every gate rule for this profile."
            : report.gate.status === "pass_with_fixes"
              ? "Publishable, but fixes are recommended before the next release."
              : failed
                ? "Not publishable as-is: at least one blocking issue must be resolved first."
                : report.gate.status === "not_configured"
                  ? "No gate profile was configured for this audit, so no publish decision was made."
                  : "The gate was not evaluated for this audit."}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {critical.length > 0 ? (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-destructive">
              <Ban className="h-4 w-4" aria-hidden />
              Blocking issues ({critical.length})
            </h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
              {critical.map((issue, index) => (
                <li key={`${index}-${gateIssueText(issue)}`}>{gateIssueText(issue)}</li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="flex items-start gap-2 rounded-md border border-success/40 bg-success/5 p-3 text-sm">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />
            <p>No blocking issues were reported by the gate.</p>
          </div>
        )}

        {noncritical.length > 0 ? (
          <div className="rounded-md border border-warning/40 bg-warning/5 p-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <AlertTriangle className="h-4 w-4 text-warning" aria-hidden />
              Non-blocking issues ({noncritical.length})
            </h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {noncritical.map((issue, index) => (
                <li key={`${index}-${gateIssueText(issue)}`}>{gateIssueText(issue)}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {topIssues.length > 0 ? (
          <div>
            <h3 className="mb-2 text-sm font-semibold">Top issues to fix first</h3>
            <ul className="space-y-2">
              {topIssues.map((rec) => (
                <li key={rec.finding_id} className="flex items-start gap-2 text-sm">
                  <ArrowRight
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary"
                    aria-hidden
                  />
                  <span className="min-w-0">
                    <SeverityBadge severity={rec.severity} />{" "}
                    <span className="font-medium">{rec.title}</span>
                    <span className="block text-muted-foreground">
                      {rec.what.length > 160 ? `${rec.what.slice(0, 157)}…` : rec.what}
                    </span>
                    <ConfidenceBadge confidence={rec.confidence} />
                  </span>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={onOpenRecommendations}
              className="mt-2 inline-block text-sm font-medium text-primary hover:underline"
            >
              See all {report.recommendations.length} recommendations →
            </button>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No recommendations were generated for this audit.
          </p>
        )}

        <p className="text-xs text-muted-foreground">
          Scores are computed with profile{" "}
          <span className="font-mono">{report.audit_metadata.score_profile_version}</span>{" "}
          over {report.audit_metadata.page_type} pages.{" "}
          {SCORE_LABELS.AVR} (AVR) is the weighted composite of applicable components.
        </p>
        <HeuristicDisclaimer />
      </CardContent>
    </Card>
  );
}
