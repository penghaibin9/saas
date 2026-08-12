import { expect } from '../lib/observability.mjs'

function accessTokenFromEnvelope(payload) {
  return String(payload?.data?.accessToken || '')
}

export class StaffLoginPage {
  constructor(page, baseUrl) {
    this.page = page
    this.baseUrl = baseUrl
    this.lastAccessToken = ''
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
      response.url().includes('/api/v1/auth/browser-login') && response.request().method() === 'POST'
    )
    await this.page.getByRole('button', { name: /进入教师工作台|登录中/ }).click()
    const response = await responsePromise
    expect(response.ok(), `staff login HTTP ${response.status()}`).toBeTruthy()
    this.lastAccessToken = accessTokenFromEnvelope(await response.json())
    expect(this.lastAccessToken, 'staff browser-login must return an in-memory access token').toBeTruthy()
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
    const oldToken = this.lastAccessToken
    const responsePromise = this.page.waitForResponse((response) =>
      response.url().includes('/api/v1/auth/browser-switch-role') && response.request().method() === 'POST'
    )
    await target.click()
    const response = await responsePromise
    expect(response.ok(), `staff role switch HTTP ${response.status()}`).toBeTruthy()
    const newToken = accessTokenFromEnvelope(await response.json())
    expect(newToken, 'browser role switch must return an in-memory access token').toBeTruthy()
    if (oldToken) expect(newToken).not.toBe(oldToken)
    this.lastAccessToken = newToken
    await this.page.waitForURL(/\/workbench/, { timeout: 60_000 })
  }

  async token() {
    return this.lastAccessToken
  }

  async currentRoleText() {
    return (await this.page.locator('.uchip__role').first().innerText()).trim()
  }
}

export class StudentLoginPage {
  constructor(page, baseUrl) {
    this.page = page
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.lastAccessToken = ''
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
      response.url().includes('/api/v1/auth/browser-login') && response.request().method() === 'POST'
    )
    await this.page.getByRole('button', { name: /进入学生服务门户|登录中/ }).click()
    const response = await responsePromise
    expect(response.ok(), `student login HTTP ${response.status()}`).toBeTruthy()
    this.lastAccessToken = accessTokenFromEnvelope(await response.json())
    expect(this.lastAccessToken, 'student browser-login must return an in-memory access token').toBeTruthy()
    await this.page.waitForURL((url) => !url.pathname.endsWith('/login'), { timeout: 60_000 })
  }
}

export function decodeJwt(token) {
  const [, payload] = token.split('.')
  if (!payload) throw new Error('Malformed JWT')
  return JSON.parse(Buffer.from(payload.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'))
}