import { defineConfig } from "@playwright/test";

// The job container starts the app and sets BASE_URL; locally, Playwright starts it itself.
const baseURL = process.env.BASE_URL || "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 0,
  reporter: "line",
  use: {
    baseURL,
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
  },
  webServer: process.env.BASE_URL
    ? undefined
    : { command: "PORT=3100 npm start", url: `${baseURL}/healthz`, reuseExistingServer: true, timeout: 60_000 },
});
