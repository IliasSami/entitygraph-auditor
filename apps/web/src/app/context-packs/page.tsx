"use client";

import * as React from "react";
import { useState, useMemo } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { WorkspaceEntity } from "@/lib/types";
import { useWorkspace } from "@/lib/workspace-context";

interface EntityItem {
  id: string;
  canonicalId: string;
  name: string;
  type: "Organization" | "Service" | "Person" | "Place" | "Concept" | "Platform";
  aliases: string[];
  pagesUsed: number;
  factsCount: number;
  lastVerified: string;
  status: "healthy" | "conflict" | "needs_review";
  conflictDetail?: string;
  definition: string;
  atId: string;
  schemaType: string;
  facts: Array<{
    property: string;
    value: string;
    source: string;
    date: string;
    verified: boolean;
  }>;
  sources: Array<{ title: string; url: string }>;
}

const ENTITY_TYPES: EntityItem["type"][] = [
  "Organization",
  "Service",
  "Person",
  "Place",
  "Concept",
  "Platform",
];

/** Map a backend workspace entity (provenance-labelled) into the UI shape. */
function mapEntity(entity: WorkspaceEntity): EntityItem {
  const type = (ENTITY_TYPES as string[]).includes(entity.kind)
    ? (entity.kind as EntityItem["type"])
    : "Concept";
  return {
    id: entity.entity_id,
    canonicalId: entity.canonical_id,
    name: entity.name,
    type,
    aliases: entity.aliases,
    pagesUsed: entity.pages_used,
    factsCount: entity.facts_count,
    lastVerified: entity.last_verified ?? "Not yet verified",
    status: entity.status,
    conflictDetail: entity.conflict_detail ?? undefined,
    definition: entity.definition,
    atId: entity.at_id,
    schemaType: entity.schema_type,
    facts: entity.facts.map((f) => ({
      property: f.property,
      value: f.value,
      source: f.source,
      date: f.date ?? "—",
      verified: f.verified,
    })),
    sources: entity.sources.map((s) => ({ title: s.title, url: s.url ?? "" })),
  };
}

