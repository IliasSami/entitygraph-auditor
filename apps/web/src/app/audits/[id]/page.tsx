"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Ban,
  FileText,
  RefreshCw,
  Trash2,
  Zap,
} from "@/components/icons";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonClasses } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorState, LoadingState, EmptyState } from "@/components/states";
import {
  GateBadge,
  HeuristicDisclaimer,
  OriginBadge,
  SampleDataBanner,
} from "@/components/status";
import { GateSummary } from "@/components/report/gate-summary";
import { StageTimeline } from "@/components/report/stage-timeline";
import { WriterHandoffDialog } from "@/components/report/writer-handoff-dialog";
import { OverviewTab } from "@/components/report/tabs/overview-tab";
import { EntitiesTab } from "@/components/report/tabs/entities-tab";
import { RelationshipsTab } from "@/components/report/tabs/relationships-tab";
import { QueriesTab } from "@/components/report/tabs/queries-tab";
import { PassagesTab } from "@/components/report/tabs/passages-tab";
import { EvidenceTab } from "@/components/report/tabs/evidence-tab";
import { RecommendationsTab } from "@/components/report/tabs/recommendations-tab";
import { FlagsTab } from "@/components/report/tabs/flags-tab";
import { HistoryTab } from "@/components/report/tabs/history-tab";
import { PublishTab } from "@/components/report/tabs/publish-tab";
import { api, isMockMode } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { usePageTitle } from "@/lib/use-page-title";
import { formatDateTime, formatDuration, titleCase } from "@/lib/format";
import type { AuditRunDetail, ExportFormat, StageRecord } from "@/lib/types";

const TABS = [
  { value: "overview", label: "Overview" },
  { value: "publish", label: "Publish & Schema" },
  { value: "entities", label: "Entities & EAV" },
  { value: "relationships", label: "Relationships" },
  { value: "queries", label: "Query coverage" },
  { value: "passages", label: "Passage audit" },
  { value: "evidence", label: "Evidence & claims" },
  { value: "recommendations", label: "Recommendations" },
  { value: "flags", label: "Sources & technical flags" },
  { value: "history", label: "History" },
] as const;

type TabValue = (typeof TABS)[number]["value"];

const RUNNING_STATUSES = new Set(["queued", "running"]);

