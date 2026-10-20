import { defineConfig } from '@playwright/test'
import { assertSafeEnvironment, config } from './lib/config.mjs'
assertSafeEnvironment()
if (!process.env.PHONE_TEST_TENANT?.startsWith('phone-')) throw Error('Dedicated synthetic phone tenant required')
export default defineConfig({ testDir: './specs', testMatch: 'phone-local.spec.mjs', workers: 1, retries: 0,
  timeout: 120000, expect: { timeout: 15000 }, reporter: 'list', outputDir: './test-results/phone',
  use: { baseURL: config.staffBaseUrl, headless: true, locale: 'zh-CN', viewport: { width: 1440, height: 1000 },
    // Auth proof and password payloads must not enter HAR/trace/video artifacts.
    trace: 'off', video: 'off', screenshot: 'off', actionTimeout: 20000, navigationTimeout: 30000 } })
