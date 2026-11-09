import { defineConfig } from "@playwright/test";

// Normal use: `npx playwright install chromium`, start the API and the web app, then `npm run e2e`.
// CHROMIUM_PATH lets a machine without downloadable browsers use its own Chromium.
const exe = process.env.CHROMIUM_PATH;
export default defineConfig({
  testDir: "e2e",
  timeout: 90000,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_URL || "http://127.0.0.1:4173",
    launchOptions: exe ? { executablePath: exe, args: [...JSON.parse(process.env.CHROMIUM_ARGS || "[]"), "--no-sandbox"] } : {},
  },
});
