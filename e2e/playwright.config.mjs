import { defineConfig, devices } from '@playwright/test'
import { assertSafeEnvironment, config } from './lib/config.mjs'

assertSafeEnvironment()

export default defineConfig({
  testDir: './specs',
  outputDir: './test-results/artifacts',
  timeout: 180_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['junit', { outputFile: 'test-results/junit.xml' }]
  ],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: config.staffBaseUrl,
    headless: process.env.PW_HEADED !== 'true',
    actionTimeout: 20_000,
    navigationTimeout: 60_000,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
    ignoreHTTPSErrors: false
  }
})
