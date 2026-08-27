import { defineConfig, devices } from '@playwright/test'
import { assertSafeEnvironment, config } from './lib/config.mjs'

assertSafeEnvironment()
if (process.env.E2E_SELF_SIGNED_TLS !== 'true') {
  throw new Error('S1 isolated TLS requires E2E_SELF_SIGNED_TLS=true; do not silently ignore certificate errors')
}

export default defineConfig({
  testDir: './specs',
  outputDir: './test-results/artifacts',
  timeout: 180_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['junit', { outputFile: 'test-results/junit.xml' }]
  ],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: config.staffBaseUrl,
    headless: true,
    actionTimeout: 20_000,
    navigationTimeout: 60_000,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
    // CI terminates TLS at the same nginx topology as production, but uses an
    // isolated self-signed certificate because no public CA can validate 127.0.0.1.
    // This opt-in config is dedicated to S1 and must never become the shared E2E default.
    ignoreHTTPSErrors: true,
  }
})
