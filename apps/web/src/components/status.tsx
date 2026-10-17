import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/format";
import type {
  Confidence,
  CoverageStatus,
  EAVStatus,
  GateStatus,
  ResultOrigin,
  Severity,
  StageStatus,
  TripleStatus,
  VerificationState,
} from "@/lib/types";
import {
  CONFIDENCE_LABELS,
  COVERAGE_STATUS_LABELS,
  EAV_STATUS_LABELS,
  GATE_STATUS_LABELS,
  RESULT_ORIGIN_LABELS,
  SEVERITY_LABELS,
  STAGE_STATUS_LABELS,
  TRIPLE_STATUS_LABELS,
  VERIFICATION_STATE_LABELS,
} from "@/lib/types";

type Tone = "success" | "warning" | "destructive" | "secondary" | "info" | "default";

const TONE_ICON: Record<Tone, string> = {
  success: "✓",
  warning: "⚠",
  destructive: "✕",
  secondary: "○",
  info: "ℹ",
  default: "•",
};

const TONE_VARIANT: Record<Tone, Parameters<typeof Badge>[0]["variant"]> = {
  success: "success",
  warning: "warning",
  destructive: "destructive",
  secondary: "secondary",
  info: "info",
  default: "default",
};

function ToneBadge({
  tone,
  children,
  className,
  testId,
}: {
  tone: Tone;
  children: React.ReactNode;
  className?: string;
  testId?: string;
}) {
  return (
    <Badge variant={TONE_VARIANT[tone]} className={className} data-testid={testId}>
      <span aria-hidden="true">{TONE_ICON[tone]}</span>
      {children}
    </Badge>
  );
}

/* ------------------------------------------------------------- publish gate */

const GATE_TONE: Record<GateStatus, Tone> = {
  pass: "success",
  pass_with_fixes: "warning",
  fail: "destructive",
  not_configured: "secondary",
  not_assessed: "secondary",
};

export function GateBadge({
  status,
  className,
}: {
  status: GateStatus | null | undefined;
  className?: string;
}) {
  if (!status) {
    return (
      <ToneBadge tone="secondary" className={className} testId="gate-badge">
        Not assessed
      </ToneBadge>
    );
  }
  return (
    <ToneBadge tone={GATE_TONE[status]} className={cn("text-xs", className)} testId="gate-badge">
      {GATE_STATUS_LABELS[status]}
    </ToneBadge>
  );
}

/* -------------------------------------------------------------- run stages */

const STAGE_TONE: Record<StageStatus, Tone> = {
  pending: "secondary",
  running: "info",
  succeeded: "success",
  failed: "destructive",
  skipped: "secondary",
  cached: "info",
};

export function StageStatusBadge({ status }: { status: StageStatus }) {
  const icon = status === "cached" ? "⚡" : status === "skipped" ? "→" : TONE_ICON[STAGE_TONE[status]];
  return (
    <Badge variant={TONE_VARIANT[STAGE_TONE[status]]}>
      <span aria-hidden="true">{icon}</span>
      {STAGE_STATUS_LABELS[status]}
    </Badge>
  );
}

const ORIGIN_TONE: Record<ResultOrigin, Tone> = {
  deterministic: "secondary",
  model_generated: "info",
  externally_verified: "success",
};

export function OriginBadge({ origin }: { origin: ResultOrigin }) {
  return (
    <Badge variant={TONE_VARIANT[ORIGIN_TONE[origin]]} data-testid="origin-badge">
      {RESULT_ORIGIN_LABELS[origin]}
    </Badge>
  );
}

/* -------------------------------------------------------------- entity EAV */

const EAV_TONE: Record<EAVStatus, Tone> = {
  explicit: "success",
  vague: "warning",
  missing: "destructive",
  conflicting: "destructive",
  unverified: "warning",
  not_applicable: "secondary",
};

