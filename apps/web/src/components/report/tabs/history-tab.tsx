"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { GitCompareArrows, History } from "@/components/icons";
import { GateBadge, StageStatusBadge } from "@/components/status";
import { EmptyState, QueryView } from "@/components/states";
import { buttonClasses } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDateTime, formatDuration, formatNumber, titleCase } from "@/lib/format";
import type { StageRecord } from "@/lib/types";

export function HistoryTab({
  projectId,
  currentAuditId,
  stages,
}: {
  projectId: string;
  currentAuditId: string;
  stages: StageRecord[];
}) {
  const audits = useQuery({
    queryKey: ["audits", { project_id: projectId }],
    queryFn: () => api.listAudits({ project_id: projectId }),
  });

  const previous = audits.data?.filter((a) => a.audit_id !== currentAuditId) ?? [];

  return (
    <div className="space-y-6">
      <section aria-labelledby="stage-history-heading">
        <h2
          id="stage-history-heading"
          className="mb-3 flex items-center gap-2 text-base font-semibold"
        >
          <History className="h-4 w-4 text-primary" aria-hidden /> This run, stage by stage
        </h2>
        {stages.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No stage records are available for this run.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <caption className="sr-only">Stage timings for this audit run</caption>
              <TableHeader>
                <TableRow>
                  <TableHead scope="col">Stage</TableHead>
                  <TableHead scope="col">Status</TableHead>
                  <TableHead scope="col">Duration</TableHead>
                  <TableHead scope="col">Attempts</TableHead>
                  <TableHead scope="col">Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stages.map((stage) => (
                  <TableRow key={stage.node}>
                    <TableCell className="font-medium">{stage.label}</TableCell>
                    <TableCell>
                      <StageStatusBadge status={stage.status} />
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {formatDuration(stage.duration_ms)}
                    </TableCell>
                    <TableCell className="tabular-nums">{stage.attempts}</TableCell>
                    <TableCell className="max-w-[24rem] text-xs text-muted-foreground">
                      {stage.error ?? stage.detail ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <section aria-labelledby="other-runs-heading">
        <h2 id="other-runs-heading" className="mb-3 text-base font-semibold">
          Other audits in this project
        </h2>
        <QueryView
          query={audits}
          loadingLabel="Loading audit history…"
          errorTitle="Could not load audit history"
          isEmpty={(rows) => rows.filter((a) => a.audit_id !== currentAuditId).length === 0}
          empty={
            <EmptyState
              title="This is the only audit for this project"
              description="Run another audit after your next content change to compare scores and track progress."
              action={
                <Link
                  href={`/audits/new?project_id=${projectId}`}
                  className={buttonClasses({ size: "sm" })}
                >
                  Run another audit
                </Link>
              }
            />
          }
        >
          {() => (
            <div className="overflow-x-auto rounded-md border">
              <Table>
                <caption className="sr-only">
                  Other audits for this project with gate results and composite scores
                </caption>
                <TableHeader>
                  <TableRow>
                    <TableHead scope="col">Created</TableHead>
                    <TableHead scope="col">Page type</TableHead>
                    <TableHead scope="col">Gate</TableHead>
                    <TableHead scope="col">Composite</TableHead>
                    <TableHead scope="col">Status</TableHead>
                    <TableHead scope="col">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {previous.map((audit) => (
                    <TableRow key={audit.audit_id}>
                      <TableCell>{formatDateTime(audit.created_at)}</TableCell>
                      <TableCell>{titleCase(audit.page_type)}</TableCell>
                      <TableCell>
                        <GateBadge status={audit.gate_status} />
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {formatNumber(audit.composite)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {titleCase(audit.status)}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
                          <Link
                            href={`/audits/${audit.audit_id}`}
                            className={buttonClasses({ variant: "link", size: "sm" })}
                          >
                            Open
                          </Link>
                          <Link
                            href={`/compare?left=${audit.audit_id}&right=${currentAuditId}`}
                            className={buttonClasses({ variant: "outline", size: "sm" })}
                          >
                            <GitCompareArrows className="h-3.5 w-3.5" aria-hidden />
                            Compare
                          </Link>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </QueryView>
      </section>
    </div>
  );
}
