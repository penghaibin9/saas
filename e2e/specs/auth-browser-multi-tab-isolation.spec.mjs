import { test, expect, attachObservability } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, decodeJwt } from '../pages/login.page.mjs'

async function tabSessionId(page) {
  return page.evaluate(() => String(sessionStorage.getItem('gx_browser_session_id_v2') || ''))
}

async function reloadAndWaitForRefresh(page) {
  const refresh = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/browser-refresh') && response.request().method() === 'POST'
  )
  await page.reload()
  const response = await refresh
  expect(response.status()).toBe(200)
}

test.describe.serial('same-context browser tab auth isolation', () => {
  test('two staff accounts in one browser context keep independent refresh sessions', async ({ browser }, testInfo) => {
    const context = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '10.254.0.41' } })
    const pageA = await context.newPage()
    const pageB = await context.newPage()
    const finalizeA = await attachObservability(pageA, testInfo, { label: 'same-context-staff-a' })
    const finalizeB = await attachObservability(pageB, testInfo, { label: 'same-context-staff-b' })
    try {
      const loginA = new StaffLoginPage(pageA, config.staffBaseUrl)
      const loginB = new StaffLoginPage(pageB, config.staffBaseUrl)
      await loginA.login(config.sandboxAdmin)
      const tokenA = await loginA.token()
      await loginB.login(config.demoAdmin)
      const tokenB = await loginB.token()
      const claimsA = decodeJwt(tokenA)
      const claimsB = decodeJwt(tokenB)
      expect(String(claimsA.userId || '')).not.toBe(String(claimsB.userId || ''))
      expect(String(claimsA.tenantId || '')).not.toBe(String(claimsB.tenantId || ''))
      const sidA = await tabSessionId(pageA)
      const sidB = await tabSessionId(pageB)
      expect(sidA).toBeTruthy()
      expect(sidB).toBeTruthy()
      expect(sidA).not.toBe(sidB)
      await reloadAndWaitForRefresh(pageA)
      await expect(pageA.locator('body')).toContainText(/体验沙箱|sandbox-school/)
      await reloadAndWaitForRefresh(pageB)
      await expect(pageB.locator('body')).toContainText(/演示职业技术学校|demo-school/)
      const logout = await pageA.evaluate(async ({ apiBaseUrl, sid }) => {
        const response = await fetch(`${apiBaseUrl}/auth/browser-logout`, {
          method: 'POST', credentials: 'include',
          headers: { 'X-Browser-Session': 'staff', 'X-Browser-Session-Id': sid }
        })
        return { status: response.status, body: await response.json() }
      }, { apiBaseUrl: config.apiBaseUrl, sid: sidA })
      expect(logout.status, JSON.stringify(logout.body)).toBe(200)
      expect(logout.body?.code, JSON.stringify(logout.body)).toBe(0)
      await reloadAndWaitForRefresh(pageB)
      await expect(pageB.locator('body')).toContainText(/演示职业技术学校|demo-school/)
    } finally {
      await finalizeA(); await finalizeB(); await context.close()
    }
  })

  test('same user can hold different roles in two tabs without cross-rotation', async ({ browser }, testInfo) => {
    const context = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '10.254.0.42' } })
    const pageA = await context.newPage()
    const pageB = await context.newPage()
    const finalizeA = await attachObservability(pageA, testInfo, { label: 'same-user-role-a' })
    const finalizeB = await attachObservability(pageB, testInfo, { label: 'same-user-role-b' })
    try {
      const loginA = new StaffLoginPage(pageA, config.staffBaseUrl)
      const loginB = new StaffLoginPage(pageB, config.staffBaseUrl)
      await loginA.login(config.multiRole)
      await loginB.login(config.multiRole)
      expect(await tabSessionId(pageA)).not.toBe(await tabSessionId(pageB))
      await loginA.switchRole(/毕设管理员|GRADUATION_ADMIN/)
      await loginB.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
      await expect.poll(() => loginA.currentRoleText()).toMatch(/毕设管理员|GRADUATION_ADMIN/)
      await expect.poll(() => loginB.currentRoleText()).toMatch(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
      await reloadAndWaitForRefresh(pageA)
      await reloadAndWaitForRefresh(pageB)
      await expect.poll(() => loginA.currentRoleText()).toMatch(/毕设管理员|GRADUATION_ADMIN/)
      await expect.poll(() => loginB.currentRoleText()).toMatch(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
    } finally {
      await finalizeA(); await finalizeB(); await context.close()
    }
  })
})
