"use client";

import * as React from "react";
import { cn } from "@/lib/format";

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  /** 0..1 when a real ratio exists. Omit when only determinate counts are known. */
  value?: number | null;
}

export function Progress({ className, value, ...props }: ProgressProps) {
  const percent = value === null || value === undefined ? null : Math.round(value * 100);
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent ?? undefined}
      aria-valuetext={percent === null ? "Progress not computable" : `${percent}% complete`}
      className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)}
      {...props}
    >
      <div
        className={cn(
          "h-full rounded-full bg-primary transition-all",
          percent === null && "animate-pulse bg-primary/50",
        )}
        style={percent === null ? undefined : { width: `${percent}%` }}
      />
    </div>
  );
}
