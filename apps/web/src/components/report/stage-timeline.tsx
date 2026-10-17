"use client";

import { CheckCircle2, Circle, Loader2, XCircle } from "@/components/icons";
import { OriginBadge, StageStatusBadge } from "@/components/status";
import { EmptyState } from "@/components/states";
import type { StageRecord } from "@/lib/types";
import { formatDuration } from "@/lib/format";

/**
 * Ordered audit-stage timeline driven purely by server progress records —
 * no invented percentages: only completed/total counts and real timings.
 */
export function StageTimeline({
  stages,
  note,
}: {
  stages: StageRecord[];
  note?: string;
}) {
  if (stages.length === 0) {
    return (
      <EmptyState
        title="Waiting for the first stage"
        description="The run has been queued. The first stage will appear here as soon as the server starts working."
      />
    );
  }
  const done = stages.filter((s) =>
    ["succeeded", "cached", "skipped"].includes(s.status),
  ).length;
  const failedStage = stages.find((s) => s.status === "failed");
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground" role="status">
        <span className="font-medium text-foreground tabular-nums">
          {done} of {stages.length}
        </span>{" "}
        stages complete{failedStage ? " · a stage failed" : ""}.
      </p>
      <ol className="space-y-1" aria-label="Audit stages">
        {stages.map((stage) => {
          const active = stage.status === "running";
          const Icon =
            stage.status === "succeeded" || stage.status === "cached"
              ? CheckCircle2
              : stage.status === "failed"
                ? XCircle
                : active
                  ? Loader2
                  : Circle;
          return (
            <li
              key={stage.node}
              className={`flex items-start gap-3 rounded-md border px-3 py-2 ${
                active
                  ? "border-primary/60 bg-primary/5"
                  : stage.status === "failed"
                    ? "border-destructive/50 bg-destructive/5"
                    : "border-transparent"
              }`}
              aria-current={active ? "step" : undefined}
            >
              <Icon
                className={`mt-0.5 h-4 w-4 shrink-0 ${
                  active ? "animate-spin text-primary" : ""
                } ${
                  stage.status === "succeeded" || stage.status === "cached"
                    ? "text-success"
                    : stage.status === "failed"
                      ? "text-destructive"
                      : "text-muted-foreground"
                }`}
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{stage.label}</span>
                  <StageStatusBadge status={stage.status} />
                  <OriginBadge origin={stage.origin} />
                  {stage.cached ? (
                    <span className="text-xs text-muted-foreground">(cache hit)</span>
                  ) : null}
                </div>
                {stage.detail ? (
                  <p className="mt-0.5 break-words text-xs text-muted-foreground">
                    {stage.detail}
                  </p>
                ) : null}
                {stage.error ? (
                  <p className="mt-1 break-words text-xs font-medium text-destructive">
                    {stage.error}
                    {stage.retries > 0 ? ` · ${stage.retries} retries` : ""}
                  </p>
                ) : null}
              </div>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {stage.duration_ms != null ? formatDuration(stage.duration_ms) : ""}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="text-xs text-muted-foreground">
        {note ??
          "Each stage is labelled with how its result was produced: deterministic, model-generated, or externally verified."}
      </p>
    </div>
  );
}
