import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

function isDashboardRequest(url) {
  try {
    return new URL(url).pathname === '/api/v1/internship/dashboard'
  } catch {
    return false
  }
}

test('岗位实习二级页不再无批次探测 dashboard，真实看板始终显式携带 batchId', async ({ page }) => {
  const fixture = await loadInternshipFixture()
  const dashboardRequests = []
  const dashboardResponses = []

  page.on('request', (request) => {
    if (!isDashboardRequest(request.url())) return
    dashboardRequests.push({ method: request.method(), url: request.url() })
  })
  page.on('response', (response) => {
    if (!isDashboardRequest(response.url())) return
    dashboardResponses.push({ status: response.status(), url: response.url() })
  })

  await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)

  // These are the exact staff-PC workspaces that exposed the unscoped dashboard
  // probe in the production browser evidence. They own their own data contracts;
  // ModuleSummaryStrip must reuse internshipBatch and must not issue a second
  // dashboard request while the parent layout is resolving the selected batch.
  const secondaryRoutes = [
    '/admin/internship/enterprises?panel=list',
    '/admin/internship/scores',
    '/admin/internship/guidance?panel=guidance',
    '/admin/internship/leaves?panel=all',
    '/admin/internship/risks?panel=board',
    '/admin/internship/leaves?panel=pending',
    '/admin/internship/students',
    '/admin/internship/batches?panel=list'
  ]

  for (const route of secondaryRoutes) {
    const separator = route.includes('?') ? '&' : '?'
    const before = dashboardRequests.length
    await page.goto(`${config.staffBaseUrl}${route}${separator}batchId=${encodeURIComponent(fixture.batchId)}`)
    await expect(page.locator('.base-portal-layout')).toBeVisible()
    await page.waitForTimeout(700)
    expect(
      dashboardRequests.slice(before),
      `${route} must not probe /internship/dashboard; batch context belongs to internshipBatch store`
    ).toEqual([])
  }

  // The real dashboard is the one place where this API is authoritative. It must
  // keep the strict backend contract by sending the selected batch explicitly.
  const requestBeforeDashboard = dashboardRequests.length
  const responseBeforeDashboard = dashboardResponses.length
  await page.goto(`${config.staffBaseUrl}/admin/internship?batchId=${encodeURIComponent(fixture.batchId)}`)
  await expect(page.locator('.base-portal-layout')).toBeVisible()
  await expect.poll(() => dashboardResponses.length - responseBeforeDashboard).toBeGreaterThan(0)

  const realDashboardRequests = dashboardRequests.slice(requestBeforeDashboard)
  const realDashboardResponses = dashboardResponses.slice(responseBeforeDashboard)
  expect(realDashboardRequests.length).toBeGreaterThan(0)

  for (const request of realDashboardRequests) {
    const url = new URL(request.url)
    expect(url.searchParams.get('batchId')).toBe(String(fixture.batchId))
  }
  for (const response of realDashboardResponses) {
    expect(response.status, response.url).toBeLessThan(400)
  }
})
