import { expect, test } from "@playwright/test";

/**
 * Coverage for the three screens backed by the workspace read-model API
 * (`/workspace/*` and `/content/brief`). They run against `next dev` in mock
 * mode, so they prove each screen's primary action renders labelled data from
 * the generator rather than hardcoded copy — and that no screen claims to have
 * consulted a source it did not.
 */

test("brief builder labels the initial outline as a sample until assembled", async ({ page }) => {
  await page.goto("/briefs");
  await expect(page.getByText(/sample outline/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /Auto-assemble/i })).toBeVisible();
});

test("brief builder assembles a brief with honest source labels", async ({ page }) => {
  await page.goto("/briefs");
  await page.getByRole("button", { name: /Auto-assemble/i }).click();

  // The generator's disclaimer replaces the sample-state banner.
  await expect(page.getByText(/internal editorial heuristic/i)).toBeVisible();
  await expect(page.getByText(/sample outline/i)).toHaveCount(0);

  // Never claim a People-Also-Ask / AI-engine lookup that was never performed.
  await expect(page.getByText("Google PAA")).toHaveCount(0);
  await expect(page.getByText("Perplexity")).toHaveCount(0);
  await expect(page.getByText("AI Citation Gap")).toHaveCount(0);

  // Word target now comes from the generator, not a hardcoded constant.
  await expect(page.getByText(/Target:\s*900/)).toBeVisible();
});

test("entity hub renders the registry chrome with provenance, no fake schema version", async ({ page }) => {
  await page.goto("/context-packs");
  await expect(page.getByText("entity registry")).toBeVisible();
  await expect(page.getByText(/facts sourced from stored audits/i)).toBeVisible();
  // The footer shows real source counts, not a fabricated schema version.
  await expect(page.getByText(/schema_version/)).toHaveCount(0);
});

test("optimizer renders backend-computed dimension bands and recommendations", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    const text = message.text();
    if (message.type() !== "error") return;
    if (/WebSocket|_next\/hmr/i.test(text)) return;
    consoleErrors.push(text);
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));

  await page.goto("/optimizer");
  await expect(page.getByText(/top recommendations/i)).toBeVisible();
  await expect(page.getByText(/internal editorial heuristic/i).first()).toBeVisible();
  // Dimension labels come from the analysis response.
  for (const label of ["Entities", "Answers", "Evidence", "Passages", "Originality"]) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }
  expect(consoleErrors).toEqual([]);
});
