import { expect } from '../lib/observability.mjs'

export class StaffLoginPage {
  constructor(page, baseUrl) {
    this.page = page
    this.baseUrl = baseUrl
  }

  async login(account) {
    await this.page.goto(`${this.baseUrl}/login?tenant=${encodeURIComponent(account.tenant)}`)
    await this.page.locator('#staff-account').fill(account.username)
    await this.page.locator('#staff-password').fill(account.password)

    const details = this.page.locator('details.tenant-details')
    if (await details.count()) {
      if (!(await details.getAttribute('open'))) await details.locator('summary').click()
      await this.page.locator('#staff-tenant').fill(account.tenant)
    }

    const agreement = this.page.locator('label.agreement input[type=checkbox]')
    if (await agreement.count() && !(await agreement.isChecked())) await agreement.check()

    const responsePromise = this.page.waitForResponse((response) =>
      response.url().includes('/api/v1/auth/login') && response.request().method() === 'POST'
    )
    await this.page.getByRole('button', { name: /进入教师工作台|登录中/ }).click()
    const response = await responsePromise
    expect(response.ok(), `staff login HTTP ${response.status()}`).toBeTruthy()
    await this.page.waitForURL((url) => !url.pathname.endsWith('/login'), { timeout: 60_000 })
    await expect(this.page.locator('body')).not.toContainText('登录失败')
  }

  async switchRole(rolePattern) {
    await this.page.getByRole('button', { name: /身份列表/ }).click()
    const menu = this.page.locator('.uchip__menu')
    await expect(menu).toBeVisible()
    const target = menu.locator('button.uchip__ctx').filter({ hasText: rolePattern }).first()
    await expect(target, `missing role context ${rolePattern}`).toBeVisible()
    if (await target.isDisabled()) return

    const oldToken = await this.token()
    const responsePromise = this.page.waitForResponse((response) =>
      response.url().includes('/api/v1/auth/switch-role') && response.request().method() === 'POST'
    )
    // 产品在身份切换成功后用 location.replace('/workbench') 整页刷新。当前页本来可能就是
    // /workbench，所以 waitForURL(/workbench/) 会误判为“已完成”；必须等这一次真实主框架导航。
    const navigationPromise = this.page.waitForEvent('framenavigated', (frame) =>
      frame === this.page.mainFrame() && new URL(frame.url()).pathname === '/workbench'
    )

    await target.click()
    const response = await responsePromise
    expect(response.ok(), `switch role HTTP ${response.status()}`).toBeTruthy()
    const payload = await response.json()
    const newToken = payload?.data?.accessToken || ''
    expect(newToken, 'switch role response must rotate access token').toBeTruthy()
    expect(newToken, 'switch role access token must differ from old token').not.toBe(oldToken)

    await navigationPromise
    await this.page.waitForLoadState('domcontentloaded')
    await this.page.waitForFunction(
      (expected) => sessionStorage.getItem('gx_pc_token_v1') === expected,
      newToken,
      { timeout: 10_000 }
    )
  }

  async token() {
    return this.page.evaluate(() => sessionStorage.getItem('gx_pc_token_v1') || '')
  }

  async currentRoleText() {
    return (await this.page.locator('.uchip__role').first().innerText()).trim()
  }
}

export class StudentLoginPage {
  constructor(page, baseUrl) {
    this.page = page
    this.baseUrl = baseUrl.replace(/\/+$/, '')
  }

  async login(account) {
    await this.page.goto(`${this.baseUrl}/login?tenant=${encodeURIComponent(account.tenant)}`)
    await this.page.locator('#student-account').fill(account.username)
    await this.page.locator('#student-password').fill(account.password)

    const details = this.page.locator('details.tenant-details')
    if (await details.count()) {
      if (!(await details.getAttribute('open'))) await details.locator('summary').click()
      await this.page.locator('#student-tenant').fill(account.tenant)
    }

    const agreement = this.page.locator('label.agreement input[type=checkbox]')
    if (!(await agreement.isChecked())) await agreement.check()

    const responsePromise = this.page.waitForResponse((response) =>
      response.url().includes('/api/v1/auth/login') && response.request().method() === 'POST'
    )
    await this.page.getByRole('button', { name: /进入学生服务门户|登录中/ }).click()
    const response = await responsePromise
    expect(response.ok(), `student login HTTP ${response.status()}`).toBeTruthy()
    await this.page.waitForURL((url) => !url.pathname.endsWith('/login'), { timeout: 60_000 })
  }
}

export function decodeJwt(token) {
  const [, payload] = token.split('.')
  if (!payload) throw new Error('Malformed JWT')
  return JSON.parse(Buffer.from(payload.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'))
}
