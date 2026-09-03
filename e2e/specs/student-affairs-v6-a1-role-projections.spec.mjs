import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const ROUTE = '/admin/student-affairs/dashboard'
const DASHBOARD_API = /\/api\/v1\/student-affairs\/dashboard(?:\?|$)/
const PASSWORD = process.env.E2E_STUDENT_AFFAIRS_PASSWORD || 'E2eTest@2026'

async function loginAndOpen(page, username) {
  const responsePromise = page.waitForResponse((response) => DASHBOARD_API.test(response.url()) && response.request().method() === 'GET')
  await new StaffLoginPage(page, config.staffBaseUrl).login({
    tenant: config.sandboxAdmin.tenant,
    username,
    password: PASSWORD
  })
  await page.goto(`${config.staffBaseUrl}${ROUTE}`)
  const response = await responsePromise
  const body = await response.json()
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
  await expect(page.locator('.sa-v6-queue-row')).toHaveCount(7)
  for (const selector of ['.app-step-guide__mask', '.tour-mask']) {
    const mask = page.locator(selector)
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
    }
  }
  return body
}

async function capture(page, testInfo, label) {
  const file = testInfo.outputPath(`${label}.png`)
  await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(label, { path: file, contentType: 'image/png' })
}

for (const role of [
  { username: 'e2e_sa_admin', view: 'SA_ADMIN', label: '学工处（全校）', mode: 'ADMIN_TENANT' },
  { username: 'e2e_college_admin', view: 'COLLEGE_SA', label: '学院学工（本院）' },
  { username: 'e2e_counselor_a', view: 'COUNSELOR', label: '辅导员（本班）', mode: 'SCOPED' }
]) {
  test(`V6 A1 real ${role.view} projection and risk drilldown`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1366, height: 768 })
    const envelope = await loginAndOpen(page, role.username)
    expect(envelope.code).toBe(0)
    expect(envelope.data.view).toBe(role.view)
    expect(envelope.data.viewLabel).toBe(role.label)
    expect(envelope.data.scopeLabel).toEqual(expect.any(String))
    expect(envelope.data.scopeLabel.length).toBeGreaterThan(0)
    if (role.mode) expect(envelope.data.scopeMode).toBe(role.mode)
    else expect(envelope.data.scopeMode).not.toBe('NONE')
    await expect(page.locator('.sa-v6-scope-card')).toContainText(role.label)
    await expect(page.locator('.sa-v6-scope-card')).toContainText(envelope.data.scopeLabel)

    const geometry = await page.locator('[data-queue="riskStudents"]').evaluate((row) => {
      const rect = row.getBoundingClientRect()
      return { top: rect.top, bottom: rect.bottom, right: rect.right, viewportWidth: innerWidth }
    })
    expect(geometry.top).toBeLessThanOrEqual(290)
    expect(geometry.bottom).toBeLessThanOrEqual(768)
    expect(geometry.right).toBeLessThanOrEqual(geometry.viewportWidth)

    const risk = page.locator('[data-queue="riskStudents"]')
    await expect(risk).toBeEnabled()
    await risk.click()
    await expect.poll(() => new URL(page.url()).pathname).toBe('/admin/student-affairs/risk')
    await expect.poll(() => new URL(page.url()).searchParams.get('status')).toBe('OPEN')
    await page.goBack()
    await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
    await capture(page, testInfo, `v6-a1-role-${role.view.toLowerCase()}`)
  })
}
