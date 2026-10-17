"use client";

import { useMemo, useState } from "react";
import { Info, Search } from "@/components/icons";
import { CoverageChip, OriginChip } from "@/components/status";
import { EmptyState } from "@/components/states";
import { Input, Select } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { AuditReport, CoverageRow, FanoutQuery } from "@/lib/types";
import {
  COVERAGE_STATUS_LABELS,
  COVERAGE_STATUSES,
  INTENT_LABELS,
  QUERY_SCOPE_LABELS,
  QUERY_SOURCE_LABELS,
} from "@/lib/types";

/**
 * Provenance summary for the fan-out query set: how many queries are real
 * (observed from a connected source) versus simulated hypotheses.
 *
 * This must stay prominent: simulated queries never count as observed data.
 */
export function FanoutProvenanceSummary({ fanout }: { fanout: FanoutQuery[] }) {
  const observed = fanout.filter((q) => q.origin === "observed").length;
  const simulated = fanout.filter((q) => q.origin === "simulated").length;

  const bySource = useMemo(() => {
    const map = new Map<string, number>();
    for (const q of fanout) {
      const key = QUERY_SOURCE_LABELS[q.source] ?? q.source;
      map.set(key, (map.get(key) ?? 0) + 1);
    }
    return [...map.entries()].sort((a, b) => b[1] - a[1]);
  }, [fanout]);

  const byScope = useMemo(() => {
    const map = new Map<string, number>();
    for (const q of fanout) {
      const key = QUERY_SCOPE_LABELS[q.scope] ?? q.scope;
      map.set(key, (map.get(key) ?? 0) + 1);
    }
    return [...map.entries()];
  }, [fanout]);

  return (
    <section
      aria-labelledby="provenance-heading"
      data-testid="fanout-provenance-summary"
      className="rounded-md border p-4"
    >
      <h3
        id="provenance-heading"
        className="flex items-center gap-2 text-sm font-semibold"
      >
        <Info className="h-4 w-4 text-info" aria-hidden />
        Query provenance
      </h3>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
        <span className="flex items-center gap-1.5">
          <OriginChip origin="observed" />
          <strong className="tabular-nums" data-testid="observed-count">
            {observed} observed
          </strong>
        </span>
        <span className="text-muted-foreground" aria-hidden>
          /
        </span>
        <span className="flex items-center gap-1.5">
          <OriginChip origin="simulated" />
          <strong className="tabular-nums" data-testid="simulated-count">
            {simulated} simulated
          </strong>
        </span>
        <span className="text-muted-foreground">of {fanout.length} total queries</span>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        {observed === 0 ? (
          <>
            <strong className="text-foreground">0 observed.</strong> No connected data
            source (Search Console, Bing, SERP People-Also-Ask, or a user-supplied brief)
            contributed to this fan-out, so every query here is a simulated hypothesis
            generated during the audit. Treat coverage percentages as a structural check,
            not as evidence about real search demand.
          </>) : (
          <>
            {observed} quer{observed === 1 ? "y was" : "ies were"} observed from connected
            sources; {simulated} {simulated === 1 ? "was" : "were"} simulated to fill
            gaps. Simulated queries are clearly labelled in the table below.
          </>
        )}
      </p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            By source
          </p>
          <ul className="space-y-0.5 text-sm">
            {bySource.map(([source, count]) => (
              <li key={source} className="flex justify-between gap-2">
                <span className="text-muted-foreground">{source}</span>
                <span className="tabular-nums">{count}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            By scope
          </p>
          <ul className="space-y-0.5 text-sm">
            {byScope.map(([scope, count]) => (
              <li key={scope} className="flex justify-between gap-2">
                <span className="text-muted-foreground">{scope}</span>
                <span className="tabular-nums">{count}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function CoverageTable({
  rows,
  fanout,
}: {
  rows: CoverageRow[];
  fanout: FanoutQuery[];
}) {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [q, setQ] = useState("");
  const originOf = (queryId: string) =>
    fanout.find((f) => f.query_id === queryId)?.origin ?? "simulated";
  const metaOf = (queryId: string) => fanout.find((f) => f.query_id === queryId);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows.filter((row) => {
      if (statusFilter !== "all" && row.status !== statusFilter) return false;
      if (needle && !row.query_text.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [rows, statusFilter, q]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-12 flex-1 sm:max-w-xs">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter queries…"
            aria-label="Filter queries by text"
            className="pl-8"
          />
        </div>
        <Select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="w-52"
          aria-label="Filter by coverage status"
        >
          <option value="all">All coverage statuses</option>
          {COVERAGE_STATUSES.map((status) => (
            <option key={status} value={status}>
              {COVERAGE_STATUS_LABELS[status]}
            </option>
          ))}
        </Select>
        <p className="text-sm text-muted-foreground">
          {filtered.length} of {rows.length} queries
        </p>
      </div>

      <div className="overflow-x-auto rounded-md border">
        <Table>
          <caption className="sr-only">
            Fan-out queries with origin, scope and coverage status
          </caption>
          <TableHeader>
            <TableRow>
              <TableHead scope="col">Query</TableHead>
              <TableHead scope="col">Origin</TableHead>
              <TableHead scope="col">Source</TableHead>
              <TableHead scope="col">Scope</TableHead>
              <TableHead scope="col">Intent</TableHead>
              <TableHead scope="col">Coverage</TableHead>
              <TableHead scope="col">Score</TableHead>
              <TableHead scope="col">Gap / destination</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((row) => {
              const meta = metaOf(row.query_id);
              return (
                <TableRow key={row.query_id}>
                  <TableCell className="max-w-[20rem] font-medium">
                    {row.query_text}
                  </TableCell>
                  <TableCell>
                    <OriginChip origin={originOf(row.query_id)} />
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {meta ? (QUERY_SOURCE_LABELS[meta.source] ?? meta.source) : "—"}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {meta ? (QUERY_SCOPE_LABELS[meta.scope] ?? meta.scope) : "—"}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {meta ? (INTENT_LABELS[meta.intent] ?? meta.intent) : "—"}
                  </TableCell>
                  <TableCell>
                    <CoverageChip status={row.status} />
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {row.coverage_score.toFixed(2)}
                  </TableCell>
                  <TableCell className="max-w-[16rem] text-xs text-muted-foreground">
                    {row.gap_reason ?? ""}
                    {row.destination_page ? (
                      <span className="block">
                        Suggested destination: {row.destination_page}
                      </span>
                    ) : null}
                    {!row.gap_reason && !row.destination_page ? (
                      <span className="text-muted-foreground">
                        {row.matched_passage_ids.length} matched passage
                        {row.matched_passage_ids.length === 1 ? "" : "s"}
                      </span>
                    ) : null}
                  </TableCell>
                </TableRow>
              );
            })}
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="py-6 text-center text-sm text-muted-foreground">
                  No query matches the current filters.
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export function QueriesTab({ report }: { report: AuditReport }) {
  if (report.fanout.length === 0) {
    return (
      <EmptyState
        title="No fan-out queries"
        description="No queries were generated for this audit, so fan-out coverage could not be assessed. Re-run the audit, or supply queries in the wizard’s primary/secondary query fields."
      />
    );
  }
  return (
    <div className="space-y-4">
      <FanoutProvenanceSummary fanout={report.fanout} />
      <CoverageTable rows={report.coverage_rows} fanout={report.fanout} />
      <p className="text-xs text-muted-foreground">
        Coverage maps each query to the passages that could answer it. “Partial” means a
        passage touches the query but does not answer it in extractable form — a common
        cause of a low coverage score even when the topic is discussed.
      </p>
    </div>
  );
}
