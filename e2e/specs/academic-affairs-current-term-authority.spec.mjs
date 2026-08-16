import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loginApi } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

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

function waitForBrowserRefresh(page, timeout = 20_000) {
  return page.waitForResponse(
    (response) => response.url().includes('/api/v1/auth/browser-refresh') &&
      response.request().method() === 'POST' && response.status() === 200,
    { timeout }
  )
}

async function dismissPageOperationGuide(page) {
  const guide = page.getByRole('dialog', { name: '页面操作引导' })
  if (!(await guide.isVisible({ timeout: 1_000 }).catch(() => false))) return
  const skip = guide.getByRole('button', { name: '跳过引导' })
  if (await skip.isVisible({ timeout: 1_000 }).catch(() => false)) await skip.click()
}

async function openAcademicW1StaffPage(page, path) {
  // The dedicated academic-w1-school exists only in the isolated Playwright database. Keeping the
  // term mutations here prevents this Gold from changing demo-school (read-only) or sandbox-school,
  // which later graduation/schedule/grade/internship Gold suites share in the same serial run.
  await new StaffLoginPage(page, config.staffBaseUrl).login(config.academicW1Admin)
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })

  const targetUrl = new URL(path, config.staffBaseUrl).toString()
  const refresh = waitForBrowserRefresh(page)
  await page.goto(targetUrl)
  await refresh
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
  await dismissPageOperationGuide(page)
}

async function reloadWithBrowserSession(page) {
  const refresh = waitForBrowserRefresh(page)
  await page.reload()
  await refresh
  await page.locator('.uchip__role').first().waitFor({ state: 'visible', timeout: 20_000 })
}

function renderedTermLabel(term) {
  return `${term.yearCode} 第 ${term.termNo} 学期`
}

function termRow(page, term) {
  return page.locator('.aa-current-item').filter({ hasText: renderedTermLabel(term) }).first()
}

