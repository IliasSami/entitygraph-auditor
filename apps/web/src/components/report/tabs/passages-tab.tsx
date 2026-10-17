"use client";

import { useMemo, useState } from "react";
import { AlignLeft, CheckCircle2, CircleAlert } from "@/components/icons";
import { SeverityBadge } from "@/components/status";
import { EmptyState } from "@/components/states";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AuditReport, Finding, Passage, PassageSkill } from "@/lib/types";
import { ANSWER_SHAPE_LABELS } from "@/lib/types";

function PassageListItem({
  passage,
  active,
  onSelect,
}: {
  passage: Passage;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={active ? "true" : undefined}
        className={`w-full px-3 py-2 text-left text-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
          active ? "bg-accent font-medium" : ""
        }`}
      >
        <span className="flex items-center justify-between gap-2">
          <span className="font-mono text-xs">{passage.passage_id}</span>
          <span className="text-xs tabular-nums text-muted-foreground">
            {passage.word_count}w
          </span>
        </span>
        <span className="mt-0.5 block truncate text-xs text-muted-foreground">
          {passage.text}
        </span>
        <span className="mt-1 flex flex-wrap gap-1 text-[11px]">
          <span
            className={`rounded px-1 ${
              passage.answer_first
                ? "bg-success/15 text-success"
                : "bg-warning/15 text-warning"
            }`}
          >
            {passage.answer_first ? "answer-first ✓" : "not answer-first"}
          </span>
          <span
            className={`rounded px-1 ${
              passage.named_subject
                ? "bg-success/15 text-success"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {passage.named_subject ? "named subject" : "no named subject"}
          </span>
          {passage.issues.length ? (
            <span className="rounded bg-destructive/15 px-1 text-destructive">
              {passage.issues.length} issue{passage.issues.length === 1 ? "" : "s"}
            </span>
          ) : null}
        </span>
      </button>
    </li>
  );
}

export function PassagesTab({ report }: { report: AuditReport }) {
  const passages = report.passages ?? [];
  const skills = useMemo(() => {
    const map = new Map<string, PassageSkill>();
    for (const skill of report.passage_skills ?? []) map.set(skill.passage_id, skill);
    return map;
  }, [report.passage_skills]);

  const [selectedId, setSelectedId] = useState<string | null>(
    passages[0]?.passage_id ?? null,
  );
  const selected = passages.find((p) => p.passage_id === selectedId) ?? null;
  const relatedFindings: Finding[] = report.passage_findings.filter(
    (f) => f.where?.passage_id && f.where.passage_id === selectedId,
  );
  const skill = selectedId ? skills.get(selectedId) : undefined;

  if (passages.length === 0 && report.passage_findings.length === 0) {
    return (
      <EmptyState
        title="No passage audit available"
        description="This report does not include passage-level data. Passage retrievability (PRS) is scored from the parsed document; if this audit was run without content, re-run it with the page text."
      />
    );
  }

  return (
    <div className="space-y-4">
      {passages.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
          <nav
            aria-label="Passage list"
            className="max-h-[36rem] overflow-y-auto rounded-md border"
          >
            <ul className="divide-y">
              {passages.map((passage) => (
                <PassageListItem
                  key={passage.passage_id}
                  passage={passage}
                  active={passage.passage_id === selectedId}
                  onSelect={() => setSelectedId(passage.passage_id)}
                />
              ))}
            </ul>
          </nav>

          <section aria-label="Passage detail" className="min-w-0 space-y-3">
            {selected ? (
              <>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                      <AlignLeft className="h-4 w-4 text-primary" aria-hidden />
                      <span className="font-mono">{selected.passage_id}</span>
                      <span className="text-muted-foreground">
                        · section {selected.section_id} · chars {selected.start_offset}–
                        {selected.end_offset} · {selected.word_count} words
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <blockquote className="border-l-2 border-primary/50 pl-3 text-sm leading-relaxed">
                      {selected.text}
                    </blockquote>
                    <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
                      <div>
                        <dt className="text-xs text-muted-foreground">Answer first</dt>
                        <dd>
                          {selected.answer_first ? (
                            <span className="inline-flex items-center gap-1 text-success">
                              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden /> Yes
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-warning">
                              <CircleAlert className="h-3.5 w-3.5" aria-hidden /> No
                            </span>
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">Named subject</dt>
                        <dd>{selected.named_subject ? "Yes" : "No"}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">Answer shape</dt>
                        <dd>
                          {selected.answer_shape
                            ? (ANSWER_SHAPE_LABELS[selected.answer_shape] ??
                              selected.answer_shape)
                            : "Not set"}
                        </dd>
                      </div>
                    </dl>
                    {skill ? (
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div>
                          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Strengths
                          </p>
                          {skill.strengths.length ? (
                            <ul className="list-disc space-y-0.5 pl-4 text-sm text-muted-foreground">
                              {skill.strengths.map((s) => (
                                <li key={s}>{s}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-sm text-muted-foreground">None recorded.</p>
                          )}
                        </div>
                        <div>
                          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Issues
                          </p>
                          {skill.issues.length ? (
                            <ul className="list-disc space-y-0.5 pl-4 text-sm text-muted-foreground">
                              {skill.issues.map((i) => (
                                <li key={i}>{i}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-sm text-muted-foreground">None recorded.</p>
                          )}
                        </div>
                      </div>
                    ) : null}
                    {selected.issues.length ? (
                      <ul className="flex flex-wrap gap-1">
                        {selected.issues.map((issue) => (
                          <li
                            key={issue}
                            className="rounded bg-warning/15 px-1.5 py-0.5 text-xs text-warning"
                          >
                            {issue}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </CardContent>
                </Card>

                {relatedFindings.length ? (
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">
                        Findings in this passage ({relatedFindings.length})
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {relatedFindings.map((finding) => (
                        <div key={finding.finding_id} className="rounded-md border p-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <SeverityBadge severity={finding.severity} />
                            <span className="text-sm font-medium">{finding.title}</span>
                          </div>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {finding.what}
                          </p>
                          {finding.how?.suggested_rewrite ? (
                            <p className="mt-2 rounded bg-success/10 p-2 text-sm">
                              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                Suggested rewrite
                              </span>
                              <span className="mt-0.5 block">
                                {finding.how.suggested_rewrite}
                              </span>
                            </p>
                          ) : null}
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ) : null}
              </>
            ) : (
              <EmptyState
                title="Select a passage"
                description="Choose a passage to see its text, extractability flags, and related findings."
              />
            )}
          </section>
        </div>
      ) : null}

      {report.passage_findings.length > 0 ? (
        <section aria-labelledby="passage-findings-heading">
          <h3 id="passage-findings-heading" className="mb-2 text-base font-semibold">
            All passage findings ({report.passage_findings.length})
          </h3>
          <ul className="space-y-2">
            {report.passage_findings.map((finding) => (
              <li key={finding.finding_id} className="rounded-md border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={finding.severity} />
                  <span className="text-sm font-medium">{finding.title}</span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {finding.where?.passage_id ?? finding.where?.section_id ?? "no location"}
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{finding.what}</p>
                {finding.where?.excerpt ? (
                  <q className="mt-1 block border-l-2 border-primary/40 pl-2 text-sm text-muted-foreground">
                    {finding.where.excerpt}
                  </q>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <EmptyState
          title="No passage findings"
          description="No extractability issues were flagged in this audit’s passages."
        />
      )}
    </div>
  );
}
