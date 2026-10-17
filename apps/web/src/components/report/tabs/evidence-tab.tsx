"use client";

import { useMemo, useState } from "react";
import { ExternalLink, FileCheck2, ShieldQuestion } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { VerificationBadge } from "@/components/status";
import { EmptyState } from "@/components/states";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate, titleCase } from "@/lib/format";
import type { AuditReport, Claim, EvidenceSource } from "@/lib/types";
import {
  CLAIM_RISK_TIER_LABELS,
  EVIDENCE_LABEL_LABELS,
  VERIFICATION_STATE_LABELS,
} from "@/lib/types";

function ClaimCard({
  claim,
  sources,
}: {
  claim: Claim;
  sources: EvidenceSource[];
}) {
  const linked = claim.evidence_source_ids
    .map((id) => sources.find((s) => s.source_id === id))
    .filter((s): s is EvidenceSource => Boolean(s));
  return (
    <li className="rounded-md border p-3" data-testid="claim-card">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 text-sm font-medium">{claim.statement}</p>
        <VerificationBadge state={claim.verification_state} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        <Badge variant={claim.risk_tier === "ordinary" ? "secondary" : "warning"}>
          {CLAIM_RISK_TIER_LABELS[claim.risk_tier] ?? titleCase(claim.risk_tier)}
        </Badge>
        {claim.requires_substantiation ? (
          <Badge variant="warning">Requires substantiation</Badge>
        ) : (
          <Badge variant="secondary">No substantiation required</Badge>
        )}
        {claim.passage_id ? (
          <span className="font-mono text-muted-foreground">{claim.passage_id}</span>
        ) : null}
      </div>
      {claim.issue ? (
        <p className="mt-2 text-sm text-destructive">{claim.issue}</p>
      ) : null}
      {linked.length ? (
        <div className="mt-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Evidence
          </p>
          <ul className="mt-1 space-y-1">
            {linked.map((source) => (
              <li key={source.source_id} className="flex items-start gap-1.5 text-sm">
                <FileCheck2
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success"
                  aria-hidden
                />
                <span>
                  {source.url ? (
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      {source.title}
                    </a>
                  ) : (
                    source.title
                  )}
                  <span className="ml-1 text-xs text-muted-foreground">
                    · {EVIDENCE_LABEL_LABELS[source.label] ?? source.label}
                    {source.publisher ? ` · ${source.publisher}` : ""}
                    {source.publication_date
                      ? ` · ${formatDate(source.publication_date)}`
                      : ""}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : claim.verification_state !== "verified" ? (
        <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
          <ShieldQuestion className="h-3.5 w-3.5" aria-hidden /> No evidence source linked
          to this claim.
        </p>
      ) : null}
    </li>
  );
}

export function EvidenceTab({ report }: { report: AuditReport }) {
  const [filter, setFilter] = useState<string>("all");

  const counts = useMemo(() => {
    const map: Record<string, number> = {
      verified: 0,
      unverified: 0,
      conflicting: 0,
      not_assessed: 0,
    };
    for (const claim of report.claims) map[claim.verification_state] += 1;
    return map;
  }, [report.claims]);

  const claims =
    filter === "all"
      ? report.claims
      : report.claims.filter((c) => c.verification_state === filter);

  if (report.claims.length === 0 && report.sources.length === 0) {
    return (
      <EmptyState
        title="No claims or evidence recorded"
        description="The auditor did not identify checkable claims in this content, and no evidence sources were supplied. Add verifiable statements (numbers, certifications, dates) to the page so claim checking has something to work with."
      />
    );
  }

  return (
    <div className="space-y-6">
      <section aria-labelledby="claims-heading">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 id="claims-heading" className="text-base font-semibold">
            Claims ({report.claims.length})
          </h2>
          <div className="flex flex-wrap gap-1" role="group" aria-label="Filter claims by verification">
            {(["all", "verified", "unverified", "conflicting", "not_assessed"] as const).map(
              (key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setFilter(key)}
                  aria-pressed={filter === key}
                  className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                    filter === key
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border text-muted-foreground hover:bg-accent"
                  }`}
                >
                  {key === "all"
                    ? `All (${report.claims.length})`
                    : `${VERIFICATION_STATE_LABELS[key]} (${counts[key]})`}
                </button>
              ),
            )}
          </div>
        </div>

        {report.claims.length === 0 ? (
          <EmptyState
            title="No claims identified"
            description="Nothing in this content was classified as a checkable claim."
          />
        ) : claims.length === 0 ? (
          <EmptyState
            title={`No ${VERIFICATION_STATE_LABELS[filter as keyof typeof VERIFICATION_STATE_LABELS] ?? filter} claims`}
            description="Try another filter."
          />
        ) : (
          <ul className="space-y-2">
            {claims.map((claim) => (
              <ClaimCard key={claim.claim_id} claim={claim} sources={report.sources} />
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="sources-heading">
        <h2 id="sources-heading" className="mb-3 text-base font-semibold">
          Evidence sources ({report.sources.length})
        </h2>
        {report.sources.length === 0 ? (
          <EmptyState
            title="No evidence sources"
            description="No citations were attached to this report. Sources can come from the context pack’s canonical facts or from claims verified during the audit."
          />
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {report.sources.map((source) => (
              <Card key={source.source_id}>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-start justify-between gap-2 text-sm">
                    <span className="min-w-0">
                      {source.url ? (
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-primary hover:underline"
                        >
                          {source.title}
                          <ExternalLink className="h-3 w-3" aria-hidden />
                        </a>
                      ) : (
                        source.title
                      )}
                    </span>
                    <Badge
                      variant={
                        source.label === "unverified" || source.label === "speculative"
                          ? "warning"
                          : "info"
                      }
                    >
                      {EVIDENCE_LABEL_LABELS[source.label] ?? source.label}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-1 text-sm text-muted-foreground">
                  {source.publisher ? <p>Publisher: {source.publisher}</p> : null}
                  {source.publication_date ? (
                    <p>Published: {formatDate(source.publication_date)}</p>
                  ) : null}
                  {source.accessed_at ? (
                    <p>Accessed: {formatDate(source.accessed_at)}</p>
                  ) : null}
                  {source.excerpt ? <q className="block">{source.excerpt}</q> : null}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <p className="text-xs text-muted-foreground">
        Verification states describe what this tool could check against supplied or linked
        sources. “Verified” does not mean independently fact-checked by a third party
        unless the source itself is an official register.
      </p>
    </div>
  );
}
