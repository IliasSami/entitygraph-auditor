"use client";

import { useMemo, useState } from "react";
import { ExternalLink, Search, Star } from "@/components/icons";
import {
  ConfidenceBadge,
  EavStatusChip,
} from "@/components/status";
import { EmptyState } from "@/components/states";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { titleCase } from "@/lib/format";
import type { AuditReport, EAVRow, Entity } from "@/lib/types";
import { ENTITY_KIND_LABELS, EXTRACTION_METHOD_LABELS } from "@/lib/types";

/** Attribute rows belonging to one entity (rows reference entities by name). */
function rowsForEntity(report: AuditReport, entity: Entity): EAVRow[] {
  return report.eav_rows.filter((row) => row.entity_name === entity.canonical_name);
}

function CoverageSummary({ rows }: { rows: EAVRow[] }) {
  const explicit = rows.filter((r) => r.status === "explicit").length;
  const missing = rows.filter((r) => r.status === "missing").length;
  const vague = rows.filter((r) => r.status === "vague").length;
  const conflicting = rows.filter((r) => r.status === "conflicting").length;
  if (rows.length === 0) {
    return <span className="text-xs text-muted-foreground">No attribute rows</span>;
  }
  return (
    <span className="flex flex-wrap items-center gap-1 text-xs" title="Attribute rows by status">
      <span className="font-medium tabular-nums">
        {explicit}/{rows.length}
      </span>
      <span className="text-muted-foreground">explicit</span>
      {missing ? (
        <span className="font-medium text-destructive tabular-nums">· {missing} missing</span>
      ) : null}
      {vague ? (
        <span className="font-medium text-warning tabular-nums">· {vague} vague</span>
      ) : null}
      {conflicting ? (
        <span className="font-medium text-destructive tabular-nums">
          · {conflicting} conflicting
        </span>
      ) : null}
    </span>
  );
}

