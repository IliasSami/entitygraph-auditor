"use client";

import * as React from "react";
import { createContext, useContext, useEffect, useState } from "react";

export type BrandThemeId = "indigo" | "emerald" | "amber" | "obsidian";
export type LogoVariantId = "node" | "prism" | "shield";

export interface BrandThemeConfig {
  id: BrandThemeId;
  name: string;
  tagline: string;
  primary: string;
  primarySoft: string;
  primaryHover: string;
  ring: string;
  swatch: string;
}

export const BRAND_THEMES: Record<BrandThemeId, BrandThemeConfig> = {
  indigo: {
    id: "indigo",
    name: "Aentio Indigo",
    tagline: "Calm Technical Craft · Deep Indigo & Stone",
    primary: "#4338ca",
    primarySoft: "#eef2ff",
    primaryHover: "#3730a3",
    ring: "#4338ca",
    swatch: "bg-indigo-700",
  },
  emerald: {
    id: "emerald",
    name: "Emerald Retrieval",
    tagline: "Generative Engine & AEO Visibility Focus",
    primary: "#059669",
    primarySoft: "#ecfdf5",
    primaryHover: "#047857",
    ring: "#059669",
    swatch: "bg-emerald-600",
  },
  amber: {
    id: "amber",
    name: "Amber Editorial",
    tagline: "Topic Architecture & Content Optimization",
    primary: "#d97706",
    primarySoft: "#fffbeb",
    primaryHover: "#b45309",
    ring: "#d97706",
    swatch: "bg-amber-600",
  },
  obsidian: {
    id: "obsidian",
    name: "Obsidian Enterprise",
    tagline: "High-Density Technical Intelligence",
    primary: "#0f172a",
    primarySoft: "#f1f5f9",
    primaryHover: "#020617",
    ring: "#0f172a",
    swatch: "bg-slate-900",
  },
};

export interface LogoVariantConfig {
  id: LogoVariantId;
  name: string;
  description: string;
}

export const LOGO_VARIANTS: Record<LogoVariantId, LogoVariantConfig> = {
  node: {
    id: "node",
    name: "Knowledge Node",
    description: "Central entity anchor connected to semantic predicate satellites",
  },
  prism: {
    id: "prism",
    name: "Prismatic Beam",
    description: "Multi-angle refractive geometry for AI search citation fan-out",
  },
  shield: {
    id: "shield",
    name: "Entity Shield",
    description: "Publication gate verification & proof-point integrity",
  },
};

interface BrandContextType {
  themeId: BrandThemeId;
  setThemeId: (id: BrandThemeId) => void;
  logoVariant: LogoVariantId;
  setLogoVariant: (variant: LogoVariantId) => void;
  activeTheme: BrandThemeConfig;
}

const BrandContext = createContext<BrandContextType | null>(null);

const THEME_STORAGE_KEY = "aentio_brand_theme";
const LOGO_STORAGE_KEY = "aentio_logo_variant";

export function BrandProvider({ children }: { children: React.ReactNode }) {
  const [themeId, setThemeIdState] = useState<BrandThemeId>(() => {
    if (typeof window === "undefined") return "indigo";
    try {
      const storedTheme = localStorage.getItem(THEME_STORAGE_KEY) as BrandThemeId | null;
      if (storedTheme && BRAND_THEMES[storedTheme]) return storedTheme;
    } catch {
      // LocalStorage unavailable
    }
    return "indigo";
  });

  const [logoVariant, setLogoVariantState] = useState<LogoVariantId>(() => {
    if (typeof window === "undefined") return "node";
    try {
      const storedLogo = localStorage.getItem(LOGO_STORAGE_KEY) as LogoVariantId | null;
      if (storedLogo && LOGO_VARIANTS[storedLogo]) return storedLogo;
    } catch {
      // LocalStorage unavailable
    }
    return "node";
  });

  // Apply theme CSS variables to document root
  useEffect(() => {
    const config = BRAND_THEMES[themeId] || BRAND_THEMES.indigo;
    const root = document.documentElement;

    root.style.setProperty("--primary", config.primary);
    root.style.setProperty("--ring", config.ring);
    root.style.setProperty("--accent-foreground", config.primary);
  }, [themeId]);

  const setThemeId = (id: BrandThemeId) => {
    setThemeIdState(id);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, id);
    } catch {
      // LocalStorage unavailable
    }
  };

  const setLogoVariant = (variant: LogoVariantId) => {
    setLogoVariantState(variant);
    try {
      localStorage.setItem(LOGO_STORAGE_KEY, variant);
    } catch {
      // LocalStorage unavailable
    }
  };

  const activeTheme = BRAND_THEMES[themeId] || BRAND_THEMES.indigo;

  return (
    <BrandContext.Provider
      value={{
        themeId,
        setThemeId,
        logoVariant,
        setLogoVariant,
        activeTheme,
      }}
    >
      {children}
    </BrandContext.Provider>
  );
}

export function useBrand() {
  const ctx = useContext(BrandContext);
  if (!ctx) {
    return {
      themeId: "indigo" as BrandThemeId,
      setThemeId: () => {},
      logoVariant: "node" as LogoVariantId,
      setLogoVariant: () => {},
      activeTheme: BRAND_THEMES.indigo,
    };
  }
  return ctx;
}
