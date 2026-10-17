"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Download, Search } from "@/components/icons";
import { Badge } from "@/components/ui/badge";
import { Button, buttonClasses } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, QueryView } from "@/components/states";
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
import { downloadBlob } from "@/lib/download";
import { usePageTitle } from "@/lib/use-page-title";
import { formatDateTime, formatNumber, titleCase } from "@/lib/format";
import type { AuditListRow, AuditRunStatus, ExportFormat } from "@/lib/types";
import { PAGE_TYPES, PAGE_TYPE_LABELS } from "@/lib/types";

const STATUS_OPTIONS: AuditRunStatus[] = ["queued", "running", "succeeded", "failed"];

export default function AuditsPage() {
  usePageTitle("Audits");

  const [projectFilter, setProjectFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [pageTypeFilter, setPageTypeFilter] = useState("all");
  const [q, setQ] = useState("");
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.listProjects() });
  const audits = useQuery({ queryKey: ["audits"], queryFn: () => api.listAudits() });

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (audits.data ?? []).filter((row) => {
      if (projectFilter !== "all" && row.project_id !== projectFilter) return false;
      if (statusFilter !== "all" && row.status !== statusFilter) return false;
      if (pageTypeFilter !== "all" && row.page_type !== pageTypeFilter) return false;
      if (
        needle &&
        !`${row.audit_id} ${row.central_entity ?? ""} ${row.primary_query ?? ""}`
          .toLowerCase()
          .includes(needle)
      ) {
        return false;
      }
      return true;
    });
  }, [audits.data, projectFilter, statusFilter, pageTypeFilter, q]);

  const projectName = (id: string) =>
    projects.data?.find((p) => p.project_id === id)?.name ?? id;

  const onExport = async (row: AuditListRow, format: ExportFormat) => {
    setExporting(row.audit_id);
    setExportError(null);
    try {
      const { blob, filename } = await api.exportAudit(row.audit_id, format);
      downloadBlob(blob, filename);
    } catch (error) {
      setExportError(
        error instanceof Error
          ? `Could not export ${row.audit_id}: ${error.message}`
          : `Could not export ${row.audit_id}.`,
      );
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Audits</h1>
          <p className="text-sm text-muted-foreground">
            Every audit run, newest first. Open a row for the full report or export it.
          </p>
        </div>
        <Link href="/audits/new" className={buttonClasses({ size: "sm" })}>
          Run an audit
        </Link>
      </div>

      {isMockMode() ? <SampleDataBanner /> : null}

      <Card>
        <CardContent className="pt-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search id, entity, or query…"
                aria-label="Search audits"
                className="pl-8"
              />
            </div>
            <Select
              value={projectFilter}
              onChange={(e) => setProjectFilter(e.target.value)}
              aria-label="Filter by project"
            >
              <option value="all">All projects</option>
              {(projects.data ?? []).map((project) => (
                <option key={project.project_id} value={project.project_id}>
                  {project.name}
                </option>
              ))}
            </Select>
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by status"
            >
              <option value="all">All statuses</option>
              {STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {titleCase(status)}
                </option>
              ))}
            </Select>
            <Select
              value={pageTypeFilter}
              onChange={(e) => setPageTypeFilter(e.target.value)}
              aria-label="Filter by page type"
            >
              <option value="all">All page types</option>
              {PAGE_TYPES.map((pageType) => (
                <option key={pageType} value={pageType}>
                  {PAGE_TYPE_LABELS[pageType]}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      {exportError ? (
        <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
          {exportError}
        </p>
      ) : null}

      <QueryView
        query={audits}
        loadingLabel="Loading audits…"
        errorTitle="Could not load audits"
        isEmpty={(data) => data.length === 0}
        empty={
          <EmptyState
            title="No audits yet"
            description="Nothing has been audited. Run your first audit to see entity coverage, relationships, and query fan-out for a page."
            action={
              <Link href="/audits/new" className={buttonClasses({ size: "sm" })}>
                Run an audit
              </Link>
            }
          />
        }
      >
        {() => (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground" role="status">
              Showing <strong className="text-foreground tabular-nums">{rows.length}</strong> of{" "}
              {(audits.data ?? []).length} audits.
            </p>
            {rows.length === 0 ? (
              <EmptyState
                title="No audits match these filters"
                description="Change or clear the filters above to see more audits."
              />
            ) : (
              <div className="overflow-x-auto rounded-md border">
                <Table>
                  <caption className="sr-only">
                    Audit runs with project, page type, status, gate result and composite score
                  </caption>
                  <TableHeader>
                    <TableRow>
                      <TableHead scope="col">Audit</TableHead>
                      <TableHead scope="col">Project</TableHead>
                      <TableHead scope="col">Page type</TableHead>
                      <TableHead scope="col">Created</TableHead>
                      <TableHead scope="col">Status</TableHead>
                      <TableHead scope="col">Gate</TableHead>
                      <TableHead scope="col">Composite</TableHead>
                      <TableHead scope="col">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((row) => (
                      <TableRow key={row.audit_id}>
                        <TableCell>
                          <Link
                            href={`/audits/${row.audit_id}`}
                            className="font-mono text-xs text-primary hover:underline"
                          >
                            {row.audit_id}
                          </Link>
                          {row.central_entity ? (
                            <span className="block text-xs text-muted-foreground">
                              {row.central_entity}
                            </span>
                          ) : null}
                        </TableCell>
                        <TableCell className="text-sm">
                          {projectName(row.project_id)}
                        </TableCell>
                        <TableCell className="text-sm">
                          {PAGE_TYPE_LABELS[row.page_type] ?? titleCase(row.page_type)}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDateTime(row.created_at)}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              row.status === "failed"
                                ? "destructive"
                                : row.status === "succeeded"
                                  ? "success"
                                  : "info"
                            }
                          >
                            {titleCase(row.status)}
                          </Badge>
                          {row.error ? (
                            <span className="mt-1 block max-w-[14rem] text-xs text-destructive">
                              {typeof row.error === "string"
                                ? row.error
                                : row.error.message}
                            </span>
                          ) : null}
                        </TableCell>
                        <TableCell>
                          <GateBadge status={row.gate_status} />
                        </TableCell>
                        <TableCell className="tabular-nums">
                          {formatNumber(row.composite)}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            <Button
                              variant="link"
                              size="sm"
                              onClick={() => onExport(row, "markdown")}
                              disabled={exporting === row.audit_id || row.status !== "succeeded"}
                            >
                              <Download className="h-3.5 w-3.5" aria-hidden /> MD
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => onExport(row, "html")}
                              disabled={exporting === row.audit_id || row.status !== "succeeded"}
                            >
                              HTML
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => onExport(row, "json")}
                              disabled={exporting === row.audit_id || row.status !== "succeeded"}
                            >
                              JSON
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => onExport(row, "csv")}
                              disabled={exporting === row.audit_id || row.status !== "succeeded"}
                            >
                              CSV
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        )}
      </QueryView>
    </div>
  );
}
