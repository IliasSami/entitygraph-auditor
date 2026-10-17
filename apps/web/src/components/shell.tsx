"use client";

import * as React from "react";
import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useIsFetching } from "@tanstack/react-query";
import { useWorkspace } from "@/lib/workspace-context";
import { AentioLogo } from "@/components/brand/logo";

interface NavItem {
  href: string;
  label: string;
  icon: string;
  badge?: string;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Home", icon: "home" },
  { href: "/optimizer", label: "Optimize", icon: "auto_awesome", badge: "Studio" },
  { href: "/briefs", label: "Briefs", icon: "description" },
  { href: "/projects", label: "Library", icon: "folder_open" },
  { href: "/context-packs", label: "Entity Hub", icon: "hub" },
  { href: "/compare", label: "AI Visibility", icon: "radar" },
  { href: "/audits", label: "Audits", icon: "assignment" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const fetching = useIsFetching();
  const { activeProject, projects, setActiveProjectId } = useWorkspace();
  const [collapsed, setCollapsed] = useState(false);

  const isActive = (href: string): boolean => {
    if (href === "/") return pathname === "/";
    if (href === "/optimizer") return pathname.startsWith("/optimizer");
    if (href === "/briefs") return pathname.startsWith("/briefs");
    if (href === "/projects") return pathname.startsWith("/projects");
    if (href === "/context-packs") return pathname.startsWith("/context-packs");
    if (href === "/compare") return pathname.startsWith("/compare");
    if (href === "/audits") return pathname === "/audits" || pathname.startsWith("/audits/");
    if (href === "/settings") return pathname.startsWith("/settings");
    return pathname.startsWith(href);
  };

  return (
    <div className="min-h-screen bg-background-canvas text-foreground flex flex-col font-sans">
      {/* ------------------------------------------------------------- TOPBAR */}
      <header className="fixed top-0 left-0 right-0 z-50 h-[52px] bg-background-canvas border-b border-border-hairline select-none">
        <div className="h-[52px] w-full px-4 flex items-center justify-between">
          {/* Left branding & Workspace Switcher */}
          <div className="flex items-center gap-2">
            <Link href="/" className="flex items-center hover:opacity-90 transition-opacity">
              <AentioLogo size={26} showText={true} />
            </Link>

            <div className="h-4 w-[1px] bg-border-hairline mx-1.5 hidden sm:block" />

            {/* Workspace / Client Project Picker */}
            <div className="relative flex items-center">
              <select
                value={activeProject?.project_id ?? ""}
                onChange={(e) => setActiveProjectId(e.target.value)}
                className="h-7 text-xs font-medium rounded px-2 pr-6 bg-surface border border-border-hairline text-foreground hover:bg-surface-subtle transition-colors appearance-none cursor-pointer focus:outline-none focus:ring-1 focus:ring-primary"
              >
                {projects.map((p) => (
                  <option key={p.project_id} value={p.project_id}>
                    {p.name} {p.brand ? `(${p.brand})` : ""}
                  </option>
                ))}
              </select>
              <span className="material-symbols-outlined text-[14px] text-muted-foreground absolute right-1.5 pointer-events-none">
                expand_more
              </span>
            </div>

            <div className="h-4 w-[1px] bg-border-hairline mx-1.5 hidden md:block" />

            {/* Breadcrumb Info */}
            <div className="hidden md:flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="hover:text-foreground transition-colors cursor-pointer">
                {activeProject?.industry || "Workspace"}
              </span>
              <span className="text-[11px]">/</span>
              <span className="text-foreground font-medium truncate max-w-[150px]">
                {activeProject?.central_entity || "Active Content"}
              </span>
            </div>

            <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded-full border border-border-hairline bg-surface text-muted-foreground font-code-data text-[10px]">
              Draft
            </span>
          </div>

          {/* Center Engine / Model Pill */}
          <div className="hidden lg:flex items-center gap-2">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface border border-border-hairline text-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse" />
              <span className="font-code-data text-[11px] text-muted-foreground">
                Local-first · Ollama / Deterministic
              </span>
            </div>
          </div>

          {/* Right Action Deck */}
          <div className="flex items-center gap-2">
            {/* Run Agent CTA */}
            <button
              onClick={() => router.push("/optimizer?action=agent")}
              className="h-8 px-2.5 inline-flex items-center gap-1.5 rounded bg-surface border border-border-hairline hover:bg-surface-subtle text-foreground text-xs font-medium transition-colors shadow-xs"
              type="button"
              title="Run Optimization Agent"
            >
              <span className="material-symbols-outlined text-[16px] text-primary">auto_awesome</span>
              <span className="hidden sm:inline">Run agent</span>
              <kbd className="font-code-data text-[10px] px-1 py-0.5 rounded bg-surface-subtle text-muted-foreground border border-border-hairline hidden md:inline">
                ⌘↵
              </kbd>
            </button>

            {/* Publish / Run Deep Audit Button */}
            <Link
              href="/audits/new"
              className="h-8 px-3.5 inline-flex items-center rounded bg-primary hover:bg-primary-hover text-white text-xs font-medium transition-colors shadow-xs"
            >
              + Deep Audit
            </Link>

            <div className="h-4 w-[1px] bg-border-hairline mx-1 hidden sm:block" />

            <Link
              href="/settings"
              className="w-8 h-8 rounded-full bg-surface-subtle border border-border-hairline flex items-center justify-center text-foreground hover:bg-surface transition-colors"
              title="Settings & Connectors"
            >
              <span className="material-symbols-outlined text-[18px]">settings</span>
            </Link>
          </div>
        </div>

        {/* Global Fetching Progress bar */}
        {fetching > 0 && (
          <div
            className="h-0.5 w-full bg-gradient-to-r from-indigo-500 via-primary to-cyan-500 animate-pulse"
            role="progressbar"
            aria-label="Loading data"
          />
        )}
      </header>

      {/* ------------------------------------------------------------- SIDEBAR */}
      <aside
        className={`fixed left-0 top-[52px] bottom-0 ${
          collapsed ? "w-14" : "w-[220px]"
        } bg-surface border-r border-border-hairline z-40 flex flex-col justify-between py-3 transition-all duration-200 select-none`}
      >
        <div className="flex flex-col gap-1 px-2">
          {NAV_ITEMS.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs font-medium transition-colors ${
                  active
                    ? "bg-primary-soft text-primary font-semibold shadow-xs"
                    : "text-muted-foreground hover:bg-surface-subtle hover:text-foreground"
                }`}
                title={item.label}
              >
                <span className="material-symbols-outlined text-[19px] shrink-0">{item.icon}</span>
                {!collapsed && (
                  <div className="flex items-center justify-between flex-1 truncate">
                    <span className="truncate">{item.label}</span>
                    {item.badge && (
                      <span className="px-1.5 py-0.2 rounded-full text-[9px] font-bold bg-primary/10 text-primary uppercase">
                        {item.badge}
                      </span>
                    )}
                  </div>
                )}
              </Link>
            );
          })}
        </div>

        {/* Bottom Sidebar: Settings, Collapse Toggle & Health Pill */}
        <div className="flex flex-col gap-2 px-2 border-t border-border-hairline pt-3">
          <Link
            href="/settings"
            className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs font-medium transition-colors ${
              isActive("/settings")
                ? "bg-primary-soft text-primary font-semibold"
                : "text-muted-foreground hover:bg-surface-subtle hover:text-foreground"
            }`}
            title="Settings & Connectors"
          >
            <span className="material-symbols-outlined text-[19px] shrink-0">tune</span>
            {!collapsed && <span>Settings</span>}
          </Link>

          {!collapsed ? (
            <div className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-surface-subtle text-[11px] text-muted-foreground font-code-data">
              <span className="flex items-center gap-1.5 truncate">
                <span className="w-2 h-2 rounded-full bg-emerald-600 shrink-0" />
                <span className="truncate">Self-hosted · healthy</span>
              </span>
              <button
                onClick={() => setCollapsed(true)}
                className="hover:text-foreground p-0.5 rounded transition"
                title="Collapse Sidebar"
              >
                <span className="material-symbols-outlined text-[14px]">chevron_left</span>
              </button>
            </div>
          ) : (
            <button
              onClick={() => setCollapsed(false)}
              className="w-full flex items-center justify-center py-1.5 text-muted-foreground hover:text-foreground transition"
              title="Expand Sidebar"
            >
              <span className="material-symbols-outlined text-[16px]">chevron_right</span>
            </button>
          )}
        </div>
      </aside>

      {/* ------------------------------------------------------------- MAIN VIEWPORT */}
      <main
        className={`w-full pt-[52px] ${
          collapsed ? "pl-14" : "pl-[220px]"
        } min-h-screen bg-background-canvas transition-all duration-200 flex flex-col`}
      >
        <div className="flex-1 w-full">{children}</div>
      </main>
    </div>
  );
}
