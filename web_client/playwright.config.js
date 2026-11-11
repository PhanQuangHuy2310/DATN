import { defineConfig, devices } from "@playwright/test";

const externalServer = process.env.EAS_E2E_EXTERNAL === "true";

export default defineConfig({
  testDir: "./e2e",
  testMatch: externalServer ? /.*\.spec\.js/ : /(portal|ui)\.spec\.js/,
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["line"], ["html", { open: "never" }]] : "line",
  use: {
    baseURL: process.env.EAS_E2E_BASE_URL || "http://127.0.0.1:4173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: externalServer ? undefined : [
    {
      command: "npm run build && npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
    {
      command: "npm --prefix ../web_admin run build && npm --prefix ../web_admin run preview -- --host 127.0.0.1 --port 4174 --strictPort",
      url: "http://127.0.0.1:4174",
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
  ],
});
