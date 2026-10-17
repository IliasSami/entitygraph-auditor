"use client";

import * as React from "react";
import { cn } from "@/lib/format";

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

/** Lightweight tooltip: shows on hover and keyboard focus (never the only source of info). */
export function Tooltip({ content, children, className }: TooltipProps) {
  const [visible, setVisible] = React.useState(false);
  return (
    <span
      className={cn("relative inline-flex", className)}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible ? (
        <span
          role="tooltip"
          className="absolute bottom-full left-1/2 z-40 mb-1 w-56 -translate-x-1/2 rounded-md border border-border bg-foreground px-2 py-1 text-center text-xs text-background shadow"
        >
          {content}
        </span>
      ) : null}
    </span>
  );
}
