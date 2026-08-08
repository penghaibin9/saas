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
    await target.click()
    await this.page.waitForURL(/\/workbench/, { timeout: 60_000 })
    await expect.poll(() => this.token(), { timeout: 15_000 }).not.toBe(oldToken)
  }

  async token() {
    // 身份切换会轮换 token 并触发导航；evaluate 恰好撞上旧 document 被销毁时应重试，
    // 不能把正常导航误判成产品失败。
    let lastError
    for (let attempt = 0; attempt < 6; attempt += 1) {
      try {
        await this.page.waitForLoadState('domcontentloaded', { timeout: 5_000 }).catch(() => {})
        return await this.page.evaluate(() => sessionStorage.getItem('gx_pc_token_v1') || '')
      } catch (error) {
        lastError = error
        const message = String(error?.message || error)
        if (!/Execution context was destroyed|navigation|Cannot find context/i.test(message)) throw error
        await this.page.waitForTimeout(100)
      }
    }
    throw lastError
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