export default function EntityHubPage() {
  const queryClient = useQueryClient();
  const { activeProject } = useWorkspace();
  const projectId = activeProject?.project_id ?? null;

  const [localEntities, setLocalEntities] = useState<EntityItem[]>([]);
  const [localFacts, setLocalFacts] = useState<Record<string, EntityItem["facts"]>>({});
  const [selectedEntityId, setSelectedEntityId] = useState<string>("");
  const [selectedFilter, setSelectedFilter] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"list" | "graph">("list");
  const [showAddModal, setShowAddModal] = useState(false);
  const [showAddFactModal, setShowAddFactModal] = useState(false);
  const [newFact, setNewFact] = useState({ property: "", value: "", source: "Manual Verification" });
  const [copiedId, setCopiedId] = useState(false);
  const [copyNotice, setCopyNotice] = useState("");
  const [bulkVerifyNotice, setBulkVerifyNotice] = useState("");
  const [entityNotice, setEntityNotice] = useState("");
  const [newEntity, setNewEntity] = useState({
    name: "",
    type: "Organization" as EntityItem["type"],
    canonicalId: "",
    definition: "",
  });

  // Live context packs query from backend
  const packsQuery = useQuery({
    queryKey: ["context-packs"],
    queryFn: () => api.listContextPacks(),
  });

  // Live entity registry derived from this project's stored audits + packs.
  const entitiesQuery = useQuery({
    queryKey: ["workspace-entities", projectId],
    queryFn: () => api.listEntities(projectId as string),
    enabled: !!projectId,
  });

  // Backend entities merged with session-only local additions.
  const entities = useMemo<EntityItem[]>(() => {
    const base = (entitiesQuery.data?.entities ?? []).map(mapEntity);
    const merged = [...base, ...localEntities];
    return merged.map((e) =>
      localFacts[e.id]
        ? {
            ...e,
            facts: [...e.facts, ...localFacts[e.id]],
            factsCount: e.factsCount + localFacts[e.id].length,
          }
        : e,
    );
  }, [entitiesQuery.data, localEntities, localFacts]);

  const selectedEntity = useMemo(
    () => entities.find((e) => e.id === selectedEntityId) ?? entities[0],
    [entities, selectedEntityId]
  );

  const conflictCount = useMemo(
    () => entities.filter((e) => e.status === "conflict").length,
    [entities],
  );

  const filteredEntities = useMemo(() => {
    return entities.filter((e) => {
      const matchesFilter = selectedFilter === "All" || e.type === selectedFilter;
      const matchesSearch =
        !searchQuery ||
        e.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        e.canonicalId.toLowerCase().includes(searchQuery.toLowerCase()) ||
        e.aliases.some((a) => a.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchesFilter && matchesSearch;
    });
  }, [entities, selectedFilter, searchQuery]);

  const filterCounts = useMemo(() => {
    const counts: Record<string, number> = { All: entities.length };
    for (const e of entities) {
      counts[e.type] = (counts[e.type] || 0) + 1;
    }
    return counts;
  }, [entities]);

  const handleCopyJsonLd = () => {
    if (!selectedEntity) return;
    const jsonLd = {
      "@context": "https://schema.org",
      "@type": selectedEntity.schemaType.replace("schema.org/", ""),
      "@id": selectedEntity.atId,
      name: selectedEntity.name,
      alternateName: selectedEntity.aliases,
      description: selectedEntity.definition,
      additionalProperty: selectedEntity.facts.map((f) => ({
        "@type": "PropertyValue",
        name: f.property,
        value: f.value,
      })),
    };
    navigator.clipboard.writeText(JSON.stringify(jsonLd, null, 2));
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const handleAddFact = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFact.property || !newFact.value || !selectedEntity) return;
    const added = {
      property: newFact.property,
      value: newFact.value,
      source: newFact.source || "Manual Verification",
      date: "Today",
      verified: true,
    };
    setLocalFacts((prev) => ({
      ...prev,
      [selectedEntity.id]: [...(prev[selectedEntity.id] ?? []), added],
    }));

    const targetPackId = activeProject?.context_pack_ids?.[0] || packsQuery.data?.[0]?.pack_id;
    if (targetPackId) {
      void api
        .addPackFact(targetPackId, {
          property: newFact.property,
          value: newFact.value,
          source: newFact.source || "Manual Verification",
        })
        .then(() => {
          void queryClient.invalidateQueries({ queryKey: ["context-packs"] });
          void queryClient.invalidateQueries({ queryKey: ["workspace-entities"] });
        })
        .catch(() => {});
    }

    setNewFact({ property: "", value: "", source: "Manual Verification" });
    setShowAddFactModal(false);
  };

  const handleCopyAtId = async () => {
    if (!selectedEntity) return;
    try {
      await navigator.clipboard.writeText(selectedEntity.atId);
      setCopyNotice("Copied canonical @id");
    } catch {
      setCopyNotice("Copy failed — copy the @id manually.");
    }
    setTimeout(() => setCopyNotice(""), 3000);
  };

  const handleAddEntity = (e: React.FormEvent) => {
    e.preventDefault();
    const name = newEntity.name.trim();
    const canonicalId = newEntity.canonicalId.trim();
    if (!name || !canonicalId) return;
    const slug = canonicalId.startsWith("#") ? canonicalId : `#${canonicalId}`;
    const created: EntityItem = {
      id: `ent-local-${Date.now()}`,
      canonicalId: slug,
      name,
      type: newEntity.type,
      aliases: [],
      pagesUsed: 0,
      factsCount: 0,
      lastVerified: "Today",
      status: "healthy",
      definition: newEntity.definition.trim() || `Canonical definition for ${name}.`,
      atId: `https://example.com/${slug.replace(/^#/, "")}`,
      schemaType: "schema.org/Thing",
      facts: [],
      sources: [],
    };
    setLocalEntities((prev) => [created, ...prev]);
    setSelectedEntityId(created.id);

    const targetPackId = activeProject?.context_pack_ids?.[0] || packsQuery.data?.[0]?.pack_id;
    if (targetPackId) {
      void api
        .addPackEntity(targetPackId, {
          name: created.name,
          type: created.type,
          definition: created.definition,
          canonical_id: created.canonicalId,
        })
        .then(() => {
          void queryClient.invalidateQueries({ queryKey: ["context-packs"] });
          void queryClient.invalidateQueries({ queryKey: ["workspace-entities"] });
        })
        .catch(() => {});
      setEntityNotice(`Entity "${created.name}" created and synced to active context pack.`);
    } else {
      setEntityNotice(`Entity "${created.name}" added as local draft.`);
    }

    setTimeout(() => setEntityNotice(""), 5000);
    setNewEntity({ name: "", type: "Organization", canonicalId: "", definition: "" });
    setShowAddModal(false);
  };

  return (
    <div className="flex flex-col w-full min-h-[calc(100vh-52px)] bg-background-canvas">
      {/* ------------------------------------------------------------- TOP COMMAND TOOLBAR */}
      <div className="px-6 py-3.5 bg-surface border-b border-border-hairline select-none">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-sans text-xl font-bold tracking-tight text-foreground">
                Entity Hub
              </h1>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-code-data bg-primary-soft text-primary font-medium">
                entity registry
              </span>
              {packsQuery.data && packsQuery.data.length > 0 && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-code-data bg-surface-subtle text-muted-foreground border border-border-hairline">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                  {packsQuery.data.length} active pack{packsQuery.data.length > 1 ? "s" : ""}
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Business knowledge graph · Canonical source of truth for claims, facts, and structured schema
            </p>
          </div>

          {/* Controls & Actions */}
          <div className="flex flex-wrap items-center gap-2">
            {/* View Switcher */}
            <div className="inline-flex items-center p-0.5 rounded-lg bg-surface-subtle border border-border-hairline">
              <button
                type="button"
                onClick={() => setViewMode("list")}
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-all ${
                  viewMode === "list"
                    ? "bg-surface text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <span className="material-symbols-outlined text-[15px]">format_list_bulleted</span>
                <span>List</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode("graph")}
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-all ${
                  viewMode === "graph"
                    ? "bg-surface text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <span className="material-symbols-outlined text-[15px]">account_tree</span>
                <span>Graph</span>
              </button>
            </div>

            {/* Quick Search */}
            <div className="relative flex items-center min-w-[240px]">
              <span className="material-symbols-outlined absolute left-2.5 text-muted-foreground text-[16px]">
                search
              </span>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search entities, facts, aliases..."
                className="w-full h-8 pl-8 pr-10 rounded-lg bg-surface-subtle border border-border-hairline text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:bg-surface transition-colors"
              />
              <span className="absolute right-2 px-1.5 py-0.5 rounded bg-surface border border-border-hairline text-[10px] font-code-data text-muted-foreground pointer-events-none">
                ⌘K
              </span>
            </div>

            {/* Export JSON-LD */}
            <button
              type="button"
              onClick={handleCopyJsonLd}
              className="h-8 px-3 rounded-lg bg-surface hover:bg-surface-subtle border border-border-hairline text-foreground text-xs font-medium inline-flex items-center gap-1.5 transition-colors"
              title="Copy JSON-LD of active entity"
            >
              <span className="material-symbols-outlined text-[15px] text-muted-foreground">
                {copiedId ? "check" : "code"}
              </span>
              <span>{copiedId ? "Copied!" : "Export JSON-LD"}</span>
            </button>

            {/* Add Entity Button */}
            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              className="h-8 px-3 rounded-lg bg-primary hover:bg-primary-hover text-white text-xs font-medium inline-flex items-center gap-1.5 shadow-xs transition-colors"
            >
              <span className="material-symbols-outlined text-[16px]">add</span>
              <span>Add entity</span>
            </button>
          </div>
        </div>

        {/* Filter Pills Row */}
        <div className="flex items-center gap-1.5 mt-3 overflow-x-auto pb-0.5 text-xs">
          {["All", "Organization", "Service", "Person", "Place", "Concept", "Platform"].map((tab) => {
            const count = filterCounts[tab] ?? 0;
            const active = selectedFilter === tab;
            return (
              <button
                key={tab}
                type="button"
                onClick={() => setSelectedFilter(tab)}
                className={`px-2.5 py-1 rounded-full font-medium transition-colors whitespace-nowrap ${
                  active
                    ? "bg-foreground text-background-canvas"
                    : "bg-surface-subtle hover:bg-surface border border-border-hairline text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab} ({count})
              </button>
            );
          })}
          <div className="ml-auto hidden sm:flex items-center gap-1.5 text-muted-foreground text-xs">
            <span className="material-symbols-outlined text-[15px]">tune</span>
            <span>Filters</span>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------- MAIN WORKSPACE (TABLE + SLIDE DRAWER) */}
      <div className="flex flex-col lg:flex-row flex-1 overflow-hidden min-h-[calc(100vh-140px)]">
        {/* Left / Center Main Entity Table Workspace */}
        <div className="flex-1 flex flex-col min-w-0 bg-background-canvas border-r border-border-hairline">
          {/* Table Header Bar */}
          <div className="px-4 py-2 flex items-center justify-between border-b border-border-hairline bg-surface/60 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                defaultChecked
                className="rounded border-border-hairline w-3.5 h-3.5 text-primary focus:ring-0"
              />
              <span>Selected 1 item</span>
              <span className="text-border-hairline">|</span>
              <button
                type="button"
                className="hover:text-foreground text-primary font-medium"
                onClick={() => {
                  setBulkVerifyNotice(
                    "Bulk re-verify requires a configured verifier provider — no facts were changed."
                  );
                  setTimeout(() => setBulkVerifyNotice(""), 5000);
                }}
              >
                Bulk re-verify
              </button>
              {bulkVerifyNotice && (
                <span className="text-[11px] text-amber-700 font-medium" role="status">
                  {bulkVerifyNotice}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 font-code-data text-[11px]">
              <span>Sorted by Canonical ID</span>
              <span className="material-symbols-outlined text-[14px]">swap_vert</span>
            </div>
          </div>

          {/* Table View */}
          {viewMode === "list" ? (
            <div className="overflow-x-auto flex-1 bg-surface">
              <table className="w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="h-9 border-b border-border-hairline bg-surface-subtle/80 text-muted-foreground font-medium uppercase tracking-wider text-[11px]">
                    <th className="w-9 px-3 py-2 text-center">
                      <input type="checkbox" className="rounded border-border-hairline w-3.5 h-3.5 text-primary" />
                    </th>
                    <th className="px-3 py-2 font-medium">Name & Canonical ID</th>
                    <th className="px-3 py-2 font-medium">Type</th>
                    <th className="px-3 py-2 font-medium">Used on</th>
                    <th className="px-3 py-2 font-medium">Verified Facts</th>
                    <th className="px-3 py-2 font-medium">Last Verified</th>
                    <th className="px-3 py-2 font-medium">Health / Status</th>
                    <th className="w-10 px-3 py-2 text-right" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-hairline text-foreground">
                  {filteredEntities.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center text-sm text-muted-foreground">
                        {!projectId
                          ? "Select a project to view its entity registry."
                          : entitiesQuery.isLoading
                            ? "Loading entity registry…"
                            : "No entities yet — run an audit to populate the knowledge registry."}
                      </td>
                    </tr>
                  )}
                  {filteredEntities.map((entity) => {
                    const isSelected = entity.id === selectedEntity?.id;
                    return (
                      <tr
                        key={entity.id}
                        onClick={() => setSelectedEntityId(entity.id)}
                        className={`h-11 transition-colors cursor-pointer group ${
                          isSelected
                            ? "bg-primary-soft/50 border-l-4 border-l-primary"
                            : "hover:bg-surface-subtle"
                        }`}
                      >
                        <td className="px-3 py-2 text-center" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => setSelectedEntityId(entity.id)}
                            className="rounded border-border-hairline w-3.5 h-3.5 text-primary"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={`material-symbols-outlined text-[16px] ${
                                isSelected ? "text-primary" : "text-muted-foreground"
                              }`}
                            >
                              {entity.type === "Organization"
                                ? "domain"
                                : entity.type === "Service"
                                ? "hub"
                                : entity.type === "Person"
                                ? "person"
                                : entity.type === "Place"
                                ? "location_on"
                                : "extension"}
                            </span>
                            <div className="flex flex-col">
                              <span
                                className={`font-medium ${
                                  isSelected ? "text-primary font-semibold" : "text-foreground"
                                }`}
                              >
                                {entity.name}
                              </span>
                              <span className="font-code-data text-[10px] text-muted-foreground">
                                {entity.canonicalId} · {entity.aliases.length} alias
                                {entity.aliases.length === 1 ? "" : "es"}
                              </span>
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface-subtle text-foreground border border-border-hairline">
                            {entity.type}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-1 text-muted-foreground">
                            <span className="font-code-data">{entity.pagesUsed} pages</span>
                            <span className="material-symbols-outlined text-[13px]">open_in_new</span>
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <span className="font-code-data font-medium">{entity.factsCount} facts</span>
                        </td>
                        <td className="px-3 py-2 font-code-data text-muted-foreground text-[11px]">
                          {entity.lastVerified}
                        </td>
                        <td className="px-3 py-2">
                          {entity.status === "healthy" ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-800 border border-emerald-200">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                              Healthy
                            </span>
                          ) : entity.status === "needs_review" ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 text-amber-800 border border-amber-200">
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
                              Draft · local
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-rose-50 text-rose-800 border border-rose-200">
                              <span className="w-1.5 h-1.5 rounded-full bg-rose-600" />
                              Conflict (1)
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <button
                            type="button"
                            className="text-muted-foreground hover:text-foreground p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <span className="material-symbols-outlined text-[15px]">more_horiz</span>
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            /* Graph View Visualizer */
            <div className="flex-1 p-6 flex flex-col items-center justify-center bg-surface-subtle/30">
              <div className="max-w-md text-center p-6 bg-surface rounded-xl border border-border-hairline shadow-xs">
                <span className="material-symbols-outlined text-4xl text-primary mb-2">account_tree</span>
                <h3 className="text-base font-semibold text-foreground mb-1">Knowledge Graph Visualization</h3>
                <p className="text-xs text-muted-foreground mb-4">
                  Visual node linkage mapping across {entities.length} entities and{" "}
                  {entities.reduce((acc, e) => acc + e.factsCount, 0)} verified properties in this workspace.
                </p>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  {entities.map((e) => (
                    <span
                      key={e.id}
                      onClick={() => {
                        setSelectedEntityId(e.id);
                        setViewMode("list");
                      }}
                      className="px-2.5 py-1 rounded-full bg-surface-subtle border border-border-hairline text-xs font-code-data hover:border-primary cursor-pointer transition-colors"
                    >
                      {e.name}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Table Footer Status Ribbon */}
          <div className="px-4 py-2.5 bg-surface border-t border-border-hairline flex flex-wrap items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <span>Showing {filteredEntities.length} of {entities.length} entities</span>
              <span className="w-1 h-1 rounded-full bg-border-hairline" />
              {conflictCount > 0 ? (
                <span className="text-rose-700 font-medium">
                  {conflictCount} entit{conflictCount === 1 ? "y" : "ies"} with conflicting facts
                </span>
              ) : (
                <span className="text-emerald-700 font-medium">No conflicts detected</span>
              )}
              <span className="w-1 h-1 rounded-full bg-border-hairline" />
              <span>Facts sourced from stored audits &amp; context packs</span>
            </div>
            <div className="flex items-center gap-2 font-code-data text-[11px]">
              <span className="text-emerald-700">
                ● {entitiesQuery.isFetching ? "syncing" : "ready"}
              </span>
              {entitiesQuery.data && (
                <span>
                  {entitiesQuery.data.source_audits} audit{entitiesQuery.data.source_audits === 1 ? "" : "s"} ·{" "}
                  {entitiesQuery.data.source_packs} pack{entitiesQuery.data.source_packs === 1 ? "" : "s"}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* ------------------------------------------------------------- RIGHT DETAIL DRAWER (440px) */}
        {selectedEntity && (
        <aside className="w-full lg:w-[440px] shrink-0 bg-surface flex flex-col h-full shadow-xs">
          {/* Drawer Header */}
          <div className="p-4 border-b border-border-hairline bg-surface">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2 truncate">
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-primary-soft text-primary uppercase tracking-wider font-code-data">
                  {selectedEntity.type}
                </span>
                <span className="text-muted-foreground text-xs">/</span>
                <span className="font-code-data text-xs text-muted-foreground truncate">
                  Entities / {selectedEntity.name}
                </span>
              </div>
            </div>

            <h2 className="text-lg font-bold text-foreground tracking-tight">
              {selectedEntity.name}
            </h2>

            {/* Aliases Chips */}
            <div className="flex flex-wrap items-center gap-1.5 mt-2">
              <span className="text-muted-foreground text-xs font-medium">Aliases:</span>
              {selectedEntity.aliases.map((alias) => (
                <span
                  key={alias}
                  className="px-2 py-0.5 rounded-full bg-surface-subtle border border-border-hairline font-code-data text-[10px] text-foreground"
                >
                  {alias}
                </span>
              ))}
            </div>

            {/* Canonical Definition Card */}
            <div className="mt-3 p-2.5 rounded-lg bg-surface-subtle/70 border border-border-hairline">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider">
                  Canonical Entity Definition
                </span>
                <span className="text-[10px] font-code-data text-muted-foreground bg-surface px-1.5 py-0.2 rounded border border-border-hairline">
                  {selectedEntity.definition.length} / 160
                </span>
              </div>
              <p className="font-serif italic text-xs leading-relaxed text-foreground">
                &ldquo;{selectedEntity.definition}&rdquo;
              </p>
            </div>

            {/* Web Identifiers & schema specs */}
            <div className="mt-3 space-y-1.5">
              <div className="flex items-center justify-between text-xs bg-surface-subtle px-2.5 py-1.5 rounded border border-border-hairline">
                <div className="flex items-center gap-1.5 truncate">
                  <span className="font-code-data text-muted-foreground text-[10px]">@id:</span>
                  <span className="font-code-data text-primary text-[11px] truncate">
                    {selectedEntity.atId}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleCopyAtId}
                  className="text-muted-foreground hover:text-foreground ml-2 shrink-0"
                  title="Copy URI"
                >
                  <span className="material-symbols-outlined text-[14px]">content_copy</span>
                </button>
              </div>

              {copyNotice && (
                <p className="text-[10px] text-emerald-700 font-medium" role="status">
                  {copyNotice}
                </p>
              )}

              <div className="flex items-center justify-between text-xs pt-0.5">
                <div className="flex items-center gap-1 text-muted-foreground">
                  <span>Schema Type:</span>
                  <span className="font-code-data text-foreground bg-surface-subtle px-1.5 py-0.5 rounded text-[10px] border border-border-hairline">
                    {selectedEntity.schemaType}
                  </span>
                </div>
                <div className="flex items-center gap-1 text-primary text-[11px] font-medium">
                  <span className="hover:underline cursor-pointer">Wikidata</span>
                  <span>·</span>
                  <span className="hover:underline cursor-pointer">LinkedIn</span>
                  <span>·</span>
                  <span className="hover:underline cursor-pointer">Google</span>
                </div>
              </div>
            </div>
          </div>

          {/* Drawer Scrollable Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* 1. Usage & Health Alert Card (Conflict Warning if active) */}
            {selectedEntity.status === "conflict" && selectedEntity.conflictDetail && (
              <div className="rounded-xl border border-rose-200 bg-rose-50/70 p-3 flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-rose-700 text-white text-[10px] font-semibold tracking-wide">
                    <span className="material-symbols-outlined text-[12px]">warning</span>
                    <span>Conflicting facts detected</span>
                  </div>
                  <span className="font-code-data text-[10px] text-rose-800 font-semibold">
                    Severity: High
                  </span>
                </div>
                <p className="text-xs text-foreground leading-relaxed">
                  {selectedEntity.conflictDetail}
                </p>
                <div className="pt-1 flex items-center justify-end">
                  <Link
                    href="/optimizer?action=resolve-conflict"
                    className="h-7 px-2.5 rounded bg-surface hover:bg-surface-subtle text-rose-700 border border-rose-300 text-xs font-semibold inline-flex items-center gap-1 transition-colors shadow-xs"
                  >
                    <span>Resolve conflict in Optimizer</span>
                    <span className="material-symbols-outlined text-[13px]">arrow_forward</span>
                  </Link>
                </div>
              </div>
            )}

            {/* 2. Verified Facts Ledger */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5">
                  <h3 className="text-xs font-bold text-foreground uppercase tracking-wider">
                    Verified Facts
                  </h3>
                  <span className="px-1.5 py-0.2 rounded-full text-[10px] font-code-data bg-surface-subtle text-muted-foreground border border-border-hairline">
                    {selectedEntity.facts.length}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowAddFactModal(true)}
                  className="text-primary hover:text-primary-hover text-xs font-medium inline-flex items-center gap-0.5"
                >
                  <span className="material-symbols-outlined text-[13px]">add</span>
                  <span>Add fact</span>
                </button>
              </div>

              <div className="rounded-lg border border-border-hairline overflow-hidden bg-surface">
                <table className="w-full text-left text-xs">
                  <thead className="bg-surface-subtle text-muted-foreground font-medium border-b border-border-hairline text-[10px] uppercase">
                    <tr>
                      <th className="p-2 font-medium">Fact Property</th>
                      <th className="p-2 font-medium">Ground Truth</th>
                      <th className="p-2 font-medium text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-hairline">
                    {selectedEntity.facts.map((fact, idx) => (
                      <tr key={idx} className="hover:bg-surface-subtle/50">
                        <td className="p-2 align-top">
                          <span className="font-medium text-foreground block">{fact.property}</span>
                          <span className="text-[10px] text-muted-foreground">{fact.source}</span>
                        </td>
                        <td className="p-2 align-top">
                          <span className="font-code-data font-semibold text-foreground text-[11px]">
                            {fact.value}
                          </span>
                          <span className="block text-[10px] text-muted-foreground">{fact.date}</span>
                        </td>
                        <td className="p-2 text-right align-top">
                          <span className="inline-flex items-center text-emerald-800 font-medium gap-0.5 text-[10px] bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
                            <span className="material-symbols-outlined text-[12px]">verified</span>
                            <span>Verified</span>
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 3. Provenance & Source Anchors */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <h3 className="text-xs font-bold text-foreground uppercase tracking-wider">
                  Provenance & Grounding Sources
                </h3>
                <span className="text-[10px] font-code-data text-muted-foreground">
                  {selectedEntity.sources.length} sources
                </span>
              </div>
              <div className="space-y-1.5">
                {selectedEntity.sources.map((src, idx) => (
                  <div
                    key={idx}
                    className="p-2 rounded-lg bg-surface-subtle border border-border-hairline flex items-center justify-between text-xs"
                  >
                    <div className="flex flex-col min-w-0 pr-2">
                      <span className="font-medium text-foreground truncate">{src.title}</span>
                      <span className="font-code-data text-[10px] text-muted-foreground truncate">
                        {src.url}
                      </span>
                    </div>
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-foreground shrink-0"
                    >
                      <span className="material-symbols-outlined text-[14px]">open_in_new</span>
                    </a>
                  </div>
                ))}
              </div>
            </div>

            {/* 4. Action Dock */}
            <div className="pt-2 border-t border-border-hairline flex items-center justify-between">
              <button
                type="button"
                onClick={handleCopyJsonLd}
                className="h-8 px-3 rounded-lg bg-surface hover:bg-surface-subtle border border-border-hairline text-foreground text-xs font-medium inline-flex items-center gap-1.5 transition-colors"
              >
                <span className="material-symbols-outlined text-[14px]">code</span>
                <span>Copy Schema JSON-LD</span>
              </button>
              <Link
                href="/optimizer"
                className="h-8 px-3 rounded-lg bg-primary hover:bg-primary-hover text-white text-xs font-medium inline-flex items-center gap-1.5 shadow-xs transition-colors"
              >
                <span>Edit in Studio</span>
                <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
              </Link>
            </div>
          </div>
        </aside>
        )}
      </div>

      {/* ------------------------------------------------------------- ADD FACT MODAL */}
      {showAddFactModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-surface rounded-xl border border-border-hairline shadow-lg max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-foreground">Add Verified Fact</h3>
              <button
                type="button"
                onClick={() => setShowAddFactModal(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <span className="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              Add a canonical truth statement for <strong className="text-foreground">{selectedEntity.name}</strong>.
              All drafts will be verified against this value.
            </p>
            <form onSubmit={handleAddFact} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-foreground mb-1">Fact Property</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Starter tier pricing, Minimum engagement"
                  value={newFact.property}
                  onChange={(e) => setNewFact({ ...newFact, property: e.target.value })}
                  className="w-full h-8 px-2.5 rounded bg-surface-subtle border border-border-hairline text-xs text-foreground focus:outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground mb-1">Ground Truth Value</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. $349/month, 4–45 team members"
                  value={newFact.value}
                  onChange={(e) => setNewFact({ ...newFact, value: e.target.value })}
                  className="w-full h-8 px-2.5 rounded bg-surface-subtle border border-border-hairline text-xs text-foreground focus:outline-none focus:border-primary font-code-data"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground mb-1">Source / Citation</label>
                <input
                  type="text"
                  placeholder="e.g. Official Pricing Page v2.4"
                  value={newFact.source}
                  onChange={(e) => setNewFact({ ...newFact, source: e.target.value })}
                  className="w-full h-8 px-2.5 rounded bg-surface-subtle border border-border-hairline text-xs text-foreground focus:outline-none focus:border-primary"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddFactModal(false)}
                  className="h-8 px-3 rounded bg-surface border border-border-hairline text-xs font-medium text-foreground hover:bg-surface-subtle"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="h-8 px-3 rounded bg-primary text-white text-xs font-medium hover:bg-primary-hover shadow-xs"
                >
                  Save Fact
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- ADD ENTITY MODAL */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-surface rounded-xl border border-border-hairline shadow-lg max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-foreground">Add New Entity</h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <span className="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              Add a brand entity or core concept as a local draft for this session.
            </p>
            <form onSubmit={handleAddEntity} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-foreground mb-1">Entity Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Job Costing Retainer"
                  value={newEntity.name}
                  onChange={(e) => setNewEntity({ ...newEntity, name: e.target.value })}
                  className="w-full h-8 px-2.5 rounded bg-surface-subtle border border-border-hairline text-xs text-foreground focus:outline-none focus:border-primary"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium text-foreground mb-1">Type</label>
                  <select
                    value={newEntity.type}
                    onChange={(e) => setNewEntity({ ...newEntity, type: e.target.value as EntityItem["type"] })}
                    className="w-full h-8 px-2 rounded bg-surface-subtle border border-border-hairline text-xs text-foreground focus:outline-none focus:border-primary"
                  >
                    <option>Organization</option>
                    <option>Service</option>
                    <option>Person</option>
                    <option>Place</option>
                    <option>Concept</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-foreground mb-1">Canonical ID</label>
                  <input
                    type="text"
                    required
                    placeholder="#job-costing-retainer"
                    value={newEntity.canonicalId}
                    onChange={(e) => setNewEntity({ ...newEntity, canonicalId: e.target.value })}
                    className="w-full h-8 px-2.5 rounded bg-surface-subtle border border-border-hairline text-xs text-foreground focus:outline-none focus:border-primary font-code-data"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground mb-1">Canonical Definition</label>
                <textarea
                  rows={2}
                  placeholder="Clear 1-2 sentence definition for answer-first extraction..."
                  value={newEntity.definition}
                  onChange={(e) => setNewEntity({ ...newEntity, definition: e.target.value })}
                  className="w-full p-2 rounded bg-surface-subtle border border-border-hairline text-xs text-foreground focus:outline-none focus:border-primary font-serif"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="h-8 px-3 rounded bg-surface border border-border-hairline text-xs font-medium text-foreground hover:bg-surface-subtle"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="h-8 px-3 rounded bg-primary text-white text-xs font-medium hover:bg-primary-hover shadow-xs"
                >
                  Create Entity
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Inline, non-blocking confirmation (local draft — nothing is persisted). */}
      {entityNotice && (
        <div
          role="status"
          className="fixed bottom-4 right-4 z-50 max-w-sm rounded-lg border border-border-hairline bg-surface px-3 py-2 text-xs text-foreground shadow-lg"
        >
          {entityNotice}
        </div>
      )}
    </div>
  );
}
