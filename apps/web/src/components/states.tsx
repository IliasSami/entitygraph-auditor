"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/errors";
import { cn } from "@/lib/format";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div
      role="status"
      className="flex items-center gap-2 rounded-lg border border-dashed border-border bg-card p-8 text-sm text-muted-foreground"
    >
      <span aria-hidden="true" className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      {label}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  title = "Something went wrong",
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  const apiError = error instanceof ApiError ? error : null;
  const message = apiError
    ? apiError.isNetwork
      ? apiError.message
      : apiError.message
    : error instanceof Error
      ? error.message
      : "Unexpected error.";
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm"
    >
      <div>
        <p className="font-semibold text-destructive">{title}</p>
        <p className="mt-1 text-muted-foreground">{message}</p>
        {apiError?.code ? (
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            code: {apiError.code}
            {apiError.traceId ? ` · trace: ${apiError.traceId}` : ""}
          </p>
        ) : null}
      </div>
      {onRetry ? (
        <div>
          <Button variant="outline" size="sm" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-2 rounded-lg border border-dashed border-border bg-card p-10 text-center",
        className,
      )}
    >
      <p className="text-sm font-medium">{title}</p>
      {description ? <p className="max-w-md text-sm text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

type QueryLike<T> = {
  data: T | undefined;
  error: unknown;
  isPending: boolean;
  isFetching?: boolean;
  refetch: () => unknown;
};

export interface QueryViewProps<T> {
  query: QueryLike<T>;
  children: (data: T) => React.ReactNode;
  loadingLabel?: string;
  errorTitle?: string;
  /** Rendered when data is present but "empty" (e.g. zero rows). */
  isEmpty?: (data: T) => boolean;
  empty?: React.ReactNode;
}

/**
 * Standard async view: loading / error / empty / data. Every data surface in
 * the app funnels through this so states are consistent.
 */
export function QueryView<T>({
  query,
  children,
  loadingLabel,
  errorTitle,
  isEmpty,
  empty,
}: QueryViewProps<T>) {
  if (query.isPending) return <LoadingState label={loadingLabel} />;
  if (query.error) return <ErrorState error={query.error} title={errorTitle} onRetry={() => query.refetch()} />;
  if (query.data === undefined) return <ErrorState error={new Error("No data returned.")} title={errorTitle} />;
  if (isEmpty?.(query.data) && empty) return <>{empty}</>;
  return <>{children(query.data)}</>;
}
