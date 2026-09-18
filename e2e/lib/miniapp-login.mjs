export async function loginMiniH5(page, { baseUrl, entry = 'student', account, timeout = 20_000 }) {
  const kind = entry === 'teacher' ? 'teacher' : 'student'
  const loginName = String(account?.username || account?.loginName || '')
  const password = String(account?.password || '')
  const tenant = String(account?.tenant || account?.tenantCode || '').trim()
  if (!loginName || !password) throw new Error('miniapp login account is incomplete')

  await page.goto(`${baseUrl}/#/pages/login/${kind}/index`)

  const accountLabel = kind === 'teacher' ? '工号或统一账号' : '学号或统一账号'
  const accountPlaceholder = kind === 'teacher' ? '请输入工号或统一账号' : '请输入学号或统一账号'
  const accountInput = page.locator(`input[aria-label="${accountLabel}"], input[placeholder="${accountPlaceholder}"]`).first()
  await accountInput.waitFor({ state: 'visible', timeout })
  await accountInput.fill(loginName)

  const passwordInput = page.locator('input[aria-label="密码"], input[placeholder="密码"]').first()
  await passwordInput.waitFor({ state: 'visible', timeout })
  await passwordInput.fill(password)

  if (tenant) {
    let tenantInput = page.locator('input.field--tenant')
    if ((await tenantInput.count()) === 0) {
      const tenantToggle = page.locator('button.tenant-box')
      await tenantToggle.waitFor({ state: 'visible', timeout })
      await tenantToggle.click()
      tenantInput = page.locator('input.field--tenant')
    }
    await tenantInput.waitFor({ state: 'visible', timeout })
    await tenantInput.fill(tenant)
  }

  const agreement = page.locator('button.agreement-toggle[aria-label="同意用户协议与隐私政策"]')
  await agreement.waitFor({ state: 'visible', timeout })
  if ((await agreement.getAttribute('aria-checked')) !== 'true') await agreement.click()

  const action = kind === 'teacher' ? '进入教师工作台' : '进入学生首页'
  const loginButton = page.locator('button.account-button').filter({ hasText: action })
  await loginButton.waitFor({ state: 'visible', timeout })
  await loginButton.click()
  await page.waitForURL(
    kind === 'teacher' ? /pages\/teacher\/workbench\/index/ : /pages\/student\/home\/index/,
    { timeout }
  )
}
