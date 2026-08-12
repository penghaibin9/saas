import { test, expect, attachObservability } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage, decodeJwt } from '../pages/login.page.mjs'

const contextOptions = (lastOctet) => ({
  extraHTTPHeaders: { 'X-Forwarded-For': `10.254.0.${lastOctet}` }
})

async function observedPage(browser, testInfo, lastOctet, label) {
  const context = await browser.newContext(contextOptions(lastOctet))
  const page = await context.newPage()
  const finalize = await attachObservability(page, testInfo, { label })
  return { context, page, finalize }
}

async function closeObserved(...entries) {
  let firstError
  for (const entry of entries) {
    try { await entry.finalize() } catch (error) { firstError ||= error }
    try { await entry.context.close() } catch (error) { firstError ||= error }
  }
  if (firstError) throw firstError
}

async function browserApi(page, token, method, path, body) {
  return page.evaluate(async ({ apiBaseUrl, tokenValue, requestMethod, requestPath, requestBody }) => {
    const response = await fetch(`${apiBaseUrl}${requestPath}`, {
      method: requestMethod,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${tokenValue}`,
        ...(requestBody === undefined ? {} : { 'Content-Type': 'application/json' })
      },
      body: requestBody === undefined ? undefined : JSON.stringify(requestBody)
    })
    const text = await response.text()
    let json = null
    try { json = JSON.parse(text) } catch { json = { message: text.slice(0, 500) } }
    return { status: response.status, json }
  }, {
    apiBaseUrl: config.apiBaseUrl,
    tokenValue: token,
    requestMethod: method,
    requestPath: path,
    requestBody: body
  })
}

test.describe.serial('登录、租户隔离与多角色身份切换', () => {
  test('真实浏览器登录：教师端与学生端均通过表单进入', async ({ browser }, testInfo) => {
    const staff = await observedPage(browser, testInfo, 21, 'staff-login')
    const student = await observedPage(browser, testInfo, 22, 'student-login')
    try {
      await new StaffLoginPage(staff.page, config.staffBaseUrl).login(config.sandboxAdmin)
      await expect(staff.page).toHaveURL(/\/workbench|\/admin/)

      await new StudentLoginPage(student.page, config.studentBaseUrl).login(config.student)
      await expect(student.page).toHaveURL(/\/portal\/(home|graduation)|\/home/)
    } finally {
      await closeObserved(staff, student)
    }
  })

  test('两个租户会话和真实资源访问完全隔离', async ({ browser }, testInfo) => {
    const sandbox = await observedPage(browser, testInfo, 23, 'sandbox-tenant')
    const demo = await observedPage(browser, testInfo, 24, 'demo-tenant')
    try {
      const sandboxLogin = new StaffLoginPage(sandbox.page, config.staffBaseUrl)
      const demoLogin = new StaffLoginPage(demo.page, config.staffBaseUrl)
      await sandboxLogin.login(config.sandboxAdmin)
      await demoLogin.login(config.demoAdmin)

      const sandboxToken = await sandboxLogin.token()
      const demoToken = await demoLogin.token()
      const sandboxPayload = decodeJwt(sandboxToken)
      const demoPayload = decodeJwt(demoToken)
      const sandboxTenant = String(sandboxPayload.tenantId || sandboxPayload.tenant_id || sandboxPayload.tid || '')
      const demoTenant = String(demoPayload.tenantId || demoPayload.tenant_id || demoPayload.tid || '')
      expect(sandboxTenant).not.toBe('')
      expect(demoTenant).not.toBe('')
      expect(sandboxTenant).not.toBe(demoTenant)

      await expect(sandbox.page.locator('body')).toContainText(/体验沙箱|sandbox-school/)
      await expect(demo.page.locator('body')).toContainText(/演示职业技术学校|demo-school/)
      await expect(sandbox.page.locator('body')).not.toContainText('演示职业技术学校（只读演示）')
      await expect(demo.page.locator('body')).not.toContainText('体验沙箱（运营平台可恢复）')

      const now = new Date()
      const academicYear = `${now.getUTCFullYear()}-${now.getUTCFullYear() + 1}`
      const batchNo = `TENANT-PROBE-${Date.now()}`
      const created = await browserApi(sandbox.page, sandboxToken, 'POST', '/graduation/batches', {
        batchName: `租户隔离探针 ${batchNo}`,
        batchNo,
        academicYear,
        gradeYear: `${now.getUTCFullYear() + 1}届`,
        plannedCount: 1,
        remark: 'isolated Playwright database only'
      })
      expect(created.status, JSON.stringify(created.json)).toBe(200)
      expect(created.json?.code, JSON.stringify(created.json)).toBe(0)
      const sandboxOnlyId = String(created.json?.data?.id || '')
      expect(sandboxOnlyId).not.toBe('')

      const crossed = await browserApi(
        demo.page,
        demoToken,
        'GET',
        `/graduation/batches/${sandboxOnlyId}`
      )
      expect([403, 404], JSON.stringify(crossed)).toContain(crossed.status)
      expect(crossed.json?.data?.id).not.toBe(sandboxOnlyId)
    } finally {
      await closeObserved(sandbox, demo)
    }
  })

  test('多角色账号通过可见身份列表切换，令牌轮换且菜单按新身份重建', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.multiRole)

    await login.switchRole(/毕设管理员|GRADUATION_ADMIN/)
    await expect.poll(() => login.currentRoleText()).toMatch(/毕设管理员|GRADUATION_ADMIN/)

    await login.switchRole(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
    await expect.poll(() => login.currentRoleText()).toMatch(/教务处管理员|教务管理员|教务老师|ACADEMIC_ADMIN/)
    await expect(page).toHaveURL(/\/workbench/)
  })
})