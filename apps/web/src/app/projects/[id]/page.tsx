"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, PencilRuler, Plus, TrendingUp } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { buttonClasses } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { GateBadge, SampleDataBanner } from "@/components/status";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, isMockMode } from "@/lib/api";
import { usePageTitle } from "@/lib/use-page-title";
import { formatDateTime, formatNumber, titleCase } from "@/lib/format";
import { PAGE_TYPE_LABELS } from "@/lib/types";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id ?? "";

  const project = useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => api.getProject(projectId),
    enabled: Boolean(projectId),
  });
  const audits = useQuery({
    queryKey: ["audits", { project_id: projectId }],
    queryFn: () => api.listAudits({ project_id: projectId }),
    enabled: Boolean(projectId),
  });
  const packs = useQuery({ queryKey: ["context-packs"], queryFn: () => api.listContextPacks() });

  usePageTitle(project.data?.name ?? "Project");

  if (project.isPending) return <LoadingState label="Loading project…" />;
  if (project.error) {
    return (
      <ErrorState
        error={project.error}
        title="Could not load this project"
        onRetry={() => project.refetch()}
      />
    );
  }
  if (!project.data) return <ErrorState error={new Error("No project returned.")} />;

  const p = project.data;
  const rows = (audits.data ?? []).sort((a, b) => b.created_at.localeCompare(a.created_at));
  const scored = rows.filter((row) => row.composite != null);
  const avg =
    scored.length > 0
      ? scored.reduce((sum, row) => sum + (row.composite ?? 0), 0) / scored.length
      : null;
  const attachedPacks = (packs.data ?? []).filter((pack) =>
    (p.context_pack_ids ?? []).includes(pack.pack_id),
  );

  return (
    <div className="space-y-5">
      <Link
        href="/projects"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Projects
      </Link>

      {isMockMode() ? <SampleDataBanner /> : null}

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{p.name}</h1>
          {p.description ? (
            <p className="mt-1 text-sm text-muted-foreground">{p.description}</p>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge variant="secondary">{p.industry ?? "Industry not set"}</Badge>
            <Badge variant="secondary">{p.country_region ?? "No region"}</Badge>
            <Badge variant="secondary">{(p.languages ?? ["en"]).join(", ")}</Badge>
            <Badge variant="secondary">Central: {p.central_entity ?? p.name}</Badge>
          </div>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/audits/new?project_id=${p.project_id}`}
            className={buttonClasses({ size: "sm" })}
          >
            <Plus className="h-3.5 w-3.5" aria-hidden /> Run an audit
          </Link>
        </div>
      </header>

      <section aria-label="Project facts" className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Audits</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{rows.length}</p>
            <p className="text-xs text-muted-foreground">
              {p.audit_count != null && p.audit_count !== rows.length
                ? `${p.audit_count} recorded on the server`
                : "in this workspace"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Average composite
            </p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">
              {formatNumber(avg)}
            </p>
            <p className="text-xs text-muted-foreground">internal heuristic, 0–10</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Context packs</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{attachedPacks.length}</p>
            <p className="text-xs text-muted-foreground">
              {attachedPacks.length === 0 ? (
                <Link href="/context-packs" className="text-primary hover:underline">
                  Import a pack
                </Link>
              ) : (
                attachedPacks.map((pack) => pack.name).join(", ")
              )}
            </p>
          </CardContent>
        </Card>
      </section>

      <section aria-labelledby="project-details-heading">
        <Card>
          <CardHeader>
            <CardTitle id="project-details-heading" className="text-base">
              Settings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <dt className="text-muted-foreground">Project ID</dt>
                <dd className="break-all font-mono text-xs">{p.project_id}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Base URL</dt>
                <dd className="break-all">{p.base_url ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Brand</dt>
                <dd>{p.brand ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Audience</dt>
                <dd>{p.audience_icp ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Target conversion</dt>
                <dd>{p.target_conversion ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Model profile</dt>
                <dd className="font-mono text-xs">{p.model_profile ?? "local_default"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Created</dt>
                <dd>{formatDateTime(p.created_at)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Updated</dt>
                <dd>{formatDateTime(p.updated_at)}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>
      </section>

      <section aria-labelledby="project-audits-heading" className="space-y-3">
        <div className="flex items-center justify-between">
          <h2
            id="project-audits-heading"
            className="flex items-center gap-2 text-base font-semibold"
          >
            <TrendingUp className="h-4 w-4 text-primary" aria-hidden /> Audit history
          </h2>
          <span className="text-sm text-muted-foreground">
            {rows.length} audit{rows.length === 1 ? "" : "s"}
          </span>
        </div>

        {audits.isPending ? (
          <LoadingState label="Loading audits…" />
        ) : audits.error ? (
          <ErrorState
            error={audits.error}
            title="Could not load audits for this project"
            onRetry={() => audits.refetch()}
          />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No audits in this project yet"
            description="Run an audit against a page to start building a score history for this project."
            action={
              <Link
                href={`/audits/new?project_id=${p.project_id}`}
                className={buttonClasses({ size: "sm" })}
              >
                <Plus className="h-3.5 w-3.5" aria-hidden /> Run the first audit
              </Link>
            }
          />
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <caption className="sr-only">Audit history for this project</caption>
              <TableHeader>
                <TableRow>
                  <TableHead scope="col">Created</TableHead>
                  <TableHead scope="col">Audit</TableHead>
                  <TableHead scope="col">Page type</TableHead>
                  <TableHead scope="col">Status</TableHead>
                  <TableHead scope="col">Gate</TableHead>
                  <TableHead scope="col">Composite</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.audit_id}>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDateTime(row.created_at)}
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/audits/${row.audit_id}`}
                        className="font-mono text-xs text-primary hover:underline"
                      >
                        {row.audit_id}
                      </Link>
                    </TableCell>
                    <TableCell className="text-sm">
                      {PAGE_TYPE_LABELS[row.page_type] ?? titleCase(row.page_type)}
                    </TableCell>
                    <TableCell className="text-sm">{titleCase(row.status)}</TableCell>
                    <TableCell>
                      <GateBadge status={row.gate_status} />
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {formatNumber(row.composite)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <PencilRuler className="h-3.5 w-3.5" aria-hidden />
        Editing project settings arrives in a later release; scores already stored are not
        recalculated when settings change.
      </p>
    </div>
  );
}
