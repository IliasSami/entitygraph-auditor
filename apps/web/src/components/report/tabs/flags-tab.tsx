"use client";

import { AlertTriangle, Ban, CircleSlash2, MinusCircle } from "@/components/icons";
import { SeverityBadge } from "@/components/status";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { titleCase } from "@/lib/format";
import type { AuditReport } from "@/lib/types";

export function FlagsTab({ report }: { report: AuditReport }) {
  const flags = report.technical_flags ?? [];
  const detected = flags.filter((f) => f.detected);
  const notDetected = flags.filter((f) => !f.detected);

  return (
    <div className="space-y-6">
      <section aria-labelledby="flags-heading">
        <h2 id="flags-heading" className="mb-3 text-base font-semibold">
          Technical flags
        </h2>
        {flags.length === 0 ? (
          <Card>
            <CardContent className="pt-6 text-sm text-muted-foreground">
              No technical flags were recorded for this audit. Flags cover things like
              missing structured data, noindex directives, or unsupported content formats —
              this audit either found none or did not run those checks.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            <div>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                <AlertTriangle className="h-4 w-4 text-warning" aria-hidden />
                Detected ({detected.length})
              </h3>
              {detected.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No flags were detected in this content.
                </p>
              ) : (
                <ul className="space-y-2">
                  {detected.map((flag) => (
                    <li key={flag.flag_id} className="rounded-md border border-warning/40 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <SeverityBadge severity={flag.severity} />
                        <span className="text-sm font-medium">{flag.label}</span>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">{flag.detail}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {notDetected.length > 0 ? (
              <div>
                <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <CircleSlash2 className="h-4 w-4 text-success" aria-hidden />
                  Checked, not present ({notDetected.length})
                </h3>
                <ul className="flex flex-wrap gap-2">
                  {notDetected.map((flag) => (
                    <li
                      key={flag.flag_id}
                      className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground"
                    >
                      {flag.label}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        )}
      </section>

      <section aria-labelledby="limitations-heading" className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle
              id="limitations-heading"
              className="flex items-center gap-2 text-sm"
            >
              <MinusCircle className="h-4 w-4 text-info" aria-hidden /> Limitations of this
              audit
            </CardTitle>
          </CardHeader>
          <CardContent>
            {report.limitations && report.limitations.length ? (
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {report.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                No limitations were recorded.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Ban className="h-4 w-4 text-muted-foreground" aria-hidden /> Not assessed
            </CardTitle>
          </CardHeader>
          <CardContent>
            {report.not_assessed && report.not_assessed.length ? (
              <ul className="space-y-1">
                {report.not_assessed.map((item) => (
                  <li key={item} className="flex items-start gap-2 text-sm">
                    <Badge variant="secondary">Not assessed</Badge>
                    <span className="text-muted-foreground">{titleCase(item)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                Every applicable check was assessed in this audit.
              </p>
            )}
          </CardContent>
        </Card>
      </section>

      <p className="text-xs text-muted-foreground">
        “Not assessed” is shown instead of a score or a pass whenever the tool lacks the
        input it would need. Nothing in this report is silently substituted with an
        estimate.
      </p>
    </div>
  );
}
