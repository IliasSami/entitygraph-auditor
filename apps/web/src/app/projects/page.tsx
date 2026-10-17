"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Boxes, Plus } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { buttonClasses } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, QueryView } from "@/components/states";
import { SampleDataBanner } from "@/components/status";
import { api, isMockMode } from "@/lib/api";
import { usePageTitle } from "@/lib/use-page-title";
import { formatDate } from "@/lib/format";

export default function ProjectsPage() {
  usePageTitle("Projects");
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.listProjects() });

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Projects</h1>
          <p className="text-sm text-muted-foreground">
            A project groups pages, context packs, and audit history for one site or brand.
          </p>
        </div>
        <Link href="/projects/new" className={buttonClasses({ size: "sm" })}>
          <Plus className="h-3.5 w-3.5" aria-hidden /> New project
        </Link>
      </div>

      {isMockMode() ? <SampleDataBanner /> : null}

      <QueryView
        query={projects}
        loadingLabel="Loading projects…"
        errorTitle="Could not load projects"
        isEmpty={(data) => data.length === 0}
        empty={
          <EmptyState
            title="No projects yet"
            description="Create a project for your site so audits, context packs, and score history share one home."
            action={
              <Link href="/projects/new" className={buttonClasses({ size: "sm" })}>
                <Plus className="h-3.5 w-3.5" aria-hidden /> New project
              </Link>
            }
          />
        }
      >
        {(data) => (
          <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.map((project) => (
              <li key={project.project_id}>
                <Card className="h-full">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center justify-between gap-2 text-base">
                      <Link
                        href={`/projects/${project.project_id}`}
                        className="hover:underline"
                      >
                        {project.name}
                      </Link>
                      <Boxes className="h-4 w-4 text-muted-foreground" aria-hidden />
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {project.description ? (
                      <p className="text-sm text-muted-foreground">{project.description}</p>
                    ) : null}
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
                      <div>
                        <dt className="text-xs text-muted-foreground">Base URL</dt>
                        <dd className="break-all text-xs">{project.base_url ?? "—"}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">Industry</dt>
                        <dd>{project.industry ?? "—"}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">Audits</dt>
                        <dd className="tabular-nums">{project.audit_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">Updated</dt>
                        <dd>{formatDate(project.updated_at)}</dd>
                      </div>
                    </dl>
                    <div className="flex flex-wrap gap-1.5">
                      <Badge variant="secondary">{project.country_region ?? "Global"}</Badge>
                      <Badge variant="secondary">
                        {project.languages?.join(", ") ?? "en"}
                      </Badge>
                      {project.context_pack_ids?.length ? (
                        <Badge variant="info">
                          {project.context_pack_ids.length} pack
                          {project.context_pack_ids.length === 1 ? "" : "s"}
                        </Badge>
                      ) : null}
                    </div>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </div>
  );
}
