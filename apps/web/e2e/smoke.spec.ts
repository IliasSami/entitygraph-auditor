import { expect, test } from "@playwright/test";

/**
 * Smoke tests. These run against `next dev` in mock mode, so they exercise the
 * real UI with the Northwind sample fixture — no backend required.
 */

test("dashboard renders the KPI cards and heading", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText("Pages ready")).toBeVisible();
  await expect(page.getByText("AI mention rate")).toBeVisible();
});

test("no application errors are logged on the dashboard", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    const text = message.text();
    if (message.type() !== "error") return;
    // Dev-only HMR noise: the WebSocket handshake warning in this environment.
    if (/WebSocket|_next\/hmr/i.test(text)) return;
    consoleErrors.push(text);
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  expect(consoleErrors).toEqual([]);
});

test("audit wizard advances from step 1 to step 2 and back", async ({ page }) => {
  await page.goto("/audits/new");
  await expect(page.getByTestId("wizard-step")).toHaveAttribute("data-step", "1");

  await page.getByLabel(/^project$/i).selectOption("proj-northwind");
  await page.getByLabel(/page type/i).selectOption("local_service");
  await page.getByRole("button", { name: "Next", exact: true }).click();

  await expect(page.getByTestId("wizard-step")).toHaveAttribute("data-step", "2");

  await page.getByRole("button", { name: "Back", exact: true }).click();
  await expect(page.getByTestId("wizard-step")).toHaveAttribute("data-step", "1");
});

test("a completed audit report opens with the score cards and gate summary", async ({ page }) => {
  await page.goto("/audits/aud-nw-main");
  await expect(page.getByTestId("gate-badge").first()).toBeVisible();
  await expect(page.getByTestId("score-card").first()).toBeVisible();

  // Opening a score card surfaces the rubric and the heuristic disclaimer.
  await page.getByTestId("score-card").first().getByRole("button").click();
  await expect(page.getByTestId("score-drawer")).toBeVisible();
  await expect(
    page.getByTestId("score-drawer").getByText(/internal editorial heuristic/i),
  ).toBeVisible();
});

test("report tabs include the fan-out query provenance summary", async ({ page }) => {
  await page.goto("/audits/aud-nw-main");
  await page.getByRole("tab", { name: "Query coverage" }).click();
  await expect(page.getByTestId("fanout-provenance-summary")).toBeVisible();
  await expect(page.getByTestId("observed-count")).toBeVisible();
  await expect(page.getByTestId("simulated-count")).toBeVisible();
});

test("context packs page shows pack conflicts prominently", async ({ page }) => {
  await page.goto("/context-packs");
  await expect(page.getByText(/conflict/i).first()).toBeVisible();
});

test("audit run diff requires two completed runs and shows score deltas once chosen", async ({ page }) => {
  await page.goto("/compare");
  // The audit-comparison view now lives on the "Audit Run Diff" tab of the
  // AI Visibility screen (the screen's default tab is the visibility matrix).
  await page.getByRole("button", { name: /Audit Run Diff/i }).click();
  await page.getByLabel(/baseline/i).selectOption("aud-nw-baseline");
  await page.getByLabel(/candidate/i).selectOption("aud-nw-main");
  await expect(page.getByText(/internal editorial heuristic/i).first()).toBeVisible();
  await expect(page.getByTestId("compare-score-delta").first()).toBeVisible();
});

test("providers page lists the deterministic baseline provider", async ({ page }) => {
  await page.goto("/providers");
  await expect(page.getByText(/deterministic baseline/i).first()).toBeVisible();
});

test("mcp page degrades to an honest empty state", async ({ page }) => {
  await page.goto("/mcp");
  await expect(page.getByText(/no mcp servers configured/i)).toBeVisible();
});
