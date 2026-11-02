import { defineConfig } from "@playwright/test";

// Mocked-API browser tests for the two current portals (client :4173, admin :4174).
// Use a local Chrome/Edge via EAS_CHROMIUM_PATH when Playwright browsers are not installed.
export default defineConfig({
  testDir: "./e2e",
  testMatch: "portal.spec.js",
  workers: 2,
  reporter: "list",
  use: {
    screenshot: process.env.EAS_SHOTS ? "on" : "only-on-failure",
    launchOptions: process.env.EAS_CHROMIUM_PATH ? { executablePath: process.env.EAS_CHROMIUM_PATH } : {},
  },
  webServer: [
    {
      command: "npm run build && npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: false,
      timeout: 120000,
    },
    {
      command: "npm --prefix ../web_admin run build && npm --prefix ../web_admin run preview -- --host 127.0.0.1 --port 4174 --strictPort",
      url: "http://127.0.0.1:4174",
      reuseExistingServer: false,
      timeout: 120000,
    },
  ],
});
