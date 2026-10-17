"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Ban, FileText, ListChecks, Plug } from "@/components/icons";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { SampleDataBanner } from "@/components/status";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, isMockMode } from "@/lib/api";
import { usePageTitle } from "@/lib/use-page-title";

export default function McpPage() {
  usePageTitle("MCP");

  const servers = useQuery({
    queryKey: ["mcp-servers"],
    queryFn: () => api.listMcpServers(),
    retry: false,
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">MCP servers</h1>
          <p className="text-sm text-muted-foreground">
            The Model Context Protocol surface exposes read-only audit tools to approved clients —
            list projects, read a report, fetch scores. There is no shell, no file write and no
            arbitrary execution tool, by design.
          </p>
        </div>
        <Badge variant="secondary">
          <span aria-hidden="true">🛡</span> Read-only tools
        </Badge>
      </div>

      {isMockMode() ? <SampleDataBanner /> : null}

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Plug className="h-4 w-4 text-muted-foreground" aria-hidden />
              Transport
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            stdio for local clients, HTTP for remote ones. Each server lists the exact endpoint it
            listens on.
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <ListChecks className="h-4 w-4 text-muted-foreground" aria-hidden />
              Allowed tools
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            An explicit allow-list per server. Anything not named in{" "}
            <span className="font-mono text-xs">allowed_tools</span> is rejected by the API.
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Ban className="h-4 w-4 text-muted-foreground" aria-hidden />
              Deliberately absent
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            No shell, no process spawn, no filesystem writes, no network fetch tool. The MCP surface
            reads audit data and nothing else.
          </CardContent>
        </Card>
      </div>

      <section aria-labelledby="mcp-servers-heading">
        <h2 id="mcp-servers-heading" className="mb-3 text-sm font-semibold">
          Configured servers
        </h2>

        {servers.isPending ? (
          <LoadingState label="Loading MCP servers…" />
        ) : servers.error ? (
          <ErrorState
            error={servers.error}
            title="Could not load MCP servers"
            onRetry={() => servers.refetch()}
          />
        ) : !servers.data || servers.data.length === 0 ? (
          <EmptyState
            title="No MCP servers configured"
            description="This API does not expose any MCP server configuration yet (the endpoint returns nothing, or is not implemented in this build). Nothing is broken — audits, reports and exports all work without it. When the API ships MCP support, configured servers appear here with their transport, endpoint and allowed tools."
            action={
              <Link href="/settings" className="underline text-sm text-primary">
                What is and is not implemented yet
              </Link>
            }
          />
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Transport</TableHead>
                    <TableHead>Endpoint</TableHead>
                    <TableHead>Allowed tools</TableHead>
                    <TableHead className="text-right">Timeout</TableHead>
                    <TableHead className="text-right">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {servers.data.map((server) => (
                    <TableRow key={server.id}>
                      <TableCell className="text-sm font-medium">{server.name}</TableCell>
                      <TableCell className="text-sm">
                        <Badge variant="secondary">{server.transport}</Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{server.endpoint}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {server.allowed_tools.length === 0 ? (
                            <span className="text-xs text-muted-foreground">None</span>
                          ) : (
                            server.allowed_tools.map((tool) => (
                              <Badge key={tool} variant="outline">
                                {tool}
                              </Badge>
                            ))
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-right text-sm tabular-nums">
                        {server.timeout_seconds}s
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge variant={server.enabled ? "success" : "secondary"}>
                          <span aria-hidden="true">{server.enabled ? "✓" : "—"}</span>
                          {server.enabled ? "Enabled" : "Disabled"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </section>

      <Alert variant="default" title="Tool safety">
        <span className="flex items-start gap-2">
          <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            MCP clients inherit this app’s permissions, not yours: a client can only call tools the
            server has listed, and every call is scoped to a single audit or project ID. If a client
            asks for something outside the allow-list, the API refuses rather than guessing.
          </span>
        </span>
      </Alert>
    </div>
  );
}
