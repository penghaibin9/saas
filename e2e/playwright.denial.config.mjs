import { defineConfig } from '@playwright/test'
import { assertSafeEnvironment, config } from './lib/config.mjs'

assertSafeEnvironment()
for (const key of ['E2E_DENIAL_TENANT', 'E2E_DENIAL_USERNAME', 'E2E_DENIAL_PASSWORD']) {
  if (!process.env[key]) throw new Error(`${key} is required for the isolated denial scenario`)
}
export default defineConfig({
  testDir: './specs', testMatch: 'load-denial.spec.mjs', workers: 1, retries: 0,
  timeout: 90000, expect: { timeout: 15000 }, reporter: 'list',
  outputDir: './test-results/denial',
  use: { baseURL: config.staffBaseUrl, headless: true, locale: 'zh-CN',
    viewport: { width: 1440, height: 1000 }, trace: 'off', video: 'off', screenshot: 'off' }
})
