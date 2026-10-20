import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e-fullstack',
  outputDir: 'test-results-fullstack-pc',
  timeout: 45_000,
  expect: { timeout: 12_000 },
  retries: 0,
  workers: 1,
  use: {
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: [
    {
      command: 'VITE_PROXY_TARGET=http://127.0.0.1:8000 VITE_ALLOW_MOCK_FALLBACK=false npm --prefix ../admin-web run dev -- --host 127.0.0.1 --port 5176',
      url: 'http://127.0.0.1:5176/login',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'VITE_PROXY_TARGET=http://127.0.0.1:8000 npm --prefix ../student-web run dev -- --host 127.0.0.1 --port 5201',
      url: 'http://127.0.0.1:5201/student/login',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
