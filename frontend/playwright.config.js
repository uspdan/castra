// @ts-check
import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright config for the seige-range frontend E2E suite.
 *
 * Phase 12 (slice 20). The tests assume the full stack is running —
 * either via `make dev` (docker-compose up) on localhost:80 fronted by
 * nginx, or via the dev workflow `vite --host 0.0.0.0` on :5173 with
 * the API at :8000. Override the target with the `E2E_BASE_URL`
 * environment variable.
 *
 * Tests are deliberately light on parallelism (workers=1) so we don't
 * race on shared user / challenge state in the database — the suite
 * registers fresh users per test (see fixtures.js) but admin actions
 * touch global rows.
 */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: /.*\.spec\.js$/,
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['html'], ['list']] : 'list',
  timeout: 30_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:8080',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    headless: true,
    // The dev compose has nginx terminating TLS only optionally;
    // accept self-signed cert by default so CI can run against a
    // staging-like compose without extra plumbing.
    ignoreHTTPSErrors: true,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  outputDir: 'test-results/',
})
