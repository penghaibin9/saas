import { test, expect } from '@playwright/test'

test('PHONE login, real self revoke, ACCOUNT fallback and refreshed readback', async ({ page }) => {
  const tenant = process.env.PHONE_TEST_TENANT, account = process.env.PHONE_TEST_ACCOUNT
  const password = 'Local-test-Password1!'
  const login = async (type, identifier) => {
    await page.goto('/login?tenant=' + tenant)
    await page.getByLabel('登录方式', { exact: true }).selectOption(type)
    await page.locator('#staff-account').fill(identifier)
    await page.locator('#staff-password').fill(password)
    await page.getByLabel('我已阅读并同意学校提供的用户协议与隐私政策').check()
    const response = page.waitForResponse(r => r.url().includes('/auth/browser-login') && r.request().method() === 'POST', { timeout: 20000 })
    await page.getByRole('button', { name: '进入教师工作台' }).click()
    expect((await response).status()).toBe(200)
    await expect(page.getByTitle('查看账号与切换身份').first()).toBeVisible()
  }
  const security = async () => {
    await page.getByTitle('查看账号与切换身份').first().click()
    await page.getByRole('button', { name: '账号安全' }).first().click()
    return page.getByRole('region', { name: '本人手机号登录凭据' })
  }
  await login('PHONE', '13800138000')
  let panel = await security()
  await expect(panel.getByText(/已验证 138\*\*\*\*8000/)).toBeVisible()
  await panel.getByLabel('当前登录密码').fill(password)
  await panel.getByRole('button', { name: '验证密码并办理解绑' }).click()
  await panel.getByLabel('解绑原因').fill('本人本地回归撤销号码')
  await panel.getByRole('button', { name: '确认生效并退出旧会话' }).click()
  await expect(panel.getByText('号码变更已生效', { exact: false })).toBeVisible()
  await panel.getByRole('button', { name: '返回登录' }).click()
  await login('ACCOUNT', account)
  await page.reload()
  panel = await security()
  await expect(panel.getByText(/已撤销，原账号可用/)).toBeVisible()
  await expect(panel.getByText('手机验证暂不可用', { exact: false })).toBeVisible()
  await expect(panel.getByRole('button', { name: '验证密码并办理绑定' })).toHaveCount(0)
})
