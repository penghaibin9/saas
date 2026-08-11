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

test.describe.serial('Golden rollout · message center / communication · Batch 14', () => {
  let adminApi

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
  })

  test('Message inbox workspace · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/messages/inbox')

    await expect(page).toHaveURL(/\/admin\/messages\/inbox/)
    await expect(page.getByRole('heading', { name: '我的消息', exact: true })).toBeVisible()
    await expect(page.locator('.mc-inbox')).toBeVisible()
    await expect(page.locator('.mc-inbox__nav')).toBeVisible()
    await expect(page.locator('.mc-inbox__list')).toBeVisible()
    await expect(page.locator('.mc-inbox__detail')).toBeVisible()
    await expect(page.getByText('加载消息…', { exact: true })).toHaveCount(0)

    await capture(page, testInfo, 'rollout-message-center-inbox-a')
  })

  test('Message compose workspace · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/messages/compose')

    await expect(page).toHaveURL(/\/admin\/messages\/compose/)
    await expect(page.getByRole('heading', { name: '通知发布', exact: true })).toBeVisible()
    await expect(page.locator('.mc-compose')).toBeVisible()
    await expect(page.locator('.mc-steps')).toBeVisible()
    await expect(page.locator('.mc-card').first()).toBeVisible()
    await expect(page.locator('.mc-steps li.is-on')).toContainText('1 内容')
    await expect(page.getByRole('button', { name: '下一步', exact: true }).first()).toBeVisible()

    await capture(page, testInfo, 'rollout-message-center-compose-a')
  })

  test('Message delivery statistics workspace · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/messages/statistics')

    await expect(page).toHaveURL(/\/admin\/messages\/statistics/)
    await expect(page.getByRole('heading', { name: '发送统计', exact: true })).toBeVisible()
    await expect(page.locator('.mc-stats')).toBeVisible()
    await expect(page.locator('.mc-grid')).toBeVisible()
    await expect(page.locator('.mc-grid .mc-card')).toHaveCount(6)
    await expect(page.getByText('按状态', { exact: true })).toBeVisible()
    await expect(page.getByText('按类型', { exact: true })).toBeVisible()
    await expect(page.getByText('渠道状态', { exact: true })).toBeVisible()

    await capture(page, testInfo, 'rollout-message-center-statistics-a')
  })
})
