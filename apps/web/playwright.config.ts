import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.WEB_PORT || 3100);
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
    extraHTTPHeaders: {},
  },
  webServer: {
    command: `next dev -p ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    timeout: 60_000,
    reuseExistingServer: !process.env.CI,
    env: {
      NEXT_PUBLIC_API_URL: API_URL,
    },
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
