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
    examWeekStart: teachingWeeks - 1
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

async function restoreSandboxState(api, {
  originalCurrent,
  originalGovernance,
  originalGovernanceClosing,
  testTerm
}) {
  // Never leave the A-W1 governance term ACTIVE for later graduation/schedule/grade specs.
  const activeNow = await currentGovernance(api)
  if (activeNow?.hasCurrent && String(activeNow.termId) !== String(originalGovernance?.termId || '')) {
    await closeActiveGovernance(api, activeNow, 'A-W1 Playwright 清理测试激活学期')
  }

  if (originalGovernance?.hasCurrent) {
    const currentAfterCleanup = await currentGovernance(api)
    if (!currentAfterCleanup?.hasCurrent || String(currentAfterCleanup.termId) !== String(originalGovernance.termId)) {
      if (!originalGovernanceClosing) {
        throw new Error('A-W1 cleanup lost the original governance version snapshot')
      }
      await api.post(`/system/academic-calendars/${originalGovernance.termId}/transition`, {
        targetStatus: 'ACTIVE',
        reason: 'A-W1 Playwright 恢复原全校当前学期',
        expectedVersion: Number(originalGovernanceClosing.version || 0)
      })
    }
  } else if (originalCurrent?.termId) {
    await api.post(`/academic-affairs/terms/${originalCurrent.termId}/set-current`, {})
  }

  // The fixture term is deliberately old and frozen after use so later default/current pickers
  // neither select it nor treat it as another live semester.
  if (testTerm?.termId) {
    await api.post(`/academic-affairs/terms/${testTerm.termId}/freeze`, {})
  }

  const restored = await api.get('/academic-affairs/terms/current')
  if (String(restored?.termId || '') !== String(originalCurrent?.termId || '')) {
    throw new Error(`A-W1 cleanup did not restore original current term: ${JSON.stringify(restored)}`)
  }
  if (originalGovernance?.hasCurrent && restored?.currentAuthority !== 'CALENDAR_GOVERNANCE') {
    throw new Error(`A-W1 cleanup did not restore governance authority: ${JSON.stringify(restored)}`)
  }
  if (!originalGovernance?.hasCurrent && restored?.currentAuthority !== 'AA_TERM_COMPAT') {
    throw new Error(`A-W1 cleanup did not restore legacy authority: ${JSON.stringify(restored)}`)
  }
}

test('A-W1 current term: legacy real click persists, then governance removes the bypass', async ({ page }, testInfo) => {
  const api = await loginApi(config.sandboxAdmin)
  const suffix = `${process.env.GITHUB_RUN_ID || 'local'}-r${testInfo.retry}`
  const governanceName = `A-W1 统一治理学期 ${suffix}`
  const originalCurrent = await api.get('/academic-affairs/terms/current')
  const originalGovernance = await currentGovernance(api)
  let originalGovernanceClosing = null
  let testTerm = null

  expect(originalCurrent?.termId, `sandbox must start with a current academic term: ${JSON.stringify(originalCurrent)}`).toBeTruthy()
  const originalName = originalCurrent.termName || `${originalCurrent.yearCode} 第 ${originalCurrent.termNo} 学期`

  try {
    // If another spec/seed ever starts using SYS-12, temporarily leave ACTIVE so the compatibility
    // click can still be proven, then restore that exact governance row in finally.
    if (originalGovernance?.hasCurrent) {
      originalGovernanceClosing = await closeActiveGovernance(
        api,
        originalGovernance,
        'A-W1 Playwright 临时进入兼容切换验收'
      )
    }

    // Only one low-year fixture term is added. Publishing it makes the original seed term a real
    // non-current PUBLISHED candidate without manufacturing a second long-lived school timeline.
    testTerm = await createPublishedTerm(api, {
      year: 2016 + testInfo.retry * 2,
      termName: governanceName,
      teachingWeeks: 20
    })

    await openGoldenStaffPage(page, '/admin/academic-affairs/terms/current')
    await expect(page.getByRole('heading', { name: '当前学期' }).first()).toBeVisible()
    await expect(page.getByText('暂保留教务当前学期兼容切换', { exact: false })).toBeVisible()
    await expect(termRow(page, governanceName)).toBeVisible()

    // This is the formal current switch under test: it must happen through visible controls.
    const originalRow = termRow(page, originalName)
    await expect(originalRow).toBeVisible()
    const setCurrent = originalRow.getByRole('button', { name: '设为当前' })
    await expect(setCurrent).toBeEnabled()
    await setCurrent.click()

    const dialog = page.getByRole('dialog', { name: '切换当前学期' })
    await expect(dialog).toBeVisible()
    const switchResponse = page.waitForResponse(
      (response) => response.url().includes(`/api/v1/academic-affairs/terms/${originalCurrent.termId}/set-current`) &&
        response.request().method() === 'POST',
      { timeout: 20_000 }
    )
    await dialog.getByRole('button', { name: '确认切换' }).click()
    const switched = await switchResponse
    expect(switched.status()).toBe(200)
    const switchedBody = await switched.json()
    expect(switchedBody.code).toBe(0)

    await expect(page.locator('.aa-current-card__sub')).toHaveText(originalName)
    await expect(termRow(page, originalName).getByText('当前学期', { exact: true })).toBeVisible()
    await capture(page, testInfo, 'a-w1-current-term-legacy-after-visible-click')

    // Full document refresh must reconstruct auth from the real HttpOnly browser session and
    // reread the same current term from MySQL.
    await reloadWithBrowserSession(page)
    await expect(page.locator('.aa-current-card__sub')).toHaveText(originalName)
    await expect(termRow(page, originalName).getByText('当前学期', { exact: true })).toBeVisible()

    const activated = await activateGovernance(api, testTerm.termId)
    expect(activated.governanceStatus).toBe('ACTIVE')

    await reloadWithBrowserSession(page)
    await expect(page.locator('.aa-current-card__sub')).toHaveText(governanceName)
    await expect(page.getByText('全校统一治理已启用', { exact: true })).toBeVisible()
    await expect(page.getByText(/教务侧只读当前结论/)).toBeVisible()

    const oldRow = termRow(page, originalName)
    await expect(oldRow).toBeVisible()
    await expect(oldRow.getByRole('button', { name: '设为当前' })).toHaveCount(0)
    await expect(oldRow.getByText('统一治理切换', { exact: true })).toBeVisible()
    await capture(page, testInfo, 'a-w1-current-term-governance-no-bypass')

    // The remaining visible action must lead to the existing SYS-12 owner, not write AaTerm here.
    await page.getByRole('button', { name: '前往学年学期与业务日历' }).click()
    await expect(page).toHaveURL(/\/admin\/system\/academic-calendar(?:\?|$)/)
    await expect(page.getByText('学年学期与业务日历', { exact: false }).first()).toBeVisible()
  } finally {
    await restoreSandboxState(api, {
      originalCurrent,
      originalGovernance,
      originalGovernanceClosing,
      testTerm
    })
  }
})