export function EavStatusChip({ status }: { status: EAVStatus }) {
  return (
    <ToneBadge tone={EAV_TONE[status]} testId="eav-status-chip">
      {EAV_STATUS_LABELS[status]}
    </ToneBadge>
  );
}

const TRIPLE_TONE: Record<TripleStatus, Tone> = {
  explicit: "success",
  implied: "info",
  missing: "destructive",
  wrong: "destructive",
  unsupported: "warning",
};

export function TripleStatusChip({ status }: { status: TripleStatus }) {
  return <ToneBadge tone={TRIPLE_TONE[status]}>{TRIPLE_STATUS_LABELS[status]}</ToneBadge>;
}

/* ------------------------------------------------------------------ claims */

const VERIFICATION_TONE: Record<VerificationState, Tone> = {
  verified: "success",
  unverified: "destructive",
  conflicting: "destructive",
  not_assessed: "secondary",
};

export function VerificationBadge({ state }: { state: VerificationState }) {
  return (
    <ToneBadge tone={VERIFICATION_TONE[state]} testId="verification-badge">
      {VERIFICATION_STATE_LABELS[state]}
    </ToneBadge>
  );
}

/* ---------------------------------------------------------------- findings */

const SEVERITY_TONE: Record<Severity, Tone> = {
  critical: "destructive",
  high: "destructive",
  medium: "warning",
  low: "info",
  info: "secondary",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <ToneBadge tone={SEVERITY_TONE[severity]}>
      {SEVERITY_LABELS[severity]}
    </ToneBadge>
  );
}

const CONFIDENCE_TONE: Record<Confidence, Tone> = {
  high: "success",
  medium: "info",
  low: "warning",
  not_assessed: "secondary",
};

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  return (
    <Badge variant={TONE_VARIANT[CONFIDENCE_TONE[confidence]]}>
      <span aria-hidden="true">
        {confidence === "high" ? "●●●" : confidence === "medium" ? "●●○" : confidence === "low" ? "●○○" : "—"}
      </span>
      {CONFIDENCE_LABELS[confidence]}
    </Badge>
  );
}

/* -------------------------------------------------------------- fan-out */

const COVERAGE_TONE: Record<CoverageStatus, Tone> = {
  covered: "success",
  partial: "warning",
  missing: "destructive",
  excluded: "secondary",
};

export function CoverageChip({ status }: { status: CoverageStatus }) {
  return <ToneBadge tone={COVERAGE_TONE[status]}>{COVERAGE_STATUS_LABELS[status]}</ToneBadge>;
}

/* ------------------------------------------------------- honest labelling */

export function OriginChip({ origin }: { origin: "observed" | "simulated" }) {
  return origin === "observed" ? (
    <Badge variant="success">
      <span aria-hidden="true">✓</span>Observed
    </Badge>
  ) : (
    <Badge variant="info">
      <span aria-hidden="true">≈</span>Simulated
    </Badge>
  );
}

export function SampleDataBanner({ compact = false }: { compact?: boolean }) {
  return (
    <div
      role="note"
      data-testid="sample-data-banner"
      className="flex items-center gap-2 rounded-md border border-accent-foreground/20 bg-accent px-3 py-2 text-xs text-accent-foreground"
    >
      <span aria-hidden="true">◆</span>
      <span className="font-medium">Sample data — not a real audit.</span>
      {!compact ? (
        <span className="text-accent-foreground/80">
          This view is driven by a built-in demo fixture so the interface can be explored without a
          backend.
        </span>
      ) : null}
    </div>
  );
}

export function HeuristicDisclaimer({ className }: { className?: string }) {
  return (
    <p className={cn("text-xs text-muted-foreground", className)} data-testid="heuristic-disclaimer">
      Internal editorial heuristic — not an official Google, Bing, OpenAI, Anthropic, or Perplexity
      metric. When no model provider is configured, semantic sections (entities, triples, claims and
      recommendations) come from a built-in deterministic baseline and are illustrative placeholders,
      not observed evidence.
    </p>
  );
}
