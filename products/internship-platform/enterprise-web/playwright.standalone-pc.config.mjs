import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e-surfaces',
  outputDir: 'test-results-surfaces',
  timeout: 35_000,
  expect: { timeout: 10_000 },
  retries: 0,
  workers: 1,
  use: {
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: [
    {
      command: 'npm --prefix ../admin-web run dev -- --host 127.0.0.1 --port 5176',
      url: 'http://127.0.0.1:5176/login',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npm --prefix ../student-web run dev -- --host 127.0.0.1 --port 5201',
      url: 'http://127.0.0.1:5201/student/login',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
