"use client";

import { useState } from "react";
import { Link2 } from "@/components/icons";
import { ConfidenceBadge, TripleStatusChip } from "@/components/status";
import { EmptyState } from "@/components/states";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { titleCase } from "@/lib/format";
import type { AuditReport, SemanticTriple } from "@/lib/types";
import { TRIPLE_TYPE_LABELS } from "@/lib/types";

function TripleEvidenceCell({ triple }: { triple: SemanticTriple }) {
  const [open, setOpen] = useState(false);
  if (!triple.evidence_excerpt && !triple.notes) {
    return (
      <span className="text-xs text-muted-foreground">No evidence captured</span>
    );
  }
  return (
    <div className="max-w-[20rem]">
      {triple.evidence_excerpt ? (
        <>
          <button
            type="button"
            className="text-sm font-medium text-primary hover:underline"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
          >
            {open ? "Hide evidence" : "Show evidence"}
          </button>
          {open ? (
            <span className="mt-1 block">
              <q className="block text-sm">{triple.evidence_excerpt}</q>
              <span className="mt-1 block text-xs text-muted-foreground">
                {triple.passage_id ?? "passage unknown"}
              </span>
            </span>
          ) : null}
        </>
      ) : (
        <span className="text-xs text-warning">{triple.notes}</span>
      )}
    </div>
  );
}

export function RelationshipsTab({ report }: { report: AuditReport }) {
  if (report.triples.length === 0) {
    return (
      <EmptyState
        title="No relationships extracted"
        description="No subject–predicate–object triples were found. Relationship clarity drives the ERS and KGR scores — describe in plain sentences how your entities relate to each other (what they do, who they serve, where they operate)."
        action={
          <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            <Link2 className="h-4 w-4" aria-hidden /> e.g. “Northwind Roofing serves
            residential customers in Tacoma.”
          </span>
        }
      />
    );
  }

  const counts = {
    explicit: report.triples.filter((t) => t.status === "explicit").length,
    implied: report.triples.filter((t) => t.status === "implied").length,
    unsupported: report.triples.filter((t) => t.status === "unsupported").length,
    wrong: report.triples.filter((t) => t.status === "wrong").length,
    missing: report.triples.filter((t) => t.status === "missing").length,
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 text-sm">
        {(
          [
            ["Explicit", counts.explicit, "text-success"],
            ["Implied", counts.implied, "text-info"],
            ["Unsupported", counts.unsupported, "text-warning"],
            ["Wrong", counts.wrong, "text-destructive"],
            ["Missing", counts.missing, "text-destructive"],
          ] as const
        ).map(([label, value, tone]) => (
          <div key={label} className="min-w-28 rounded-md border px-3 py-2">
            <p className={`text-lg font-semibold tabular-nums ${tone}`}>{value}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto rounded-md border">
        <Table>
          <caption className="sr-only">
            Extracted subject–predicate–object relationships with status, type and evidence
          </caption>
          <TableHeader>
            <TableRow>
              <TableHead scope="col">Subject</TableHead>
              <TableHead scope="col">Predicate</TableHead>
              <TableHead scope="col">Object</TableHead>
              <TableHead scope="col">Type</TableHead>
              <TableHead scope="col">Status</TableHead>
              <TableHead scope="col">Confidence</TableHead>
              <TableHead scope="col">Evidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {report.triples.map((triple) => (
              <TableRow key={triple.triple_id}>
                <TableCell className="font-medium">{triple.subject}</TableCell>
                <TableCell className="font-mono text-xs">{triple.predicate}</TableCell>
                <TableCell className="font-medium">{triple.object_}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {TRIPLE_TYPE_LABELS[triple.triple_type] ?? titleCase(triple.triple_type)}
                </TableCell>
                <TableCell>
                  <TripleStatusChip status={triple.status} />
                </TableCell>
                <TableCell>
                  <ConfidenceBadge confidence={triple.confidence} />
                </TableCell>
                <TableCell>
                  <TripleEvidenceCell triple={triple} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">How to read this</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
          <p>
            <strong className="text-foreground">Explicit</strong> — stated verbatim in the
            content, with an evidence excerpt to prove it.
          </p>
          <p>
            <strong className="text-foreground">Implied</strong> — inferred from context
            but not stated directly. Stronger than nothing, weaker than a direct claim.
          </p>
          <p>
            <strong className="text-foreground">Unsupported</strong> — claimed but no
            evidence was found in the audited content.
          </p>
          <p>
            <strong className="text-foreground">Wrong / Missing</strong> — contradicted by
            the content, or a canonical relationship of this page type that is absent.
            Fix these first: answer engines treat them as trust signals.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
