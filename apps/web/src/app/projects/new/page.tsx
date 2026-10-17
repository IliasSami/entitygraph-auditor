"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight } from "@/components/icons";
import { Button, buttonClasses } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { ErrorState } from "@/components/states";
import { SampleDataBanner } from "@/components/status";
import { api, isMockMode } from "@/lib/api";
import { usePageTitle } from "@/lib/use-page-title";
import type { ProjectCreate } from "@/lib/types";

function ErrorText({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="mt-1 text-xs font-medium text-destructive">
      {message}
    </p>
  );
}

export default function NewProjectPage() {
  usePageTitle("New project");
  const router = useRouter();
  const queryClient = useQueryClient();
  const [values, setValues] = useState({
    name: "",
    brand: "",
    base_url: "",
    industry: "",
    country_region: "",
    audience_icp: "",
    central_entity: "",
    target_conversion: "",
    languages: "en",
    description: "",
  });
  const [errors, setErrors] = useState<{ name?: string }>({});

  const create = useMutation({
    mutationFn: (payload: ProjectCreate) => api.createProject(payload),
    onSuccess: (project) => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push(`/projects/${project.project_id}`);
    },
  });

  const update = (key: keyof typeof values) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setValues((current) => ({ ...current, [key]: event.target.value }));

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (values.name.trim().length < 2) {
      setErrors({ name: "Give the project a name (at least 2 characters)." });
      return;
    }
    setErrors({});
    create.mutate({
      name: values.name.trim(),
      brand: values.brand.trim() || values.name.trim(),
      base_url: values.base_url.trim() || null,
      industry: values.industry.trim() || null,
      country_region: values.country_region.trim() || null,
      audience_icp: values.audience_icp.trim() || null,
      central_entity: values.central_entity.trim() || values.name.trim(),
      target_conversion: values.target_conversion.trim() || null,
      languages: values.languages
        .split(/[,\s]+/)
        .map((code) => code.trim())
        .filter(Boolean),
      description: values.description.trim() || null,
    });
  };

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="space-y-1">
        <Link
          href="/projects"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Projects
        </Link>
        <h1 className="text-xl font-semibold">New project</h1>
        <p className="text-sm text-muted-foreground">
          The brand entity you name here becomes the default central entity for audits in
          this project.
        </p>
      </div>

      {isMockMode() ? <SampleDataBanner /> : null}

      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
          <CardDescription>Only the name is required; everything else is optional.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label htmlFor="name">Project name *</Label>
              <Input
                id="name"
                value={values.name}
                onChange={update("name")}
                placeholder="Northwind Roofing"
                aria-invalid={Boolean(errors.name)}
              />
              <ErrorText message={errors.name} />
            </div>
            <div>
              <Label htmlFor="brand">Brand entity</Label>
              <Input id="brand" value={values.brand} onChange={update("brand")} />
            </div>
            <div>
              <Label htmlFor="base_url">Base URL</Label>
              <Input
                id="base_url"
                type="url"
                placeholder="https://example.com"
                value={values.base_url}
                onChange={update("base_url")}
              />
            </div>
            <div>
              <Label htmlFor="industry">Industry</Label>
              <Input id="industry" value={values.industry} onChange={update("industry")} />
            </div>
            <div>
              <Label htmlFor="country_region">Country / region</Label>
              <Input
                id="country_region"
                placeholder="US-WA"
                value={values.country_region}
                onChange={update("country_region")}
              />
            </div>
            <div>
              <Label htmlFor="languages">Languages</Label>
              <Input
                id="languages"
                placeholder="en, es"
                value={values.languages}
                onChange={update("languages")}
              />
            </div>
            <div>
              <Label htmlFor="central_entity">Central entity</Label>
              <Input
                id="central_entity"
                value={values.central_entity}
                onChange={update("central_entity")}
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="audience_icp">Audience / ICP</Label>
              <Textarea
                id="audience_icp"
                rows={2}
                value={values.audience_icp}
                onChange={update("audience_icp")}
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="target_conversion">Target conversion</Label>
              <Input
                id="target_conversion"
                placeholder="Book a free inspection"
                value={values.target_conversion}
                onChange={update("target_conversion")}
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                rows={2}
                value={values.description}
                onChange={update("description")}
              />
            </div>

            {create.error ? (
              <div className="sm:col-span-2">
                <ErrorState error={create.error} title="Could not create the project" />
              </div>
            ) : null}

            <div className="flex justify-end gap-2 sm:col-span-2">
              <Link href="/projects" className={buttonClasses({ variant: "outline" })}>
                Cancel
              </Link>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Creating…" : "Create project"}
                <ArrowRight className="h-3.5 w-3.5" aria-hidden />
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
