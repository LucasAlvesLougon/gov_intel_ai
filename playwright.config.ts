import { defineConfig, devices } from "@playwright/test";

/**
 * E2E do fluxo demo: cadastro → upload → processamento → busca → chat.
 * Base URL é o frontend Next.js publicado em localhost:3000 (Docker Compose).
 * Execução: `npx playwright test e2e/govintel-flow.spec.ts`
 */
export default defineConfig({
  testDir: "e2e",
  testMatch: "govintel-flow.spec.ts",
  timeout: 240_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
