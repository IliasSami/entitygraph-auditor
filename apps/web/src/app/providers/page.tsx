"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Cpu, Plug, ShieldCheck, ShieldQuestion, Zap } from "@/components/icons";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { QueryView } from "@/components/states";
import { SampleDataBanner } from "@/components/status";
import { api, isMockMode } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { ProviderInfo, TestConnectionResponse } from "@/lib/types";
import { usePageTitle } from "@/lib/use-page-title";

const MODEL_SUGGESTIONS: Record<string, string[]> = {
  dummy: ["deterministic-baseline"],
  ollama: ["llama3.1:8b", "mistral:7b", "qwen2.5:7b"],
  openai: ["gpt-4o-mini", "gpt-4o"],
  anthropic: ["claude-sonnet-4-5", "claude-haiku-4-5"],
  gemini: ["gemini-2.0-flash", "gemini-1.5-pro"],
};

function ProviderCard({
  provider,
  selected,
  onSelect,
}: {
  provider: ProviderInfo;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <Card className={selected ? "border-primary/50" : undefined}>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center justify-between gap-2 text-base">
            <span className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-muted-foreground" aria-hidden />
              {provider.label}
            </span>
            <Badge variant={provider.local ? "success" : "warning"}>
              <span aria-hidden="true">{provider.local ? "◉" : "☁"}</span>
              {provider.local ? "Runs locally" : "Off-device"}
            </Badge>
          </CardTitle>
          <CardDescription>{provider.description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-1.5">
            <Badge variant={provider.requires_api_key ? "secondary" : "outline"}>
              {provider.requires_api_key ? "API key required" : "No API key"}
            </Badge>
            <Badge variant={provider.structured_output ? "info" : "secondary"}>
              {provider.structured_output ? "Structured output" : "Free-text output"}
            </Badge>
            <Badge variant={provider.sends_data_off_device ? "warning" : "success"}>
              <span aria-hidden="true">{provider.sends_data_off_device ? "↑" : "↓"}</span>
              {provider.sends_data_off_device ? "Sends page text off device" : "Page text stays on device"}
            </Badge>
          </div>
          {provider.cost_warning ? (
            <p className="text-xs text-muted-foreground">{provider.cost_warning}</p>
          ) : null}
          <Button
            variant={selected ? "secondary" : "outline"}
            size="sm"
            onClick={onSelect}
            aria-pressed={selected}
          >
            {selected ? "Selected" : "Test this provider"}
          </Button>
        </CardContent>
      </Card>
    </li>
  );
}

function TestResultBadge({ result }: { result: TestConnectionResponse }) {
  if (result.ok) {
    return (
      <Badge variant="success">
        <span aria-hidden="true">✓</span> Connected · {formatNumber(result.latency_ms, 0)} ms
      </Badge>
    );
  }
  return (
    <Badge variant="destructive">
      <span aria-hidden="true">✕</span> Failed
    </Badge>
  );
}

export default function ProvidersPage() {
  usePageTitle("Providers");

  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: () => api.listProviders(),
  });

  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [result, setResult] = useState<TestConnectionResponse | null>(null);

  const selected = providers.data?.providers.find((p) => p.type === selectedType) ?? null;

  const test = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("Pick a provider first.");
      return api.testConnection({
        provider_type: selected.type,
        model: model || MODEL_SUGGESTIONS[selected.type]?.[0] || "default",
        base_url: baseUrl || null,
        api_key: apiKey || null,
      });
    },
    onSuccess: (response) => setResult(response),
    onError: (error) =>
      setResult({
        ok: false,
        latency_ms: 0,
        detail: error instanceof Error ? error.message : "Connection failed.",
      }),
  });

  const select = (provider: ProviderInfo) => {
    setSelectedType(provider.type);
    setModel(MODEL_SUGGESTIONS[provider.type]?.[0] ?? "");
    setBaseUrl("");
    setApiKey("");
    setResult(null);
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Model providers</h1>
          <p className="text-sm text-muted-foreground">
            Audits run two ways: fully deterministic (offline, no model) or with a model for the
            semantic stages. This page lists what is installed and lets you verify a connection
            before starting a run.
          </p>
        </div>
        <Badge variant="secondary">
          <span aria-hidden="true">🛡</span> Keys are sent to the API, never stored in the browser
        </Badge>
      </div>

      {isMockMode() ? <SampleDataBanner /> : null}

      <Alert variant="info" title="Deterministic-only mode is the default">
        Every audit can run with zero paid APIs: parsing, entity extraction, EAV checks, fan-out
        scoring and gate decisions are rule-based. Model providers only add semantic stages (passage
        skill, claim verification drafts, relationship inference), and each result is labelled with
        its origin so heuristic output is never mistaken for observed fact.
      </Alert>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          <QueryView
            query={providers}
            loadingLabel="Loading providers…"
            errorTitle="Could not load providers"
            isEmpty={(data) => data.providers.length === 0}
            empty={
              <Card className="border-dashed">
                <CardContent className="p-10 text-center">
                  <p className="text-sm font-medium">No providers registered</p>
                  <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
                    The API reports no model providers. Deterministic-only audits still work — start
                    one from the new-audit wizard.
                  </p>
                </CardContent>
              </Card>
            }
          >
            {(data) => (
              <ul className="grid gap-4 xl:grid-cols-2">
                {data.providers.map((provider) => (
                  <ProviderCard
                    key={provider.id}
                    provider={provider}
                    selected={selectedType === provider.type}
                    onSelect={() => select(provider)}
                  />
                ))}
              </ul>
            )}
          </QueryView>
        </div>

        <Card className="h-fit">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Plug className="h-4 w-4 text-muted-foreground" aria-hidden />
              Test connection
            </CardTitle>
            <CardDescription>
              Sends one small request to the selected provider. Nothing is saved.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {!selected ? (
              <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                Select a provider on the left to configure a test.
              </p>
            ) : (
              <form
                className="space-y-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  setResult(null);
                  test.mutate();
                }}
              >
                <div className="space-y-1.5">
                  <Label htmlFor="provider-model">Model</Label>
                  <Input
                    id="provider-model"
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    placeholder={MODEL_SUGGESTIONS[selected.type]?.[0] ?? "model name"}
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    Suggested: {(MODEL_SUGGESTIONS[selected.type] ?? []).join(", ") || "none"}
                  </p>
                </div>

                {selected.local && selected.type !== "dummy" ? (
                  <div className="space-y-1.5">
                    <Label htmlFor="provider-url">Base URL</Label>
                    <Input
                      id="provider-url"
                      value={baseUrl}
                      onChange={(event) => setBaseUrl(event.target.value)}
                      placeholder="http://localhost:11434"
                    />
                  </div>
                ) : null}

                {selected.requires_api_key ? (
                  <div className="space-y-1.5">
                    <Label htmlFor="provider-key">API key</Label>
                    <Input
                      id="provider-key"
                      type="password"
                      autoComplete="off"
                      value={apiKey}
                      onChange={(event) => setApiKey(event.target.value)}
                      placeholder="sk-…"
                    />
                    <p className="text-xs text-muted-foreground">
                      Sent over HTTPS to the API for this request only; it is not written to
                      browser storage.
                    </p>
                  </div>
                ) : null}

                <Button type="submit" size="sm" className="w-full" disabled={test.isPending}>
                  <Zap className="h-3.5 w-3.5" aria-hidden />
                  {test.isPending ? "Testing…" : "Run connection test"}
                </Button>
              </form>
            )}

            {test.isPending ? (
              <p role="status" className="text-sm text-muted-foreground">
                Contacting {selected?.label}…
              </p>
            ) : null}

            {result ? (
              <div className="space-y-2 rounded-lg border border-border bg-card p-3" role="status">
                <div className="flex items-center gap-2">
                  <TestResultBadge result={result} />
                  {result.model_name ? (
                    <Badge variant="secondary">{result.model_name}</Badge>
                  ) : null}
                </div>
                <p className="text-sm text-muted-foreground">{result.detail}</p>
                <p className="text-xs text-muted-foreground">
                  {selected?.sends_data_off_device
                    ? "Off-device provider: a successful test means page text can be sent here during semantic stages."
                    : "Local provider: audited page text is not sent over the network."}
                </p>
              </div>
            ) : null}

            <p className="flex items-start gap-2 text-xs text-muted-foreground">
              <ShieldQuestion className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              <span>
                A connection test only proves reachability and auth. It does not run an audit or
                spend a full run’s tokens.
              </span>
            </p>
            <p className="flex items-start gap-2 text-xs text-muted-foreground">
              <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              <span>
                Model output is always labelled <span className="font-medium">simulated</span> in
                reports, never as observed fact.
              </span>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
