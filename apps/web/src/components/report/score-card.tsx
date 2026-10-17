"use client";

import * as React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Drawer } from "@/components/ui/drawer";
import { ConfidenceBadge, HeuristicDisclaimer } from "@/components/status";
import { cn, formatNumber } from "@/lib/format";
import type { ComponentScore, ScoreKey } from "@/lib/types";
import { SCORE_LABELS } from "@/lib/types";

function SubScoreBar({ label, value }: { label: string; value: number }) {
  const pretty = label
    .split(/[_\s]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="min-w-0 flex-1 truncate text-muted-foreground" title={pretty}>
        {pretty}
      </span>
      <div className="h-1.5 w-24 shrink-0 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, value * 10)}%` }} />
      </div>
      <span className="w-8 text-right font-mono text-xs">{formatNumber(value)}</span>
    </div>
  );
}

export interface ScoreCardProps {
  score: ComponentScore;
  onSelect?: (score: ComponentScore) => void;
  className?: string;
}

/** Compact component-score card; clicking opens the rubric drawer. */
export function ScoreCard({ score, onSelect, className }: ScoreCardProps) {
  const content = (
    <>
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-xs font-semibold">{score.score_key}</span>
        <span className="text-2xl font-semibold tabular-nums">{formatNumber(score.value)}</span>
      </div>
      <div className="mt-0.5 text-left text-xs text-muted-foreground">
        {SCORE_LABELS[score.score_key]}
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <div className="h-full rounded-full bg-primary" style={{ width: `${score.value * 10}%` }} />
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
        <span>{score.weight}% weight</span>
        <ConfidenceBadge confidence={score.confidence} />
      </div>
    </>
  );

  return (
    <Card
      className={cn("transition-colors", onSelect && "hover:border-primary/50", className)}
      data-testid="score-card"
    >
      <CardContent className="p-4">
        {onSelect ? (
          <button
            type="button"
            onClick={() => onSelect(score)}
            className="w-full text-left rounded focus-visible:outline-2 focus-visible:outline-ring"
            aria-label={`Open rubric detail for ${SCORE_LABELS[score.score_key]}`}
          >
            {content}
          </button>
        ) : (
          <div>{content}</div>
        )}
      </CardContent>
    </Card>
  );
}

/** Drawer with the full rubric breakdown for one component score. */
export function ScoreDrawer({
  score,
  onOpenChange,
}: {
  score: ComponentScore | null;
  onOpenChange: (score: ComponentScore | null) => void;
}) {
  const open = score !== null;
  const key = score?.score_key ?? "";
  return (
    <Drawer
      open={open}
      onOpenChange={(next) => {
        if (!next) onOpenChange(null);
      }}
        title={score ? `${score.score_key} — ${SCORE_LABELS[key as ScoreKey] ?? key}` : "Score detail"}
    >
      {score ? (
        <div className="flex flex-col gap-4" data-testid="score-drawer">
          <div className="flex items-center gap-3">
            <span className="text-3xl font-semibold tabular-nums">{formatNumber(score.value)}</span>
            <span className="text-sm text-muted-foreground">/ 10 · {score.weight}% of composite</span>
            <ConfidenceBadge confidence={score.confidence} />
          </div>

          <p className="text-sm">{score.rationale}</p>

          <section aria-labelledby={`sub-${score.score_key}`}>
            <h3 id={`sub-${score.score_key}`} className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Rubric sub-scores
            </h3>
            <div className="flex flex-col gap-2">
              {Object.entries(score.sub_scores).map(([label, value]) => (
                <SubScoreBar key={label} label={label} value={value} />
              ))}
              {Object.keys(score.sub_scores).length === 0 ? (
                <p className="text-sm text-muted-foreground">No sub-scores were recorded for this component.</p>
              ) : null}
            </div>
          </section>

          <section aria-labelledby={`lost-${score.score_key}`}>
            <h3 id={`lost-${score.score_key}`} className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Why points were lost
            </h3>
            {score.lost_points_reasons.length ? (
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {score.lost_points_reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No points were deducted on this component.</p>
            )}
          </section>

          {score.observed_queries !== null && score.observed_queries !== undefined ? (
            <p className="text-sm text-muted-foreground">
              Coverage was computed from {score.observed_queries} observed and{" "}
              {score.simulated_queries ?? 0} simulated queries.
            </p>
          ) : null}

          <HeuristicDisclaimer />
        </div>
      ) : null}
    </Drawer>
  );
}
