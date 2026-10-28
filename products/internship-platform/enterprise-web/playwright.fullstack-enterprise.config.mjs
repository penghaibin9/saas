import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e-fullstack-enterprise',
  outputDir: 'test-results-fullstack-enterprise',
  timeout: 45_000,
  expect: { timeout: 12_000 },
  retries: 0,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5202/enterprise/',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: {
    command: 'VITE_PROXY_TARGET=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5202',
    url: 'http://127.0.0.1:5202/enterprise/',
    reuseExistingServer: false,
    timeout: 60_000,
  },
})
