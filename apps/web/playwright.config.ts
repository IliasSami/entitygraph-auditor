import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright smoke tests run the UI in mock mode (NEXT_PUBLIC_MOCK=1) so they
 * do not require the FastAPI backend.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    // Must be `localhost`, not 127.0.0.1: Next.js 16 blocks dev resources for
    // "unexpected" origins and the app would hydrate never (SSR-only HTML).
    baseURL: "http://localhost:3100",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      // Use the full Chromium build rather than the headless shell: some
      // environments only ship the former. Both are Chromium.
      use: { ...devices["Desktop Chrome"], channel: "chromium" },
    },
  ],
  webServer: {
    command: "npm run dev -- --port 3100",
    url: "http://localhost:3100",
    reuseExistingServer: false,
    timeout: 180_000,
    env: {
      NEXT_PUBLIC_MOCK: "1",
      NEXT_PUBLIC_API_BASE: "http://localhost:8000",
    },
  },
});
