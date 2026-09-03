import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const ROUTE = '/admin/student-affairs/dashboard'
const DASHBOARD_API = /\/api\/v1\/student-affairs\/dashboard(?:\?|$)/
async function openDashboard(page, account = config.sandboxAdmin) {
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
  await page.goto(`${config.staffBaseUrl}${ROUTE}`)
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
  await expect(page.locator('.sa-v6-queue-row')).toHaveCount(7)
  for (const selector of ['.app-step-guide__mask', '.tour-mask']) {
    const mask = page.locator(selector)
    if (await mask.isVisible().catch(() => false)) {
      await page.getByRole('button', { name: /跳过引导|跳过/ }).first().click()
      await expect(mask).toBeHidden()
    }
  }
  await page.evaluate(async () => {
    await document.fonts.ready
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    document.querySelector('.bpl-main')?.scrollTo(0, 0)
    window.scrollTo(0, 0)
  })
}
async function evidence(page, testInfo, label) {
  const result = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('.sa-v6-queue-row')].map((row) => {
      const rect = row.getBoundingClientRect()
      return { key: row.dataset.queue, top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right, disabled: row.disabled }
    })
    const scope = document.querySelector('.sa-v6-page-shell')
    const sla = document.querySelector('.sa-context-stack')
    const containers = [scope, ...scope.querySelectorAll('.sa-v6-workspace, .sa-v6-hero, .sa-v6-queue-card, .sa-v6-side')]
    return {
      width: innerWidth, height: innerHeight, rows,
      completeRows: rows.filter((row) => row.top >= 0 && row.bottom <= innerHeight).length,
      firstRowY: rows[0]?.top,
      horizontalOverflow: Math.max(0, document.documentElement.scrollWidth - innerWidth, ...containers.map((el) => el.scrollWidth - el.clientWidth)),
      slaTop: sla?.getBoundingClientRect().top ?? null,
      slaFocusableCount: sla?.querySelectorAll('a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])').length ?? 0
    }
  })
  const file = testInfo.outputPath(`${label}.png`)
  await page.screenshot({ path: file, fullPage: false, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(label, { path: file, contentType: 'image/png' })
  await testInfo.attach(`${label}-geometry`, { body: JSON.stringify(result, null, 2), contentType: 'application/json' })
  return result
}
async function expectDestination(page, path, query = {}) {
  await expect.poll(() => new URL(page.url()).pathname).toBe(path)
  for (const [key, value] of Object.entries(query)) {
    await expect.poll(() => new URL(page.url()).searchParams.get(key)).toBe(value)
  }
}
async function returnToDashboard(page) {
  await page.goBack()
  await expectDestination(page, ROUTE)
  await expect(page.locator('.sa-v6-dashboard')).toBeVisible()
}
for (const [width, height, minimumRows] of [[1760, 1000, 4], [1440, 900, 4], [1366, 768, 3], [1280, 800, 3]]) {
  test(`V6 A1 real API ${width}x${height}: first working row and complete records`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height })
    await openDashboard(page)
    const result = await evidence(page, testInfo, `v6-a1-${width}x${height}`)
    expect(result.firstRowY, 'Working queue must start within the V6 first-screen budget').toBeLessThanOrEqual(290)
    expect(result.completeRows).toBeGreaterThanOrEqual(minimumRows)
    expect(result.horizontalOverflow).toBeLessThanOrEqual(1)
    if (result.slaTop !== null) {
      expect(result.slaTop).toBeGreaterThan(result.rows.at(-1).bottom)
      expect(result.slaFocusableCount, 'Visual reorder is limited to the read-only SLA').toBe(0)
    }
    await expect(page.locator('.bpl-help__btn')).toBeVisible()
    await expect(page.locator('.bpl-bell')).toBeVisible()
    await expect(page.locator('.bpl-cmdk--fn')).toBeVisible()
  })
}
test('V6 A1 125 percent equivalent CSS viewport remains usable', async ({ page }, testInfo) => {
  // 1366/1.25 by 768/1.25: equivalent CSS viewport, not native browser zoom.
  await page.setViewportSize({ width: 1093, height: 614 })
  await openDashboard(page)
  const result = await evidence(page, testInfo, 'v6-a1-125pct-equivalent')
  expect(result.completeRows).toBeGreaterThanOrEqual(3)
  expect(result.horizontalOverflow).toBeLessThanOrEqual(1)
})
test('V6 A1 six real theme controls preserve contrast at 1366 without refetch', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await openDashboard(page)
  let dashboardRequests = 0
  page.on('request', (request) => { if (DASHBOARD_API.test(request.url())) dashboardRequests++ })
  for (const theme of ['a', 'b', 'c', 'd', 'e', 'f']) {
    const dot = page.locator(`button.bpl-thdot--${theme}`)
    await expect(dot).toBeVisible()
    const centerIsClickable = await dot.evaluate((element) => {
      const rect = element.getBoundingClientRect()
      const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)
      return hit === element || element.contains(hit)
    })
    expect(centerIsClickable, `theme ${theme} control center must be pointer-accessible`).toBe(true)
    await dot.click()
    await expect(page.locator('.base-portal-layout')).toHaveClass(new RegExp(`\\bth-${theme}\\b`))
    await expect(dot).toHaveAttribute('aria-pressed', 'true')
    await expect(page.locator('button.bpl-thdot[aria-pressed="true"]')).toHaveCount(1)
    const contrast = await page.locator('.sa-v6-queue-row').first().evaluate((row) => {
      // Canvas normalizes computed color syntax (including color-mix) to sRGB bytes.
      const canvas = document.createElement('canvas'); canvas.width = 1; canvas.height = 1
      const ctx = canvas.getContext('2d', { willReadFrequently: true })
      const luminance = (color) => {
        ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = color; ctx.fillRect(0, 0, 1, 1)
        const rgb = [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3).map((value) => {
          const c = value / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
        })
        return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722
      }
      const a = luminance(getComputedStyle(row.querySelector('strong')).color)
      const b = luminance(getComputedStyle(row).backgroundColor)
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
    })
    await evidence(page, testInfo, `v6-a1-theme-${theme}`)
    expect(contrast, `working title contrast in theme ${theme}`).toBeGreaterThanOrEqual(4.5)
  }
  expect(dashboardRequests).toBe(0)
})
test('V6 A1 real scoped counselor and keyboard drilldown', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await openDashboard(page, {
    tenant: config.sandboxAdmin.tenant,
    username: process.env.E2E_AFFAIRS_COUNSELOR_USERNAME || 'e2e_counselor_a',
    password: process.env.E2E_AFFAIRS_COUNSELOR_PASSWORD || 'E2eTest@2026'
  })
  await expect(page.locator('.sa-v6-scope-card')).toContainText('辅导员')
  const result = await evidence(page, testInfo, 'v6-a1-counselor')
  expect(result.firstRowY).toBeLessThanOrEqual(290)
  expect(result.completeRows).toBeGreaterThanOrEqual(3)
  const risk = page.locator('[data-queue="riskStudents"]')
  await expect(risk).toBeEnabled(); await risk.focus(); await expect(risk).toBeFocused()
  await page.keyboard.press('Enter')
  await expectDestination(page, '/admin/student-affairs/risk', { status: 'OPEN' })
  await returnToDashboard(page)
})
test('V6 A1 sandbox admin real-clicks every queue, quick entry and cross-center entry', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const contextPromise = page.waitForResponse((res) => /\/api\/v1\/rbac\/current-context(?:\?|$)/.test(res.url()))
  await openDashboard(page)
  const contextResponse = await contextPromise
  expect(contextResponse.status()).toBe(200)
  const context = await contextResponse.json()
  expect(context.code).toBe(0)
  // The real fixture owns these canonical permissions. Missing UI is a defect, not an excuse to skip.
  for (const code of ['studentAffairs.orientation.view', 'internship.risk.view', 'graduationDesign.risk.view']) {
    expect(context.data.permissionPatterns, `fixture must be authorized for ${code}`).toContain(code)
  }
  const clicked = []
  const queues = [
    ['riskStudents', '/admin/student-affairs/risk', { status: 'OPEN' }],
    ['overdueLeave', '/admin/student-affairs/leave/ledger', { status: 'OVERDUE' }],
    ['pendingTodo', '/admin/approval/todos', {}],
    ['pendingLeave', '/admin/student-affairs/leave', {}],
    ['pendingAid', '/admin/student-affairs/aid', { status: 'REVIEW' }],
    ['pendingFunding', '/admin/student-affairs/funding', { status: 'REVIEW' }],
    ['pendingDiscipline', '/admin/student-affairs/discipline', { status: 'REVIEW' }]
  ]
  for (const [key, pathname, query] of queues) {
    const row = page.locator(`[data-queue="${key}"]`)
    await expect(row, `${key} must remain a real authorized entry for sandbox admin`).toBeEnabled()
    await row.click()
    await expectDestination(page, pathname, query)
    clicked.push({ key, url: page.url() })
    await returnToDashboard(page)
  }

  const allTodo = page.locator('[data-action="all-todo"]')
  await expect(allTodo).toBeEnabled()
  await allTodo.click()
  await expectDestination(page, '/admin/approval/todos')
  clicked.push({ key: 'all-todo', url: page.url() })
  await returnToDashboard(page)

  const quickEntries = [
    ['quick-student', '学生主档', '/admin/student/list', {}],
    ['quick-orientation', '数字迎新', '/admin/orientation', {}],
    ['quick-dorm', '宿舍异常', '/admin/student-affairs/dorm/exception', {}]
  ]
  for (const [key, label, pathname, query] of quickEntries) {
    const button = page.locator('.sa-v6-entry-card .sa-v6-entry').filter({ hasText: label }).first()
    await expect(button, `${label} quick entry must be visible for sandbox admin`).toBeEnabled()
    await button.click()
    await expectDestination(page, pathname, query)
    clicked.push({ key, url: page.url() })
    await returnToDashboard(page)
  }

  const crossCenterEntries = [
    ['cross-orientation', '数字迎新', '/admin/orientation', {}],
    ['cross-internship', '岗位实习风险', '/admin/internship/risks', {}],
    ['cross-graduation', '毕业设计风险', '/admin/graduation/risk-archive', { panel: 'risk' }]
  ]
  for (const [key, label, pathname, query] of crossCenterEntries) {
    const button = page.locator('.sa-v6-bridge-actions').getByRole('button', { name: label, exact: true })
    await expect(button, `${label} cross-center entry must be visible for sandbox admin`).toBeEnabled()
    await button.click()
    await expectDestination(page, pathname, query)
    if (key === 'cross-graduation') {
      await expect(page.locator('.gp-tabs__item').filter({ hasText: /^问题预警$/ })).toBeVisible()
      await expect(page.locator('.gp-tabs__item').filter({ hasText: /^问题预警$/ })).toHaveClass(/is-active/)
    }
    clicked.push({ key, url: page.url() })
    await returnToDashboard(page)
  }

  await testInfo.attach('v6-a1-real-click-destinations', {
    body: JSON.stringify(clicked, null, 2),
    contentType: 'application/json'
  })
  expect(clicked).toHaveLength(14)
})
test('V6 A1 test-injected missing values and malformed refresh remain honest', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  let malformed = false
  // Alter only this test's HTTP response. No fixture enters production code.
  await page.route(DASHBOARD_API, async (route) => {
    if (malformed) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, data: null }) })
      return
    }
    const response = await route.fetch(); const envelope = await response.json()
    expect(envelope.code).toBe(0)
    envelope.data.summaryCards = envelope.data.summaryCards.filter((card) => !['riskStudents', 'pendingLeave'].includes(card.key))
    envelope.data.summaryCards.find((card) => card.key === 'pendingTodo').value = 0
    delete envelope.data.riskSummary
    await route.fulfill({ response, json: envelope })
  })
  await openDashboard(page)
  const missing = page.locator('[data-queue="pendingLeave"]')
  await expect(missing.locator('.sa-v6-queue-row__count')).toHaveText('—')
  await expect(missing).toContainText('汇总未取得'); await expect(missing).not.toHaveClass(/is-success/)
  await expect(page.locator('[data-queue="pendingTodo"]')).toContainText('当前无事项')
  await expect(page.locator('.sa-v6-risk-card')).toContainText('摘要待核实')
  await evidence(page, testInfo, 'v6-a1-test-injected-partial')
  malformed = true
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await expect(page.locator('.sa-v6-dashboard')).toHaveCount(0)
  await expect(page.locator('.sa-v6-page-shell')).toContainText('未取得有效的学工汇总')
  const file = testInfo.outputPath('v6-a1-test-injected-error.png')
  await page.screenshot({ path: file, animations: 'disabled' })
  await testInfo.attach('v6-a1-test-injected-error', { path: file, contentType: 'image/png' })
})
test('V6 A1 test-injected long scope and large counters do not overflow', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.route(DASHBOARD_API, async (route) => {
    const response = await route.fetch(); const envelope = await response.json()
    expect(envelope.code).toBe(0)
    envelope.data.scopeLabel = '智能制造与信息工程学院学生工作管理范围'.repeat(3)
    for (const card of envelope.data.summaryCards) card.value = 123456
    await route.fulfill({ response, json: envelope })
  })
  await openDashboard(page)
  const result = await evidence(page, testInfo, 'v6-a1-test-injected-extreme')
  expect(result.horizontalOverflow).toBeLessThanOrEqual(1)
  await expect(page.locator('[data-metric="pendingTodo"] dd')).toHaveText('123,456')
  const scopeValue = page.locator('.sa-v6-scope-grid > div:nth-child(2) dd')
  const scopeVisual = await scopeValue.evaluate((element) => {
    const style = getComputedStyle(element)
    const rect = element.getBoundingClientRect()
    return {
      text: element.textContent,
      title: element.getAttribute('title'),
      height: rect.height,
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      overflow: style.overflow,
      textOverflow: style.textOverflow,
      whiteSpace: style.whiteSpace
    }
  })
  expect(scopeVisual.title).toBe(scopeVisual.text)
  expect(scopeVisual.whiteSpace).toBe('nowrap')
  expect(scopeVisual.overflow).toBe('hidden')
  expect(scopeVisual.textOverflow).toBe('ellipsis')
  expect(scopeVisual.height).toBeLessThanOrEqual(24)
  expect(scopeVisual.scrollWidth).toBeGreaterThan(scopeVisual.clientWidth)
})
