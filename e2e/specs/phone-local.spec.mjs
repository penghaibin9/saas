import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'

async function capturedSmsCode(phone) {
  let code = ''
  await expect.poll(async () => {
    try {
      const lines = (await readFile(process.env.PHONE_SMS_MAILBOX, 'utf8'))
        .split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line))
      code = String(lines.filter(item => item.phone === phone).at(-1)?.code || '')
      return /^\d{6}$/.test(code)
    } catch {
      return false
    }
  }, { timeout: 20000, intervals: [100, 200, 500] }).toBe(true)
  return code
}

test('PHONE login, real self revoke, ACCOUNT fallback and refreshed readback', async ({ page }) => {
  const tenant = process.env.PHONE_TEST_TENANT, account = process.env.PHONE_TEST_ACCOUNT
  const password = 'Local-test-Password1!'
  const login = async (type, identifier) => {
    await page.goto('/login?tenant=' + tenant)
    await page.getByRole('button', { name: type === 'PHONE' ? '手机号登录' : '账号登录', exact: true }).click()
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

test('real xlsx import creates accounts through Staff PC', async ({ page }) => {
  test.skip(process.env.PHONE_REAL_IMPORT_BROWSER !== '1', 'requires the real XLSX/MySQL import fixture')
  const tenant = process.env.PHONE_TEST_TENANT
  await page.goto(`/login?tenant=${tenant}`)
  await page.getByRole('button', { name: '账号登录', exact: true }).click()
  await page.locator('#staff-account').fill(process.env.PHONE_IMPORTER_ACCOUNT)
  await page.locator('#staff-password').fill(process.env.PHONE_IMPORTER_PASSWORD)
  await page.getByLabel('我已阅读并同意学校提供的用户协议与隐私政策').check()
  const response = page.waitForResponse(r => r.url().includes('/auth/browser-login') && r.request().method() === 'POST', { timeout: 20000 })
  await page.getByRole('button', { name: '进入教师工作台' }).click()
  expect((await response).status()).toBe(200)
  await expect(page.getByTitle('查看账号与切换身份').first()).toBeVisible()

  const imports = [
    { route: '/admin/system/identity-import/teachers', title: '教职工导入',
      template: process.env.PHONE_IMPORT_TEACHER_TEMPLATE },
    { route: '/admin/system/identity-import/students', title: '学生导入与账号开通',
      template: process.env.PHONE_IMPORT_STUDENT_TEMPLATE }
  ]
  for (const item of imports) {
    await page.goto(item.route)
    await expect(page.getByRole('heading', { name: item.title }).first()).toBeVisible()
    await page.getByLabel('选择身份导入文件').setInputFiles(item.template)
    await expect(page.getByTestId('identity-filename')).toBeVisible()
    await page.getByTestId('identity-upload').click()
    await expect(page.getByTestId('identity-status')).toContainText('预检通过', { timeout: 100000 })
    await expect(page.getByText('新增待本人验证')).toBeVisible()
    await page.getByTestId('identity-review-open').click()
    await page.getByLabel('我已核对本次导入名单与数量').check()
    await page.getByTestId('identity-confirm').click()
    await expect(page.getByTestId('identity-receipt')).toContainText('导入完成', { timeout: 30000 })
    await expect(page.getByTestId('identity-note')).toContainText('已从服务端重新读取完成结果')
  }
})

test('imported accounts complete verified bind, change and four authenticated surfaces', async ({ page, browser }) => {
  test.skip(process.env.PHONE_REAL_IMPORT_BROWSER !== '1', 'requires the real XLSX/MySQL import fixture')
  const tenant = process.env.PHONE_TEST_TENANT
  const teacher = {
    account: process.env.PHONE_IMPORT_TEACHER_ACCOUNT,
    phone: process.env.PHONE_IMPORT_TEACHER_PHONE,
    initialPassword: process.env.PHONE_IMPORT_TEACHER_INITIAL_PASSWORD,
    password: 'Teacher-real-Password2!'
  }
  const student = {
    account: process.env.PHONE_IMPORT_STUDENT_ACCOUNT,
    phone: process.env.PHONE_IMPORT_STUDENT_PHONE,
    changedPhone: process.env.PHONE_IMPORT_STUDENT_CHANGED_PHONE,
    initialPassword: process.env.PHONE_IMPORT_STUDENT_INITIAL_PASSWORD,
    password: 'Student-real-Password2!'
  }

  const staffLogin = async (type, identifier, password) => {
    await page.goto(`/login?tenant=${tenant}`)
    await page.getByRole('button', { name: type === 'PHONE' ? '手机号登录' : '账号登录', exact: true }).click()
    await page.locator('#staff-account').fill(identifier)
    await page.locator('#staff-password').fill(password)
    await page.getByLabel('我已阅读并同意学校提供的用户协议与隐私政策').check()
    const response = page.waitForResponse(r => r.url().includes('/auth/browser-login') && r.request().method() === 'POST', { timeout: 20000 })
    await page.getByRole('button', { name: '进入教师工作台' }).click()
    expect((await response).status()).toBe(200)
  }
  const studentLogin = async (type, identifier, password) => {
    await page.goto(`http://127.0.0.1:15311/portal/login?tenant=${tenant}`)
    await page.getByLabel('登录方式', { exact: true }).selectOption(type)
    await page.locator('#student-account').fill(identifier)
    await page.locator('#student-password').fill(password)
    await page.getByText('我已阅读并同意学校提供的用户协议与隐私政策').locator('input').check()
    const response = page.waitForResponse(r => r.url().includes('/auth/browser-login') && r.request().method() === 'POST', { timeout: 20000 })
    await page.getByRole('button', { name: '进入学生服务门户' }).click()
    expect((await response).status()).toBe(200)
  }
  const finishPhoneProof = async (container, phone, labels) => {
    await container.getByLabel(labels.phone, { exact: true }).fill(phone)
    await container.getByLabel(labels.password, { exact: true }).fill(labels.currentPassword)
    await container.getByRole('button', { name: labels.action, exact: true }).click()
    await container.getByRole('button', { name: '请求短信验证码', exact: true }).click()
    const code = await capturedSmsCode(phone)
    await container.getByLabel('短信验证码', { exact: true }).fill(code)
    await container.getByRole('button', { name: '验证本次号码', exact: true }).click()
    await container.getByRole('button', { name: '确认生效并退出旧会话', exact: true }).click()
  }

  // Student: generated credential receipt -> forced password change -> imported PENDING candidate.
  await studentLogin('ACCOUNT', student.account, student.initialPassword)
  await expect(page.getByRole('heading', { name: '首次登录，请先修改初始密码' })).toBeVisible()
  await page.locator('#sp-old-password').fill(student.initialPassword)
  await page.locator('#sp-new-password').fill(student.password)
  await page.locator('#sp-confirm-password').fill(student.password)
  await page.getByRole('button', { name: '修改密码并重新登录' }).click()
  await expect(page.getByRole('heading', { name: '学生登录' })).toBeVisible()

  await studentLogin('ACCOUNT', student.account, student.password)
  await page.goto('http://127.0.0.1:15311/portal/account-security')
  const studentSecurity = page.locator('main.account-security')
  await expect(studentSecurity.getByText(/候选：137\*\*\*\*/)).toBeVisible()
  await finishPhoneProof(studentSecurity, student.phone, {
    phone: '本人手机号', password: '当前密码', currentPassword: student.password,
    action: '验证密码并绑定'
  })
  await studentSecurity.getByRole('button', { name: '返回学生登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '学生登录' })).toBeVisible()

  // The newly verified alias authenticates the same imported student, who then changes it.
  await studentLogin('PHONE', student.phone, student.password)
  await expect(page).toHaveURL(/\/portal\/home/)
  await page.goto('http://127.0.0.1:15311/portal/account-security')
  await expect(studentSecurity.getByText(/登录号码：137\*\*\*\*/)).toBeVisible()
  await finishPhoneProof(studentSecurity, student.changedPhone, {
    phone: '本人手机号', password: '当前密码', currentPassword: student.password,
    action: '验证密码并换号'
  })
  await studentSecurity.getByRole('button', { name: '返回学生登录', exact: true }).click()
  await studentLogin('PHONE', student.changedPhone, student.password)
  await expect(page).toHaveURL(/\/portal\/home/)

  // Teacher: the same receipt/first-login rule, then a real self-service bind in Staff PC.
  await staffLogin('ACCOUNT', teacher.account, teacher.initialPassword)
  await expect(page.getByRole('heading', { name: '首次登录，请先修改初始密码' })).toBeVisible()
  await page.locator('#old-password').fill(teacher.initialPassword)
  await page.locator('#new-password').fill(teacher.password)
  await page.locator('#confirm-password').fill(teacher.password)
  await page.getByRole('button', { name: '修改密码并重新登录' }).click()
  await expect(page.getByRole('heading', { name: '教师 / 管理人员登录' })).toBeVisible()

  await staffLogin('ACCOUNT', teacher.account, teacher.password)
  await expect(page.getByTitle('查看账号与切换身份').first()).toBeVisible()
  await page.getByTitle('查看账号与切换身份').first().click()
  await page.getByRole('button', { name: '账号安全' }).first().click()
  const teacherSecurity = page.getByRole('region', { name: '本人手机号登录凭据' })
  await expect(teacherSecurity.getByText(/待核验号码：139\*\*\*\*/)).toBeVisible()
  await finishPhoneProof(teacherSecurity, teacher.phone, {
    phone: '本次本人手机号', password: '当前登录密码', currentPassword: teacher.password,
    action: '验证密码并办理绑定'
  })
  await teacherSecurity.getByRole('button', { name: '返回登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '教师 / 管理人员登录' })).toBeVisible()

  // Reuse the imported identities on both mobile role entries at real mobile widths.
  const mobileCases = [
    { side: 'teacher', type: 'ACCOUNT', identifier: teacher.account, password: teacher.password,
      home: '/pages/teacher/workbench/index' },
    { side: 'teacher', type: 'PHONE', identifier: teacher.phone, password: teacher.password,
      home: '/pages/teacher/workbench/index' },
    { side: 'student', type: 'ACCOUNT', identifier: student.account, password: student.password,
      home: '/pages/student/home/index' },
    { side: 'student', type: 'PHONE', identifier: student.changedPhone, password: student.password,
      home: '/pages/student/home/index' }
  ]
  for (const item of mobileCases) {
    const context = await browser.newContext({
      viewport: { width: item.side === 'teacher' ? 390 : 375, height: 844 },
      locale: 'zh-CN', isMobile: true, hasTouch: true
    })
    const mobile = await context.newPage()
    await mobile.goto(`${process.env.PHONE_TEST_MINI_BASE_URL}/#/pages/login/${item.side}/index`)
    if (item.type === 'PHONE') {
      await mobile.locator('uni-picker .tenant-box').tap()
      const column = mobile.locator('uni-picker-view-column')
      await column.waitFor({ state: 'visible' })
      await column.hover()
      await mobile.mouse.wheel(0, 100)
      await expect(mobile.locator('.uni-picker-view-content')).toHaveAttribute('style', /translateY\(-34px\)/)
      await mobile.locator('.uni-picker-action-confirm:visible').tap()
      await expect(mobile.locator('uni-picker')).toContainText('已验证手机号')
    }
    await mobile.getByRole('textbox').nth(0).fill(item.identifier)
    await mobile.getByRole('textbox').nth(1).fill(item.password)
    await mobile.getByText('学校编码', { exact: true }).click()
    await mobile.getByRole('textbox').nth(2).fill(tenant)
    await mobile.getByText('我已阅读并同意学校提供的', { exact: true }).click()
    const response = mobile.waitForResponse(r => r.url().includes('/auth/browser-login') && r.request().method() === 'POST', { timeout: 20000 })
    await mobile.locator('uni-button.account-button').click()
    expect((await response).status()).toBe(200)
    await expect(mobile).toHaveURL(new RegExp(item.home.replaceAll('/', '\\/')))
    await context.close()
  }
})