function EavTable({ rows, showEntity = true }: { rows: EAVRow[]; showEntity?: boolean }) {
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? rows : rows.slice(0, 50);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {rows.length} attribute row{rows.length === 1 ? "" : "s"} ·{" "}
          {rows.filter((r) => r.status === "missing").length} missing ·{" "}
          {rows.filter((r) => r.status === "vague").length} vague ·{" "}
          {rows.filter((r) => r.status === "explicit").length} explicit
        </p>
        {rows.length > 50 ? (
          <button
            type="button"
            className="text-sm font-medium text-primary hover:underline"
            onClick={() => setShowAll((v) => !v)}
            aria-expanded={showAll}
          >
            {showAll ? "Show first 50 rows" : `Show all ${rows.length} rows`}
          </button>
        ) : null}
      </div>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <caption className="sr-only">
            Entity–attribute–value rows with status, confidence and evidence
          </caption>
          <TableHeader>
            <TableRow>
              {showEntity ? <TableHead scope="col">Entity</TableHead> : null}
              <TableHead scope="col">Attribute</TableHead>
              <TableHead scope="col">Value</TableHead>
              <TableHead scope="col">Status</TableHead>
              <TableHead scope="col">Confidence</TableHead>
              <TableHead scope="col">Required</TableHead>
              <TableHead scope="col">Evidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.map((row) => (
              <TableRow key={row.eav_id}>
                {showEntity ? (
                  <TableCell className="font-medium">{row.entity_name}</TableCell>
                ) : null}
                <TableCell className="font-mono text-xs">{row.attribute}</TableCell>
                <TableCell className="max-w-[20rem] break-words">
                  {row.value ?? <span className="text-muted-foreground">—</span>}
                </TableCell>
                <TableCell>
                  <EavStatusChip status={row.status} />
                </TableCell>
                <TableCell>
                  <ConfidenceBadge confidence={row.confidence} />
                </TableCell>
                <TableCell>
                  {row.is_required_by_page_type ? (
                    <span className="text-xs font-medium text-warning">
                      Required for this page type
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">Optional</span>
                  )}
                </TableCell>
                <TableCell className="max-w-[18rem]">
                  {row.evidence_excerpt ? (
                    <q className="block truncate text-xs" title={row.evidence_excerpt}>
                      {row.evidence_excerpt}
                    </q>
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      {row.notes ?? "—"}
                    </span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export function EntitiesTab({ report }: { report: AuditReport }) {
  const [q, setQ] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(
    report.entities[0]?.entity_id ?? null,
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return report.entities;
    return report.entities.filter(
      (e) =>
        e.canonical_name.toLowerCase().includes(needle) ||
        e.kind.toLowerCase().includes(needle) ||
        e.aliases.some((alias) => alias.toLowerCase().includes(needle)),
    );
  }, [q, report.entities]);

  const selected =
    report.entities.find((e) => e.entity_id === selectedId) ?? null;
  const selectedRows = selected ? rowsForEntity(report, selected) : [];

  if (report.entities.length === 0) {
    return (
      <EmptyState
        title="No entities extracted"
        description="The parser found no entities to audit. Check that the content names the organisation, people, and products you care about — entities drive every downstream score."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-12 flex-1 sm:max-w-xs">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter entities…"
            aria-label="Filter entities by name, kind, or alias"
            className="pl-8"
          />
        </div>
        <p className="text-sm text-muted-foreground">
          {filtered.length} of {report.entities.length} entities ·{" "}
          {report.eav_rows.length} attribute rows
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
        <nav
          aria-label="Entity list"
          className="max-h-[32rem] overflow-y-auto rounded-md border"
        >
          <ul className="divide-y">
            {filtered.map((e) => (
              <li key={e.entity_id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(e.entity_id)}
                  className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                    selectedId === e.entity_id ? "bg-accent font-medium" : ""
                  }`}
                  aria-current={selectedId === e.entity_id ? "true" : undefined}
                >
                  <span className="min-w-0">
                    <span className="flex items-center gap-1 truncate">
                      {e.is_central ? (
                        <Star
                          className="h-3 w-3 shrink-0 fill-current text-warning"
                          aria-hidden
                          aria-label="Central entity"
                        />
                      ) : null}
                      {e.canonical_name}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {ENTITY_KIND_LABELS[e.kind] ?? titleCase(e.kind)}
                    </span>
                  </span>
                  <CoverageSummaryCompact report={report} entity={e} />
                </button>
              </li>
            ))}
            {filtered.length === 0 ? (
              <li className="px-3 py-4 text-sm text-muted-foreground">
                No entity matches “{q}”.
              </li>
            ) : null}
          </ul>
        </nav>

        <div className="min-w-0 space-y-4">
          {selected ? (
            <>
              <div className="rounded-md border p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-semibold">{selected.canonical_name}</h3>
                  <span className="rounded-full bg-secondary px-2 py-0.5 text-xs font-medium">
                    {ENTITY_KIND_LABELS[selected.kind] ?? titleCase(selected.kind)}
                  </span>
                  {selected.is_central ? (
                    <span className="rounded-full bg-warning/15 px-2 py-0.5 text-xs font-medium text-warning">
                      Central entity
                    </span>
                  ) : null}
                </div>
                <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-muted-foreground">Confidence</dt>
                    <dd>
                      <ConfidenceBadge confidence={selected.confidence} />
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Salience</dt>
                    <dd className="tabular-nums">{selected.salience.toFixed(2)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Mentions</dt>
                    <dd className="tabular-nums">
                      {selected.occurrences.length} captured occurrence
                      {selected.occurrences.length === 1 ? "" : "s"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Extraction method</dt>
                    <dd>
                      {EXTRACTION_METHOD_LABELS[selected.method] ?? titleCase(selected.method)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Aliases</dt>
                    <dd className="flex flex-wrap gap-1">
                      {selected.aliases.length ? (
                        selected.aliases.map((alias) => (
                          <span
                            key={alias}
                            className="rounded bg-secondary px-1.5 py-0.5 text-xs"
                          >
                            {alias}
                          </span>
                        ))
                      ) : (
                        <span className="text-muted-foreground">None recorded</span>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Attribute coverage</dt>
                    <dd>
                      <CoverageSummary rows={selectedRows} />
                    </dd>
                  </div>
                  {selected.wikidata_id ? (
                    <div>
                      <dt className="text-muted-foreground">Wikidata</dt>
                      <dd>
                        <a
                          href={`https://www.wikidata.org/wiki/${selected.wikidata_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 font-mono text-xs text-primary hover:underline"
                        >
                          {selected.wikidata_id}
                          <ExternalLink className="h-3 w-3" aria-hidden />
                        </a>
                      </dd>
                    </div>
                  ) : null}
                </dl>
                {selectedRows.some((r) => r.status === "missing") ? (
                  <p className="mt-2 text-sm text-warning">
                    {
                      selectedRows.filter((r) => r.status === "missing").length
                    }{" "}
                    attribute slot{selectedRows.filter((r) => r.status === "missing").length === 1 ? " is" : "s are"}{" "}
                    missing for this entity — answer engines fill those gaps from other
                    sources unless you state them.
                  </p>
                ) : null}
              </div>

              {selected.occurrences.length > 0 ? (
                <div className="rounded-md border p-4">
                  <h4 className="mb-2 text-sm font-semibold">Where it is mentioned</h4>
                  <ul className="space-y-2">
                    {selected.occurrences.slice(0, 5).map((occ, index) => (
                      <li
                        key={`${occ.passage_id}-${index}`}
                        className="border-l-2 border-primary/40 pl-3 text-sm"
                      >
                        <span className="block text-muted-foreground">{occ.sentence}</span>
                        <span className="text-xs text-muted-foreground">
                          {occ.passage_id} · chars {occ.start_offset}–{occ.end_offset}
                        </span>
                      </li>
                    ))}
                  </ul>
                  {selected.occurrences.length > 5 ? (
                    <p className="mt-2 text-xs text-muted-foreground">
                      + {selected.occurrences.length - 5} more occurrences.
                    </p>
                  ) : null}
                </div>
              ) : null}

              {selectedRows.length > 0 ? (
                <EavTable rows={selectedRows} showEntity={false} />
              ) : (
                <EmptyState
                  title="No attribute rows"
                  description="This entity has no entity–attribute–value rows in the report."
                />
              )}
            </>
          ) : (
            <EmptyState
              title="Select an entity"
              description="Choose an entity from the list to see its attributes, mentions, and coverage."
            />
          )}
        </div>
      </div>

      <details className="rounded-md border p-3">
        <summary className="cursor-pointer text-sm font-medium">
          All {report.eav_rows.length} attribute rows (flat table)
        </summary>
        <div className="mt-3">
          <EavTable rows={report.eav_rows} />
        </div>
      </details>

      <p className="text-xs text-muted-foreground">
        Attribute rows compare the canonical EAV schema for each entity type with what the
        content actually says. Missing rows are reported as missing — they are never
        invented to improve coverage.
      </p>
    </div>
  );
}

/** Compact coverage marker used inside the entity list. */
function CoverageSummaryCompact({ report, entity }: { report: AuditReport; entity: Entity }) {
  const rows = rowsForEntity(report, entity);
  const explicit = rows.filter((r) => r.status === "explicit").length;
  const missing = rows.filter((r) => r.status === "missing").length;
  if (rows.length === 0) return null;
  return (
    <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
      {explicit}/{rows.length}
      {missing ? <span className="text-destructive"> · {missing}✗</span> : null}
    </span>
  );
}
