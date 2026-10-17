"use client";

import * as React from "react";
import { cn } from "@/lib/format";

export interface DrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
  title?: string;
  side?: "right" | "left";
  className?: string;
}

/** Side sheet used for detail views (score rubrics, passage spans). */
export function Drawer({ open, onOpenChange, children, title, side = "right", className }: DrawerProps) {
  const panelRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onOpenChange(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        aria-label="Close panel"
        className="absolute inset-0 bg-foreground/30"
        onClick={() => onOpenChange(false)}
        tabIndex={-1}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          "absolute top-0 flex h-full w-full max-w-md flex-col overflow-y-auto bg-card shadow-xl focus:outline-none",
          side === "right" ? "right-0 border-l border-border" : "left-0 border-r border-border",
          className,
        )}
      >
        <div className="sticky top-0 flex items-start justify-between gap-4 border-b border-border bg-card p-4">
          <h2 className="text-sm font-semibold">{title}</h2>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            aria-label="Close panel"
            className="rounded p-1 text-muted-foreground hover:bg-muted"
          >
            ✕
          </button>
        </div>
        <div className="flex-1 p-4">{children}</div>
      </div>
    </div>
  );
}
