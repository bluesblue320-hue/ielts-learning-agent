import { defineConfig, devices } from "@playwright/test";

const databaseUrl = process.env.IELTS_E2E_DATABASE_URL ?? "postgresql+psycopg://ielts_test:phase5-e2e@127.0.0.1:55433/ielts_e2e_test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: { baseURL: "http://localhost:3000", ...devices["Desktop Chrome"] },
  webServer: [
    { command: "python -m tests.e2e_server", cwd: "..", url: "http://localhost:8000/health/ready", reuseExistingServer: false, env: { IELTS_E2E_DATABASE_URL: databaseUrl } },
    { command: "npm run dev", url: "http://localhost:3000", reuseExistingServer: false, env: { NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000" } },
  ],
});