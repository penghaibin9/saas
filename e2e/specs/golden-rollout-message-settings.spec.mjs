import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'

const VIEWPORT = { width: 1440, height: 1000 }

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function settleVisual(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

async function capture(page, testInfo, name) {
  await dismissGuide(page)
  await settleVisual(page)
  const viewportPath = testInfo.outputPath(`${name}-1440x1000.png`)
  const fullPath = testInfo.outputPath(`${name}-full.png`)
  await page.screenshot({ path: viewportPath, fullPage: false, animations: 'disabled', caret: 'hide' })
  await page.screenshot({ path: fullPath, fullPage: true, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-viewport`, { path: viewportPath, contentType: 'image/png' })
  await testInfo.attach(`${name}-full`, { path: fullPath, contentType: 'image/png' })
}

async function openStaffWorkspace(page, api, path) {
  await page.addInitScript((token) => {
    window.sessionStorage.setItem('gx_pc_token_v1', token)
  }, api.token)
  await page.goto(`${config.staffBaseUrl}${path}`)
  await dismissGuide(page)
}

test.describe.serial('Golden rollout · message preferences / channel governance · Batch 16', () => {
  let adminApi

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
  })

  test('Message settings workspace · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/messages/settings')

    await expect(page).toHaveURL(/\/admin\/messages\/settings/)
    await expect(page.getByRole('heading', { name: '消息设置', exact: true })).toBeVisible()
    await expect(page.locator('.mc-settings')).toBeVisible()
    await expect(page.locator('.mc-settings .mc-panel')).toHaveCount(4)
    await expect(page.getByText('分类偏好', { exact: true })).toBeVisible()
    await expect(page.getByText('渠道', { exact: true })).toBeVisible()
    await expect(page.getByText('静默时段', { exact: true })).toBeVisible()
    await expect(page.getByText('发布频控', { exact: true })).toBeVisible()

    await capture(page, testInfo, 'rollout-message-settings-a')
  })
})
