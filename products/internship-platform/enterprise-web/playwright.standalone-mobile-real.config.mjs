import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e-surfaces',
  testMatch: /standalone-mobile-real\.spec\.mjs/,
  outputDir: 'test-results-mobile-real',
  timeout: 45_000,
  expect: { timeout: 12_000 },
  retries: 0,
  workers: 1,
  use: {
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: {
    command: 'npm --prefix ../mobile run dev:h5 -- --host 127.0.0.1 --port 5203',
    url: 'http://127.0.0.1:5203/',
    reuseExistingServer: false,
    timeout: 90_000,
    env: {
      VITE_PROXY_TARGET: 'http://127.0.0.1:8000',
      VITE_API_BASE_URL: 'http://127.0.0.1:8000'
    }
  },
})
