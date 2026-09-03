import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const ROUTE = '/admin/student-affairs/dashboard'
const DASHBOARD_API = /\/api\/v1\/student-affairs\/dashboard(?:\?|$)/
const AUDIT_API = /\/api\/v1\/audit\/logs(?:\?|$)/

async function login(page) {
  await page.setViewportSize({ width: 1366, height: 768 })
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
}

async function dismissGuide(page) {
  for (const selector of ['.app-step-guide__mask', '.tour-mask']) {
    const mask = page.locator(selector)
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
    }
  }
}

async function capture(page, testInfo, label) {
  const file = testInfo.outputPath(`${label}.png`)
  await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(label, { path: file, contentType: 'image/png' })
}

async function fulfillFromReal(route, transform) {
  const response = await route.fetch()
  const envelope = await response.json()
  expect(envelope.code).toBe(0)
  transform(envelope)
  await route.fulfill({ response, json: envelope })
}

test('V6 A1 loading state never flashes old work data', async ({ page }, testInfo) => {
  await login(page)
  let release
  const gate = new Promise((resolve) => { release = resolve })
  await page.route(DASHBOARD_API, async (route) => {
    await gate
    const response = await route.fetch()
    await route.fulfill({ response })
  })
  const navigation = page.goto(`${config.staffBaseUrl}${ROUTE}`)
  await expect(page.locator('.sa-v6-page-shell')).toContainText('正在加载学工今日工作真实数据…')
  await expect(page.locator('.sa-v6-dashboard')).toHaveCount(0)
  await capture(page, testInfo, 'v6-a1-state-loading')
  release()
  await navigation
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
})

test('V6 A1 empty summary is distinct from zero-valued ready data', async ({ page }, testInfo) => {
  await login(page)
  await page.route(DASHBOARD_API, (route) => fulfillFromReal(route, (envelope) => {
    envelope.data.summaryCards = []
  }))
  await page.goto(`${config.staffBaseUrl}${ROUTE}`)
  await expect(page.locator('.sa-v6-dashboard')).toHaveCount(0)
  await expect(page.locator('.sa-v6-page-shell')).toContainText('当前范围暂无可展示的学工汇总')
  await capture(page, testInfo, 'v6-a1-state-empty')
})

test('V6 A1 no-scope response fails closed in the real browser', async ({ page }, testInfo) => {
  await login(page)
  await page.route(DASHBOARD_API, (route) => fulfillFromReal(route, (envelope) => {
    envelope.data.scopeMode = 'NONE'
    envelope.data.scopeType = 'NONE'
    envelope.data.scopeLabel = '无数据范围'
  }))
  await page.goto(`${config.staffBaseUrl}${ROUTE}`)
  await expect(page.locator('.sa-v6-dashboard')).toHaveCount(0)
  await expect(page.locator('.sa-v6-page-shell')).toContainText('当前账号未配置学工数据范围')
  await expect(page.locator('.sa-v6-page-shell')).toContainText('配置负责学院、班级或学生范围')
  await capture(page, testInfo, 'v6-a1-state-no-scope')
})

for (const failure of [
  {
    status: 403,
    code: 403001,
    title: '当前身份无权查看学工今日工作',
    safeCopy: /没有.*权限|无权/,
    label: 'forbidden'
  },
  {
    status: 503,
    code: 503001,
    title: '学工今日工作加载失败',
    safeCopy: /系统服务暂时不可用|稍后重试/,
    label: 'error'
  }
]) {
  test(`V6 A1 ${failure.label} response has an honest and sanitized full-page state`, async ({ page }, testInfo) => {
    await login(page)
    await page.route(DASHBOARD_API, async (route) => {
      await route.fulfill({
        status: failure.status,
        contentType: 'application/json',
        body: JSON.stringify({ code: failure.code, message: `E2E ${failure.label}` })
      })
    })
    await page.goto(`${config.staffBaseUrl}${ROUTE}`)
    const shell = page.locator('.sa-v6-page-shell')
    await expect(page.locator('.sa-v6-dashboard')).toHaveCount(0)
    await expect(shell).toContainText(failure.title)
    await expect(shell).toContainText(failure.safeCopy)
    await expect(shell).not.toContainText(`E2E ${failure.label}`)
    await capture(page, testInfo, `v6-a1-state-${failure.label}`)
  })
}

test('V6 A1 audit failure is an explicit local degradation', async ({ page }, testInfo) => {
  await login(page)
  await page.route(AUDIT_API, async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ code: 503001, message: 'E2E audit unavailable' })
    })
  })
  await page.goto(`${config.staffBaseUrl}${ROUTE}`)
  await dismissGuide(page)
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
  await expect(page.locator('.sa-dashboard-panel--audit')).toContainText('操作记录暂不可用')
  await expect(page.locator('.sa-dashboard-panel--audit')).not.toContainText('暂无可展示审计记录')
  await capture(page, testInfo, 'v6-a1-state-audit-degraded')
})
