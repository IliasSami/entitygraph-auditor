import * as React from "react";
import { cn } from "@/lib/format";

type Variant = "default" | "secondary" | "outline" | "success" | "warning" | "destructive" | "info" | "sample";

const VARIANT_CLASSES: Record<Variant, string> = {
  default: "bg-primary/10 text-primary border-primary/30",
  secondary: "bg-secondary text-secondary-foreground border-transparent",
  outline: "bg-card text-foreground border-border",
  success: "bg-success/10 text-success border-success/30",
  warning: "bg-warning/10 text-warning border-warning/30",
  destructive: "bg-destructive/10 text-destructive border-destructive/30",
  info: "bg-info/10 text-info border-info/30",
  sample: "bg-accent text-accent-foreground border-accent-foreground/20",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

/** Status badges always pair colour with an icon/short text — never colour alone. */
export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap",
        VARIANT_CLASSES[variant],
        className,
      )}
      {...props}
    />
  );
}
