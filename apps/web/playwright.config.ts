import { defineConfig, devices } from "@playwright/test";

/**
 * UI smoke / e2e checks (DRD §15: desktop, tablet and mobile checked with Playwright).
 * The API is mocked per test (e2e/mock-api.ts), so these run without models or a database.
 * Runs against a production build on port 3100.
 *
 * - Default browser: Playwright's Chromium (`npx playwright install chromium`).
 * - Windows machines without that download can use the installed Edge: PW_CHANNEL=msedge.
 */
const channel = process.env.PW_CHANNEL;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3100",
    trace: "retain-on-failure",
    ...(channel ? { channel } : {}),
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], ...(channel ? { channel } : {}) } },
  ],
  webServer: {
    command: "npm run build && npx next start -p 3100",
    url: "http://localhost:3100",
    reuseExistingServer: !process.env.CI,
    timeout: 240_000,
    // The API proxy target is irrelevant: every /api/v1 request is intercepted by the tests.
    env: { API_INTERNAL_URL: "http://127.0.0.1:9" },
  },
});
