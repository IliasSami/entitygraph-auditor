"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, Download, FileText } from "@/components/icons";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ErrorState, LoadingState } from "@/components/states";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { WriterHandoff } from "@/lib/types";

function LexiconGroup({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      {items.length ? (
        <ul className="mt-1 flex flex-wrap gap-1">
          {items.map((item) => (
            <li key={item} className="rounded bg-secondary px-1.5 py-0.5 text-xs">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-xs text-muted-foreground">None</p>
      )}
    </div>
  );
}

export function WriterHandoffDialog({
  auditId,
  open,
  onOpenChange,
}: {
  auditId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [copied, setCopied] = useState(false);
  const handoff = useQuery<WriterHandoff>({
    queryKey: ["writer-handoff", auditId],
    queryFn: () => api.writerHandoff(auditId),
    enabled: open,
    staleTime: 60_000,
  });

  const copy = async () => {
    if (!handoff.data) return;
    try {
      await navigator.clipboard.writeText(handoff.data.brief_markdown);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  const download = () => {
    if (!handoff.data) return;
    const blob = new Blob([handoff.data.brief_markdown], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `writer-brief-${auditId}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Writer handoff"
      className="max-w-3xl"
    >
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          A writing brief generated from this audit’s recommendations: what to change,
          where, and the language to use or avoid. It is produced deterministically from
          the report — no extra model call is made.
        </p>

        {handoff.isPending ? (
          <LoadingState label="Generating the writer brief…" />
        ) : handoff.error ? (
          <ErrorState
            error={handoff.error}
            title="Could not generate the writer brief"
            onRetry={() => handoff.refetch()}
          />
        ) : handoff.data ? (
          <>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={copy}>
                <Copy className="h-3.5 w-3.5" aria-hidden />
                {copied ? "Copied" : "Copy brief"}
              </Button>
              <Button variant="outline" size="sm" onClick={download}>
                <Download className="h-3.5 w-3.5" aria-hidden /> Download .md
              </Button>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <LexiconGroup title="Include" items={handoff.data.lexicon.include} />
              <LexiconGroup title="Replace" items={handoff.data.lexicon.replace} />
              <LexiconGroup title="Avoid" items={handoff.data.lexicon.avoid} />
            </div>

            {handoff.data.actions.length ? (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">
                    Actions ({handoff.data.actions.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {handoff.data.actions.map((action) => (
                      <li key={action.finding_id} className="rounded-md border p-2 text-sm">
                        <span className="font-medium">{action.title}</span>
                        <span className="ml-2 font-mono text-xs text-muted-foreground">
                          {action.finding_id}
                        </span>
                        {action.suggested_rewrite ? (
                          <p className="mt-1 text-muted-foreground">
                            {action.suggested_rewrite}
                          </p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ) : null}

            <div>
              <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <FileText className="h-3.5 w-3.5" aria-hidden /> Brief
              </p>
              <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-xs">
                {handoff.data.brief_markdown}
              </pre>
            </div>
          </>
        ) : null}
      </div>
    </Dialog>
  );
}
