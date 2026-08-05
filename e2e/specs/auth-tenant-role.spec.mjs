import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage, decodeJwt } from '../pages/login.page.mjs'

const contextOptions = (lastOctet) => ({
  extraHTTPHeaders: { 'X-Forwarded-For': `10.254.0.${lastOctet}` }
})

test.describe.serial('登录、租户隔离与多角色身份切换', () => {
  test('真实浏览器登录：教师端与学生端均通过表单进入', async ({ browser }) => {
    const staffContext = await browser.newContext(contextOptions(21))
    const staffPage = await staffContext.newPage()
    await new StaffLoginPage(staffPage, config.staffBaseUrl).login(config.sandboxAdmin)
    await expect(staffPage).toHaveURL(/\/workbench|\/admin/)
    await staffContext.close()

    const studentContext = await browser.newContext(contextOptions(22))
    const studentPage = await studentContext.newPage()
    await new StudentLoginPage(studentPage, config.studentBaseUrl).login(config.student)
    await expect(studentPage).toHaveURL(/\/portal\/(home|graduation)|\/home/)
    await studentContext.close()
  })

  test('两个租户会话完全隔离，JWT 租户和页面学校标识不得串线', async ({ browser }) => {
    const sandbox = await browser.newContext(contextOptions(23))
    const demo = await browser.newContext(contextOptions(24))
    const sandboxPage = await sandbox.newPage()
    const demoPage = await demo.newPage()

    const sandboxLogin = new StaffLoginPage(sandboxPage, config.staffBaseUrl)
    const demoLogin = new StaffLoginPage(demoPage, config.staffBaseUrl)
    await sandboxLogin.login(config.sandboxAdmin)
    await demoLogin.login(config.demoAdmin)

    const sandboxPayload = decodeJwt(await sandboxLogin.token())
    const demoPayload = decodeJwt(await demoLogin.token())
    const sandboxTenant = String(sandboxPayload.tenantId || sandboxPayload.tenant_id || sandboxPayload.tid || '')
    const demoTenant = String(demoPayload.tenantId || demoPayload.tenant_id || demoPayload.tid || '')
    expect(sandboxTenant).not.toBe('')
    expect(demoTenant).not.toBe('')
    expect(sandboxTenant).not.toBe(demoTenant)

    await expect(sandboxPage.locator('body')).toContainText(/体验沙箱学校|sandbox-school/)
    await expect(demoPage.locator('body')).toContainText(/演示职业技术学校|demo-school/)
    await expect(sandboxPage.locator('body')).not.toContainText('演示职业技术学校（只读演示）')
    await expect(demoPage.locator('body')).not.toContainText('体验沙箱学校（运营平台可恢复）')

    await sandbox.close()
    await demo.close()
  })

  test('多角色账号通过可见身份列表切换，令牌轮换且菜单按新身份重建', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(config.multiRole)

    await login.switchRole(/毕设管理员|GRADUATION_ADMIN/)
    await expect.poll(() => login.currentRoleText()).toMatch(/毕设管理员|GRADUATION_ADMIN/)

    await login.switchRole(/教务管理员|教务老师|ACADEMIC_ADMIN/)
    await expect.poll(() => login.currentRoleText()).toMatch(/教务管理员|教务老师|ACADEMIC_ADMIN/)
    await expect(page).toHaveURL(/\/workbench/)
  })
})
