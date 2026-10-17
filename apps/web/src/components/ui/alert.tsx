import * as React from "react";
import { cn } from "@/lib/format";

type Variant = "default" | "info" | "warning" | "destructive" | "success";

const VARIANT_CLASSES: Record<Variant, string> = {
  default: "border-border bg-card",
  info: "border-info/30 bg-info/5",
  warning: "border-warning/40 bg-warning/5",
  destructive: "border-destructive/40 bg-destructive/5",
  success: "border-success/30 bg-success/5",
};

const ICONS: Record<Variant, string> = {
  default: "ℹ",
  info: "ℹ",
  warning: "⚠",
  destructive: "✕",
  success: "✓",
};

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: Variant;
  title?: string;
}

export function Alert({ variant = "default", title, className, children, ...props }: AlertProps) {
  return (
    <div
      role="alert"
      className={cn("flex gap-3 rounded-lg border p-3 text-sm", VARIANT_CLASSES[variant], className)}
      {...props}
    >
      <span aria-hidden="true" className="mt-0.5 select-none">
        {ICONS[variant]}
      </span>
      <div className="min-w-0">
        {title ? <p className="mb-0.5 font-semibold">{title}</p> : null}
        <div className="text-sm text-muted-foreground">{children}</div>
      </div>
    </div>
  );
}
