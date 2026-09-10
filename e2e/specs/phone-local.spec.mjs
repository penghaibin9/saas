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

test('student first-login password change keeps ACCOUNT and PHONE entries on the original subject', async ({ page }) => {
  const tenant = process.env.PHONE_TEST_TENANT
  const account = process.env.PHONE_TEST_STUDENT_ACCOUNT
  const initialAccount = process.env.PHONE_TEST_INITIAL_STUDENT_ACCOUNT
  const phone = process.env.PHONE_TEST_STUDENT_PHONE
  const initialPassword = 'Student-initial-Password1!'
  const newPassword = 'Student-local-Password2!'
  const login = async (type, identifier, password) => {
    await page.goto(`http://127.0.0.1:15311/portal/login?tenant=${tenant}`)
    await page.getByLabel('登录方式', { exact: true }).selectOption(type)
    await page.locator('#student-account').fill(identifier)
    await page.locator('#student-password').fill(password)
    await page.getByText('我已阅读并同意学校提供的用户协议与隐私政策').locator('input').check()
    const response = page.waitForResponse(r => r.url().includes('/auth/browser-login') && r.request().method() === 'POST', { timeout: 20000 })
    await page.getByRole('button', { name: '进入学生服务门户' }).click()
    expect((await response).status()).toBe(200)
  }

  await login('ACCOUNT', initialAccount, initialPassword)
  await expect(page.getByRole('heading', { name: '首次登录，请先修改初始密码' })).toBeVisible()
  await page.locator('#sp-old-password').fill(initialPassword)
  await page.locator('#sp-new-password').fill(newPassword)
  await page.locator('#sp-confirm-password').fill(newPassword)
  await page.getByRole('button', { name: '修改密码并重新登录' }).click()
  await expect(page.getByRole('heading', { name: '学生登录' })).toBeVisible()

  await login('ACCOUNT', account, newPassword)
  await page.goto('http://127.0.0.1:15311/portal/account-security')
  await expect(page.getByRole('heading', { name: '我的账号与安全' })).toBeVisible()
  await expect(page.getByText(/登录号码：137\*\*\*\*/)).toBeVisible()
  await page.reload()
  await expect(page.getByText(/登录号码：137\*\*\*\*/)).toBeVisible()

  await page.goto('http://127.0.0.1:15311/portal/login?tenant=' + tenant)
  await login('PHONE', phone, newPassword)
  await expect(page).toHaveURL(/\/portal\/home/)
})

test('teacher and student H5 entries authenticate with ACCOUNT and PHONE at mobile width', async ({ browser }) => {
  const tenant = process.env.PHONE_TEST_TENANT
  const miniBase = process.env.PHONE_TEST_MINI_BASE_URL
  const cases = [
    { side: 'teacher', type: 'ACCOUNT', identifier: process.env.PHONE_TEST_MINI_TEACHER_ACCOUNT,
      password: 'Local-test-Password1!', button: '进入教师工作台', home: '/pages/teacher/workbench/index' },
    { side: 'teacher', type: 'PHONE', identifier: process.env.PHONE_TEST_MINI_TEACHER_PHONE,
      password: 'Local-test-Password1!', button: '进入教师工作台', home: '/pages/teacher/workbench/index' },
    { side: 'student', type: 'ACCOUNT', identifier: process.env.PHONE_TEST_STUDENT_ACCOUNT,
      password: 'Student-local-Password2!', button: '进入学生首页', home: '/pages/student/home/index' },
    { side: 'student', type: 'PHONE', identifier: process.env.PHONE_TEST_STUDENT_PHONE,
      password: 'Student-local-Password2!', button: '进入学生首页', home: '/pages/student/home/index' },
  ]
  for (const item of cases) {
    const context = await browser.newContext({ viewport: { width: item.side === 'teacher' ? 390 : 375, height: 844 },
      locale: 'zh-CN', isMobile: true, hasTouch: true })
    const page = await context.newPage()
    await page.goto(`${miniBase}/#/pages/login/${item.side}/index`)
    if (item.type === 'PHONE') {
      await page.locator('uni-picker .tenant-box').tap()
      const column = page.locator('uni-picker-view-column')
      await column.waitFor({ state: 'visible' })
      await column.hover()
      await page.mouse.wheel(0, 100)
      await expect(page.locator('.uni-picker-view-content')).toHaveAttribute('style', /translateY\(-34px\)/)
      await page.locator('.uni-picker-action-confirm:visible').tap()
      await expect(page.locator('uni-picker')).toContainText('已验证手机号')
    }
    await page.getByRole('textbox').nth(0).fill(item.identifier)
    await page.getByRole('textbox').nth(1).fill(item.password)
    await page.getByText('学校编码', { exact: true }).click()
    await page.getByRole('textbox').nth(2).fill(tenant)
    await page.getByText('我已阅读并同意学校提供的', { exact: true }).click()
    const response = page.waitForResponse(r => r.url().includes('/auth/browser-login') && r.request().method() === 'POST', { timeout: 20000 })
    await page.locator('uni-button.account-button').click()
    expect((await response).status()).toBe(200)
    await expect(page).toHaveURL(new RegExp(item.home.replaceAll('/', '\\/')))
    await context.close()
  }
})
