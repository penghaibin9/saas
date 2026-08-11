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

test.describe.serial('Golden rollout · message campaign record / detail · Batch 17', () => {
  let adminApi
  let draft
  let title

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
    const rawRun = process.env.GITHUB_RUN_ID || `${Date.now()}`
    const runId = String(rawRun).replace(/\D/g, '').slice(-12) || String(Date.now()).slice(-12)
    title = `Playwright 校务通知治理 ${runId}`

    // Create one real DRAFT through the production API in the isolated E2E tenant.
    // No fake recipient, no publish bypass, and the whole database is discarded after the run.
    draft = await adminApi.post('/admin/message-campaigns', {
      title,
      contentPlain: '这是一条仅用于隔离浏览器验收的真实消息发布草稿，用于核验发布记录与发布详情的桌面信息层级。',
      summary: '隔离 E2E 发布记录与发布详情视觉证据',
      category: 'ANNOUNCEMENT',
      priority: 'NORMAL',
      requireAck: true,
      audiences: [],
      channels: ['IN_APP'],
      idempotencyKey: `pw-message-golden-${runId}`
    })
    expect(draft?.campaignId).toBeTruthy()
    expect(String(draft?.status || '').toUpperCase()).toBe('DRAFT')
  })

  test('Message outbox real data state · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/messages/outbox')

    await expect(page).toHaveURL(/\/admin\/messages\/outbox/)
    await expect(page.getByRole('heading', { name: '发布记录', exact: true })).toBeVisible()
    const table = page.locator('.mc-table')
    await expect(table).toBeVisible()
    await expect(table.locator('thead')).toContainText('标题')
    await expect(table.locator('thead')).toContainText('状态')
    await expect(table.locator('thead')).toContainText('已送达')

    const row = table.locator('tbody tr').filter({ hasText: title }).first()
    await expect(row).toBeVisible()
    await expect(row).toContainText('草稿')
    await expect(row).toContainText('公告')
    await expect(row).toContainText('普通')
    await expect(row.getByRole('button', { name: '详情', exact: true })).toBeVisible()

    await capture(page, testInfo, 'rollout-message-campaign-outbox-a')
  })

  test('Message campaign real draft detail · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, `/admin/messages/outbox/${draft.campaignId}`)

    await expect(page).toHaveURL(new RegExp(`/admin/messages/outbox/${draft.campaignId}`))
    await expect(page.getByRole('heading', { name: '发布详情', exact: true })).toBeVisible()
    await expect(page.locator('.mc-detail')).toBeVisible()
    await expect(page.locator('.mc-detail h2')).toHaveText(title)
    await expect(page.locator('.mc-meta')).toContainText('状态 草稿')
    await expect(page.locator('.mc-meta')).toContainText('接收 0')
    await expect(page.locator('.mc-body')).toContainText('隔离浏览器验收')
    await expect(page.getByRole('button', { name: '返回列表', exact: true })).toBeVisible()

    await capture(page, testInfo, 'rollout-message-campaign-detail-a')
  })
})