async function createPublishedTerm(api, { year, termName, teachingWeeks }) {
  const created = await api.post('/academic-affairs/terms', {
    yearCode: `${year}-${year + 1}`,
    termNo: 1,
    termName,
    startDate: `${year}-09-01`,
    endDate: `${year + 1}-01-31`,
    teachingWeeks,
    examWeekStart: teachingWeeks - 1
  })
  return api.post(`/academic-affairs/terms/${created.termId}/publish`, {})
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

async function currentGovernance(api) {
  return api.get('/system/academic-calendars/current', { module: 'ACADEMIC_AFFAIRS' })
}

async function closeActiveGovernance(api, current, reason) {
  if (!current?.hasCurrent || !current?.termId) return null
  return api.post(`/system/academic-calendars/${current.termId}/transition`, {
    targetStatus: 'CLOSING',
    reason,
    expectedVersion: Number(current.version || 0),
    force: true
  })
}

async function restoreAcademicW1State(api, { originalCurrent, legacyBaseTerm, governanceTerm }) {
  // Never leave SYS-12 ACTIVE after this spec. CLOSING is the formal state-machine exit and
  // force=true only bypasses closing blockers; it does not bypass the transition graph.
  const activeNow = await currentGovernance(api)
  if (activeNow?.hasCurrent) {
    await closeActiveGovernance(api, activeNow, 'A-W1 Playwright 清理测试激活学期')
  }

  // The isolated A-W1 tenant deliberately starts without term facts. There is no formal
  // "unset current" or Term delete command, so when this spec creates its own legacy base we keep
  // that low-year term as this dedicated tenant's sole PUBLISHED current instead of deleting facts
  // with raw SQL or contaminating sandbox-school.
  const restoreTargetId = originalCurrent?.termId || legacyBaseTerm?.termId
  if (restoreTargetId) {
    await api.post(`/academic-affairs/terms/${restoreTargetId}/set-current`, {})
  }

  if (governanceTerm?.termId && String(governanceTerm.termId) !== String(restoreTargetId || '')) {
    const row = await api.get(`/academic-affairs/terms/${governanceTerm.termId}`)
    if (row?.status === 'PUBLISHED') {
      await api.post(`/academic-affairs/terms/${governanceTerm.termId}/freeze`, {})
    }
  }

  const restoredGovernance = await currentGovernance(api)
  if (restoredGovernance?.hasCurrent) {
    throw new Error(`A-W1 cleanup left an ACTIVE governance row: ${JSON.stringify(restoredGovernance)}`)
  }
  const restored = await api.get('/academic-affairs/terms/current')
  if (String(restored?.termId || '') !== String(restoreTargetId || '')) {
    throw new Error(`A-W1 cleanup did not restore isolated current term: ${JSON.stringify(restored)}`)
  }
  if (restored?.currentAuthority !== 'AA_TERM_COMPAT') {
    throw new Error(`A-W1 cleanup did not restore legacy authority: ${JSON.stringify(restored)}`)
  }
}

test('A-W1 current term: legacy real click persists, then governance removes the bypass', async ({ page }, testInfo) => {
  const api = await loginApi(config.academicW1Admin)
  const suffix = `${process.env.GITHUB_RUN_ID || 'local'}-r${testInfo.retry}`
  const originalCurrent = await api.get('/academic-affairs/terms/current')
  const originalGovernance = await currentGovernance(api)
  let legacyBaseTerm = null
  let governanceTerm = null

  expect(originalCurrent?.currentAuthority).toBe('AA_TERM_COMPAT')
  expect(
    originalGovernance?.hasCurrent,
    `academic-w1-school must begin without SYS-12 ACTIVE governance: ${JSON.stringify(originalGovernance)}`
  ).toBeFalsy()

  try {
    // The minimal dedicated tenant has no term by design. Build a low-year legacy current through
    // the same formal APIs used in production instead of depending on a rich demo/sandbox seeder.
    let legacyCurrent = originalCurrent
    if (!legacyCurrent?.termId) {
      legacyBaseTerm = await createPublishedTerm(api, {
        year: 2008 + testInfo.retry * 4,
        termName: `A-W1 兼容基准学期 ${suffix}`,
        teachingWeeks: 17
      })
      legacyCurrent = await api.get('/academic-affairs/terms/current')
      expect(String(legacyCurrent?.termId || '')).toBe(String(legacyBaseTerm.termId))
      expect(legacyCurrent?.currentAuthority).toBe('AA_TERM_COMPAT')
    }

    const legacyName = legacyCurrent.termName || renderedTermLabel(legacyCurrent)

    // Publishing a second low-year term makes the legacy base a real non-current PUBLISHED row,
    // giving the browser a visible "设为当前" action to exercise.
    governanceTerm = await createPublishedTerm(api, {
      year: 2010 + testInfo.retry * 4,
      termName: `A-W1 统一治理学期 ${suffix}`,
      teachingWeeks: 20
    })
    const governanceName = governanceTerm.termName

    await openAcademicW1StaffPage(page, '/admin/academic-affairs/terms/current')
    await expect(page.getByRole('heading', { name: '当前学期' }).first()).toBeVisible()
    await expect(page.getByText('暂保留教务当前学期兼容切换', { exact: false })).toBeVisible()
    await expect(termRow(page, governanceTerm)).toBeVisible()

    // Formal current switch under test: visible button -> shared confirmation component -> real POST.
    const legacyRow = termRow(page, legacyCurrent)
    await expect(legacyRow).toBeVisible()
    const setCurrent = legacyRow.getByRole('button', { name: '设为当前' })
    await expect(setCurrent).toBeEnabled()
    await setCurrent.click()

    // AppConfirmDialog currently has role=dialog but no aria-label/aria-labelledby. Scope by its
    // real DOM + visible title instead of pretending it has an accessible dialog name.
    const dialog = page.locator('.app-confirm-dialog').filter({ hasText: '切换当前学期' }).first()
    await expect(dialog).toBeVisible()
    await expect(dialog.locator('.app-confirm-dialog__title')).toHaveText('切换当前学期')
    const switchResponse = page.waitForResponse(
      (response) => response.url().includes(`/api/v1/academic-affairs/terms/${legacyCurrent.termId}/set-current`) &&
        response.request().method() === 'POST',
      { timeout: 20_000 }
    )
    await dialog.getByRole('button', { name: '确认切换' }).click()
    const switched = await switchResponse
    expect(switched.status()).toBe(200)
    const switchedBody = await switched.json()
    expect(switchedBody.code).toBe(0)

    await expect(page.locator('.aa-current-card__sub')).toHaveText(legacyName)
    await expect(termRow(page, legacyCurrent).getByText('当前学期', { exact: true })).toBeVisible()
    await capture(page, testInfo, 'a-w1-current-term-legacy-after-visible-click')

    // Full document refresh reconstructs auth from the real HttpOnly browser session and rereads
    // the current term from MySQL; in-memory-only success cannot pass this assertion.
    await reloadWithBrowserSession(page)
    await expect(page.locator('.aa-current-card__sub')).toHaveText(legacyName)
    await expect(termRow(page, legacyCurrent).getByText('当前学期', { exact: true })).toBeVisible()

    const activated = await activateGovernance(api, governanceTerm.termId)
    expect(activated.governanceStatus).toBe('ACTIVE')

    await reloadWithBrowserSession(page)
    await expect(page.locator('.aa-current-card__sub')).toHaveText(governanceName)
    await expect(page.getByText('全校统一治理已启用', { exact: true })).toBeVisible()
    await expect(page.getByText(/教务侧只读当前结论/)).toBeVisible()

    const oldRow = termRow(page, legacyCurrent)
    await expect(oldRow).toBeVisible()
    await expect(oldRow.getByRole('button', { name: '设为当前' })).toHaveCount(0)
    await expect(oldRow.getByText('统一治理切换', { exact: true })).toBeVisible()
    await capture(page, testInfo, 'a-w1-current-term-governance-no-bypass')

    // The remaining visible action must lead to the existing SYS-12 owner, not write AaTerm here.
    await page.getByRole('button', { name: '前往学年学期与业务日历' }).click()
    await expect(page).toHaveURL(/\/admin\/system\/academic-calendar(?:\?|$)/)
    await expect(page.getByText('学年学期与业务日历', { exact: false }).first()).toBeVisible()
  } finally {
    await restoreAcademicW1State(api, { originalCurrent, legacyBaseTerm, governanceTerm })
  }
})