export default function AuditReportPage() {
  const params = useParams<{ id: string }>();
  const auditId = params?.id ?? "";
  const router = useRouter();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<TabValue>("overview");
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<unknown>(null);
  const [deleting, setDeleting] = useState(false);

  usePageTitle(`Audit ${auditId.slice(0, 8)}`);

  const run = useQuery<AuditRunDetail>({
    queryKey: ["audit", auditId],
    queryFn: () => api.getAudit(auditId),
    enabled: auditId.length > 0,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && RUNNING_STATUSES.has(status) ? 1200 : false;
    },
  });

  const status = run.data?.status ?? null;
  const live = status !== null && RUNNING_STATUSES.has(status);
  /**
   * Stream bookkeeping keyed by audit id: transitions only ever happen inside
   * SSE callbacks (an external system), never in the render or an effect body.
   */
  const [stream, setStream] = useState<{ id: string; closed: boolean; sawEvent: boolean }>({
    id: "",
    closed: false,
    sawEvent: false,
  });
  const streamState =
    stream.id === auditId
      ? stream.closed
        ? "closed"
        : stream.sawEvent
          ? "open"
          : "waiting"
      : "waiting";
  const lastEventAt = useRef<number | null>(null);

  /* Live stage updates: SSE while the run is active; polling is the fallback. */
  useEffect(() => {
    if (!auditId || !live) return;
    const unsubscribe = api.subscribeAuditEvents(
      auditId,
      () => {
        lastEventAt.current = Date.now();
        setStream({ id: auditId, closed: false, sawEvent: true });
        void queryClient.invalidateQueries({ queryKey: ["audit", auditId] });
      },
      (event) => {
        lastEventAt.current = Date.now();
        const terminal = event.status === "succeeded" || event.status === "failed";
        setStream({ id: auditId, closed: terminal, sawEvent: true });
        void queryClient.invalidateQueries({ queryKey: ["audit", auditId] });
      },
      () => setStream({ id: auditId, closed: true, sawEvent: true }),
    );
    return () => unsubscribe();
  }, [auditId, live, queryClient]);

  const onExport = useCallback(
    async (format: ExportFormat) => {
      setExporting(true);
      setExportError(null);
      try {
        const { blob, filename } = await api.exportAudit(auditId, format);
        downloadBlob(blob, filename);
      } catch (error) {
        setExportError(error);
      } finally {
        setExporting(false);
      }
    },
    [auditId],
  );

  const onDelete = useCallback(async () => {
    if (
      !window.confirm(
        "Delete this audit and its report? This cannot be undone from the interface.",
      )
    ) {
      return;
    }
    setDeleting(true);
    try {
      await api.deleteAudit(auditId);
      await queryClient.invalidateQueries({ queryKey: ["audits"] });
      router.push("/audits");
    } catch (error) {
      setExportError(error);
      setDeleting(false);
    }
  }, [auditId, queryClient, router]);

  if (run.isPending) return <LoadingState label="Loading audit…" />;
  if (run.error) {
    return (
      <ErrorState
        error={run.error}
        title="Could not load this audit"
        onRetry={() => run.refetch()}
      />
    );
  }
  if (!run.data) return <ErrorState error={new Error("No audit returned.")} />;

  const data = run.data;
  const report = data.report;
  const stages: StageRecord[] = data.progress?.stages ?? [];
  const completed = data.progress?.completed ?? 0;
  const total = data.progress?.total ?? stages.length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <Link
          href="/audits"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> All audits
        </Link>
      </div>

      {isMockMode() ? <SampleDataBanner /> : null}

      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">
            Audit <span className="font-mono text-base">{auditId}</span>
          </h1>
          <Badge variant={live ? "info" : data.status === "failed" ? "destructive" : "success"}>
            {titleCase(data.status)}
          </Badge>
          {data.gate_status ? <GateBadge status={data.gate_status} /> : null}
          {data.deterministic_only ? (
            <Badge variant="secondary">
              <Zap className="h-3 w-3" aria-hidden /> Deterministic only
            </Badge>
          ) : null}
        </div>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          <span>Started {formatDateTime(data.created_at)}</span>
          {data.completed_at ? (
            <span>Finished {formatDateTime(data.completed_at)}</span>
          ) : null}
          {data.duration_ms != null ? (
            <span>Took {formatDuration(data.duration_ms)}</span>
          ) : null}
          {data.page_type ? <span>{titleCase(data.page_type)} page</span> : null}
          {data.provider_model ? <span>{data.provider_model}</span> : null}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setHandoffOpen(true)}
            disabled={!report}
          >
            <FileText className="h-3.5 w-3.5" aria-hidden /> Writer handoff
          </Button>
          <Link
            href={`/audits/new`}
            className={buttonClasses({ variant: "outline", size: "sm" })}
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden /> Run another audit
          </Link>
          <Button
            variant="ghost"
            size="sm"
            onClick={onDelete}
            disabled={deleting || live}
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden /> {deleting ? "Deleting…" : "Delete"}
          </Button>
        </div>
      </header>

      {exportError ? (
        <ErrorState error={exportError} title="The last action failed" />
      ) : null}

      {live ? (
        <section aria-labelledby="run-progress-heading" className="space-y-4">
          <div className="rounded-lg border p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 id="run-progress-heading" className="text-sm font-semibold">
                Running audit
              </h2>
              <span
                className="flex items-center gap-2 text-xs text-muted-foreground"
                role="status"
              >
                <OriginBadge origin="deterministic" />
                {streamState === "open"
                  ? "Live updates streaming from the server"
                  : streamState === "closed"
                    ? "Stream closed — polling for the final result"
                    : "Subscribed — waiting for the first update…"}
              </span>
            </div>
            <div className="mt-3 space-y-2">
              <p className="text-sm text-muted-foreground">
                <strong className="text-foreground tabular-nums">
                  {completed} of {total}
                </strong>{" "}
                stages complete. Progress is reported by the server stage by stage — no
                estimated percentage is shown.
              </p>
              <Progress
                value={total > 0 ? completed / total : null}
                aria-label="Stages complete"
                aria-valuetext={`${completed} of ${total} stages complete`}
              />
            </div>
          </div>
          <StageTimeline stages={stages} />
          <HeuristicDisclaimer />
        </section>
      ) : data.status === "failed" ? (
        <section aria-labelledby="failed-heading" className="space-y-4">
          <Alert variant="destructive" title="This audit failed">
            <p>
              {data.error?.code ? (
                <span className="font-mono text-xs">{data.error.code}: </span>
              ) : null}
              {data.error?.message ??
                "A stage did not complete. No partial report was written."}
            </p>
            <p className="mt-2">
              The failing stage and its error are listed below. Fix the cause (for example a
              provider timeout) and run the audit again — the content version is already
              stored.
            </p>
          </Alert>
          <StageTimeline stages={stages} />
          <div>
            <Link href="/audits/new" className={buttonClasses({ size: "sm" })}>
              <RefreshCw className="h-3.5 w-3.5" aria-hidden /> Run a new audit
            </Link>
          </div>
        </section>
      ) : report ? (
        <div className="space-y-5">
          <GateSummary
            report={report}
            onExport={onExport}
            exporting={exporting}
            onOpenRecommendations={() => setTab("recommendations")}
          />

          {report.limitations && report.limitations.length > 0 ? (
            <Alert variant="info" title="Read this before acting on the scores">
              <ul className="list-disc space-y-1 pl-4">
                {report.limitations.slice(0, 3).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </Alert>
          ) : null}

          <Tabs
            value={tab}
            onValueChange={(value) => setTab(value as TabValue)}
            label="Report sections"
          >
            <TabsList>
              {TABS.map((item) => (
                <TabsTrigger key={item.value} value={item.value}>
                  {item.label}
                </TabsTrigger>
              ))}
            </TabsList>

            <TabsContent value="overview">
              <OverviewTab report={report} />
            </TabsContent>
            <TabsContent value="publish">
              <PublishTab report={report} />
            </TabsContent>
            <TabsContent value="entities">
              <EntitiesTab report={report} />
            </TabsContent>
            <TabsContent value="relationships">
              <RelationshipsTab report={report} />
            </TabsContent>
            <TabsContent value="queries">
              <QueriesTab report={report} />
            </TabsContent>
            <TabsContent value="passages">
              <PassagesTab report={report} />
            </TabsContent>
            <TabsContent value="evidence">
              <EvidenceTab report={report} />
            </TabsContent>
            <TabsContent value="recommendations">
              <RecommendationsTab report={report} />
            </TabsContent>
            <TabsContent value="flags">
              <FlagsTab report={report} />
            </TabsContent>
            <TabsContent value="history">
              <HistoryTab
                projectId={report.audit_metadata.project_id}
                currentAuditId={auditId}
                stages={stages}
              />
            </TabsContent>
          </Tabs>

          <Separator />
          <p className="text-xs text-muted-foreground">
            Report generated {formatDateTime(report.audit_metadata.created_at)} · content
            hash <span className="font-mono">{report.audit_metadata.content_hash}</span>
          </p>
        </div>
      ) : (
        <EmptyState
          title="No report for this audit"
          description="The run finished but no report was stored. This usually means the audit was cancelled, or report storage was disabled for this project."
          action={
            <Link href="/audits/new" className={buttonClasses({ size: "sm" })}>
              <Ban className="h-3.5 w-3.5" aria-hidden /> Run a new audit
            </Link>
          }
        />
      )}

      <WriterHandoffDialog
        auditId={auditId}
        open={handoffOpen && Boolean(report)}
        onOpenChange={setHandoffOpen}
      />
    </div>
  );
}
