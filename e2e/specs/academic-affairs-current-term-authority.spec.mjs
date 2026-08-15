import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'
import { openGoldenStaffPage } from '../lib/golden-staff-page.mjs'

async function capture(page, testInfo, name, width = 1440, height = 900) {
  await page.setViewportSize({ width, height })
  await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {})
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  const path = testInfo.outputPath(`${name}-${width}x${height}.png`)
  await page.screenshot({ path, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-${width}x${height}`, { path, contentType: 'image/png' })
}

async function reloadWithBrowserSession(page) {
  const refresh = page.waitForResponse(
    (response) => response.url().includes('/api/v1/auth/browser-refresh') &&
      response.request().method() === 'POST' && response.status() === 200,
    { timeout: 20_000 }
  )
  await page.reload()
  await refresh
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
}

function termRow(page, termName) {
  return page.locator('.aa-current-item').filter({ hasText: termName }).first()
}

async function createPublishedTerm(api, { year, termName, teachingWeeks }) {
  const created = await api.post('/academic-affairs/terms', {
    yearCode: `${year}-${year + 1}`,
    termNo: 1,
    termName,
    startDate: `${year}-09-01`,
    endDate: `${year + 1}-01-31`,
    teachingWeeks,
    examWeekStart: teachingWeeks > 17 ? teachingWeeks - 1 : teachingWeeks
  })
  await api.post(`/academic-affairs/terms/${created.termId}/publish`, {})
  return created
}

async function activateGovernance(api, termId) {
  const enrolled = await api.post(`/system/academic-calendars/${termId}/enroll`, {
    timezone: 'Asia/Shanghai'
  })
  const validated = await api.post(`/system/academic-calendars/${termId}/transition`, {
    targetStatus: 'VALIDATED',
    reason: 'A-W1 Playwright 当前学期统一治理验收',
    expectedVersion: Number(enrolled.version || 0)
  })
  return api.post(`/system/academic-calendars/${termId}/transition`, {
    targetStatus: 'ACTIVE',
    reason: 'A-W1 Playwright 当前学期统一治理验收',
    expectedVersion: Number(validated.version || 0)
  })
}

test('A-W1 current term: legacy real click persists, then governance removes the bypass', async ({ page }, testInfo) => {
  const api = await loginApi(config.sandboxAdmin)
  const yearBase = 2094 + testInfo.retry * 4
  const suffix = `${process.env.GITHUB_RUN_ID || 'local'}-r${testInfo.retry}`
  const legacyName = `A-W1 兼容当前学期 ${suffix}`
  const governanceName = `A-W1 统一治理学期 ${suffix}`

  // Fixture setup may use the real API; the formal current switch below must be a visible browser click.
  const legacyTerm = await createPublishedTerm(api, {
    year: yearBase,
    termName: legacyName,
    teachingWeeks: 17
  })
  const governanceTerm = await createPublishedTerm(api, {
    year: yearBase + 1,
    termName: governanceName,
    teachingWeeks: 20
  })

  await openGoldenStaffPage(page, '/admin/academic-affairs/terms/current')
  await expect(page.getByRole('heading', { name: '当前学期' }).first()).toBeVisible()
  await expect(page.getByText('暂保留教务当前学期兼容切换', { exact: false })).toBeVisible()
  await expect(page.getByText(governanceName, { exact: true })).toBeVisible()

  const legacyRow = termRow(page, legacyName)
  await expect(legacyRow).toBeVisible()
  const setCurrent = legacyRow.getByRole('button', { name: '设为当前' })
  await expect(setCurrent).toBeEnabled()
  await setCurrent.click()

  const dialog = page.getByRole('dialog', { name: '切换当前学期' })
  await expect(dialog).toBeVisible()
  const switchResponse = page.waitForResponse(
    (response) => response.url().includes(`/api/v1/academic-affairs/terms/${legacyTerm.termId}/set-current`) &&
      response.request().method() === 'POST',
    { timeout: 20_000 }
  )
  await dialog.getByRole('button', { name: '确认切换' }).click()
  const switched = await switchResponse
  expect(switched.status()).toBe(200)
  const switchedBody = await switched.json()
  expect(switchedBody.code).toBe(0)

  await expect(page.locator('.aa-current-card__sub')).toHaveText(legacyName)
  await expect(termRow(page, legacyName).getByText('当前学期', { exact: true })).toBeVisible()
  await capture(page, testInfo, 'a-w1-current-term-legacy-after-visible-click')

  // A full document refresh must reconstruct auth from the real HttpOnly browser session and
  // reread the same current term from MySQL.
  await reloadWithBrowserSession(page)
  await expect(page.locator('.aa-current-card__sub')).toHaveText(legacyName)
  await expect(termRow(page, legacyName).getByText('当前学期', { exact: true })).toBeVisible()

  const activated = await activateGovernance(api, governanceTerm.termId)
  expect(activated.governanceStatus).toBe('ACTIVE')

  await reloadWithBrowserSession(page)
  await expect(page.locator('.aa-current-card__sub')).toHaveText(governanceName)
  await expect(page.getByText('全校统一治理已启用', { exact: true })).toBeVisible()
  await expect(page.getByText(/教务侧只读当前结论/)).toBeVisible()

  const oldRow = termRow(page, legacyName)
  await expect(oldRow).toBeVisible()
  await expect(oldRow.getByRole('button', { name: '设为当前' })).toHaveCount(0)
  await expect(oldRow.getByText('统一治理切换', { exact: true })).toBeVisible()
  await capture(page, testInfo, 'a-w1-current-term-governance-no-bypass')

  // The remaining visible action must lead to the existing SYS-12 owner, not write AaTerm here.
  await page.getByRole('button', { name: '前往学年学期与业务日历' }).click()
  await expect(page).toHaveURL(/\/admin\/system\/academic-calendar(?:\?|$)/)
  await expect(page.getByText('学年学期与业务日历', { exact: false }).first()).toBeVisible()
})
