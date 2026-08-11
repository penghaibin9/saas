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

async function expectEitherVisible(first, second) {
  await expect.poll(async () => {
    return (await first.isVisible().catch(() => false)) || (await second.isVisible().catch(() => false))
  }, { timeout: 10000 }).toBe(true)
}

test.describe.serial('Golden rollout · message governance / delivery operations · Batch 15', () => {
  let adminApi

  test.beforeAll(async () => {
    adminApi = await loginApi(config.sandboxAdmin)
  })

  test('Message outbox governance workspace · Screenshot A frozen', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/messages/outbox')

    await expect(page).toHaveURL(/\/admin\/messages\/outbox/)
    await expect(page.getByRole('heading', { name: '发布记录', exact: true })).toBeVisible()
    const table = page.locator('.mc-table')
    const empty = page.getByText('暂无发布记录', { exact: true })
    await expectEitherVisible(table, empty)

    if (await table.isVisible().catch(() => false)) {
      await expect(table.locator('thead')).toContainText('标题')
      await expect(table.locator('thead')).toContainText('状态')
      await expect(table.locator('thead')).toContainText('已送达')
    }

    await capture(page, testInfo, 'rollout-message-governance-outbox-a')
  })

  test('Message template governance workspace · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openStaffWorkspace(page, adminApi, '/admin/messages/templates')

    await expect(page).toHaveURL(/\/admin\/messages\/templates/)
    await expect(page.getByRole('heading', { name: '消息模板', exact: true })).toBeVisible()
    await expect(page.locator('.mc-tpl')).toBeVisible()
    await expect(page.locator('.mc-toolbar')).toBeVisible()
    await expect(page.getByRole('button', { name: '新建模板', exact: true })).toBeVisible()
    await expectEitherVisible(page.locator('.mc-item').first(), page.getByText('暂无模板', { exact: true }))

    const visual = await page.locator('.mps:has(.mc-tpl)').evaluate((el) => {
      const toolbar = el.querySelector('.mc-toolbar')
      const input = toolbar?.querySelector('input')
      const emptyPanel = el.querySelector('.mc-tpl .ags-panel')
      const firstItem = el.querySelector('.mc-item')
      return {
        toolbarHeight: toolbar?.getBoundingClientRect().height || 0,
        toolbarRadius: parseFloat(getComputedStyle(toolbar).borderRadius) || 0,
        inputHeight: input?.getBoundingClientRect().height || 0,
        inputRadius: parseFloat(getComputedStyle(input).borderRadius) || 0,
        panelHeight: emptyPanel?.getBoundingClientRect().height || 0,
        panelRadius: emptyPanel ? (parseFloat(getComputedStyle(emptyPanel).borderRadius) || 0) : 0,
        itemRadius: firstItem ? (parseFloat(getComputedStyle(firstItem).borderRadius) || 0) : 0
      }
    })
    expect(visual.toolbarHeight).toBeGreaterThanOrEqual(50)
    expect(visual.toolbarHeight).toBeLessThanOrEqual(58)
    expect(visual.toolbarRadius).toBeGreaterThanOrEqual(10)
    expect(visual.inputHeight).toBeGreaterThanOrEqual(34)
    expect(visual.inputRadius).toBeGreaterThanOrEqual(8)
    if (visual.panelHeight) {
      expect(visual.panelHeight).toBeGreaterThanOrEqual(210)
      expect(visual.panelHeight).toBeLessThanOrEqual(235)
      expect(visual.panelRadius).toBeGreaterThanOrEqual(14)
    }
    if (visual.itemRadius) expect(visual.itemRadius).toBeGreaterThanOrEqual(13)

    await capture(page, testInfo, 'rollout-message-governance-templates-b')
  })

  // Delivery operations is intentionally not Golden-frozen in Batch 15.
  // The real page still exposes a `(partial)` maturity label and raw reconciliation JSON.
  // Those are product/content maturity debts, not visual defects; CSS must not hide them.
})
