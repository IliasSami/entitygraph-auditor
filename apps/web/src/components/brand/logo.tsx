"use client";

import * as React from "react";
import { useBrand, type LogoVariantId } from "./brand-context";

export interface LogoProps extends React.SVGProps<SVGSVGElement> {
  size?: number;
  className?: string;
  showText?: boolean;
  variant?: LogoVariantId;
}

/** Official Aentio Emblem & Wordmark (Calm Technical Craft) */
export function AentioLogo({
  size = 28,
  className = "",
  showText = true,
  variant,
  ...props
}: LogoProps) {
  const brand = useBrand();
  const effectiveVariant = variant || brand.logoVariant || "node";

  return (
    <div className={`inline-flex items-center gap-2.5 font-sans ${className}`}>
      {/* Aentio Token Emblem */}
      <div
        style={{ width: size, height: size }}
        className="rounded-lg bg-primary flex items-center justify-center text-white shrink-0 shadow-xs transition-colors"
      >
        <svg
          width={Math.round(size * 0.65)}
          height={Math.round(size * 0.65)}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          {...props}
        >
          {effectiveVariant === "node" && (
            <>
              {/* Central Knowledge Node & Connections */}
              <circle cx="12" cy="12" r="3" fill="currentColor" />
              <path d="M12 3v6M12 15v6M3 12h6M15 12h6" />
              <circle cx="12" cy="3" r="1.5" />
              <circle cx="12" cy="21" r="1.5" />
              <circle cx="3" cy="12" r="1.5" />
              <circle cx="21" cy="12" r="1.5" />
            </>
          )}

          {effectiveVariant === "prism" && (
            <>
              {/* Prismatic Ray & Angle Refraction */}
              <polygon points="12 2 22 19 2 19" strokeWidth="2" />
              <line x1="2" y1="13" x2="8.5" y2="13" strokeWidth="1.8" />
              <line x1="12" y1="9" x2="22" y2="11" strokeWidth="1.8" />
              <line x1="13" y1="11" x2="21" y2="15" strokeWidth="1.8" />
              <circle cx="12" cy="13" r="1.5" fill="currentColor" />
            </>
          )}

          {effectiveVariant === "shield" && (
            <>
              {/* Verified Knowledge Shield */}
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" strokeWidth="2" />
              <path d="m9 12 2 2 4-4" strokeWidth="2.2" />
            </>
          )}
        </svg>
      </div>

      {showText && (
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5 leading-none">
            <span className="text-[17px] font-bold tracking-tight text-foreground font-sans">
              Aentio
            </span>
            <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold text-primary uppercase tracking-wider transition-colors">
              Optimizer
            </span>
          </div>
          <span className="text-[10px] font-medium tracking-tight text-muted-foreground mt-0.5">
            AI Search &amp; Entity Studio
          </span>
        </div>
      )}
    </div>
  );
}

/** Backwards-compatible alias */
export const EntityGraphLogo = AentioLogo;
