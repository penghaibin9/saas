import { createHash } from 'node:crypto'
import { expect } from '../lib/observability.mjs'

const BROWSER_LOGIN_WINDOW_MS = 60_000
const BROWSER_LOGIN_SAFE_LIMIT = 9
const BROWSER_LOGIN_HEADROOM_MS = 500
const browserLoginStarts = []
let browserLoginPace = Promise.resolve()

function accessTokenFromEnvelope(payload) {
  return String(payload?.data?.accessToken || '')
}

export async function paceBrowserLogin(page) {
  let release
  const previous = browserLoginPace
  browserLoginPace = new Promise((resolve) => { release = resolve })
  await previous
  try {
    const pruneExpired = () => {
      const now = Date.now()
      while (browserLoginStarts.length && now - browserLoginStarts[0] >= BROWSER_LOGIN_WINDOW_MS) {
        browserLoginStarts.shift()
      }
    }
    pruneExpired()
    if (browserLoginStarts.length >= BROWSER_LOGIN_SAFE_LIMIT) {
      const waitMs = Math.max(
        0,
        BROWSER_LOGIN_WINDOW_MS - (Date.now() - browserLoginStarts[0]) + BROWSER_LOGIN_HEADROOM_MS
      )
      if (waitMs > 0) await page.waitForTimeout(waitMs)
      pruneExpired()
    }
    browserLoginStarts.push(Date.now())
  } finally {
    release()
  }
}

async function browserRefreshCookie(page, channel = 'staff') {
  const sessionId = await page.evaluate(() => String(sessionStorage.getItem('gx_browser_session_id_v2') || ''))
  if (!sessionId) return ''
  const suffix = createHash('sha256').update(sessionId).digest('hex').slice(0, 24)
  const name = `gx_${channel}_refresh_v2_${suffix}`
  const cookies = await page.context().cookies()
  return String(cookies.find((cookie) => cookie.name === name)?.value || '')
}

function roleMatches(text, pattern) {
  const value = String(text || '')
  if (pattern instanceof RegExp) {
    pattern.lastIndex = 0
    const matched = pattern.test(value)
    pattern.lastIndex = 0
    return matched
  }
  return value.includes(String(pattern || ''))
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

    // The production auth contract intentionally limits one client IP to 10 login attempts per
    // rolling minute. Browser E2E exercises many real roles from one runner IP, so respect that
    // contract with headroom instead of spoofing X-Forwarded-For or weakening the backend limit.
    await paceBrowserLogin(this.page)
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
    const currentRole = await this.currentRoleText().catch(() => '')
    if (roleMatches(currentRole, rolePattern)) return

    await this.page.getByRole('button', { name: /身份列表/ }).click()
    const menu = this.page.locator('.uchip__menu')
    await expect(menu).toBeVisible()
    const target = menu.locator('button.uchip__ctx').filter({ hasText: rolePattern }).first()
    await expect(target, `missing role context ${rolePattern}`).toBeVisible()
    if (await target.isDisabled()) return

    const oldRefreshToken = await browserRefreshCookie(this.page, 'staff')
    expect(oldRefreshToken, 'staff role switch must start from an HttpOnly refresh session').toBeTruthy()
    const responsePromise = this.page.waitForResponse((response) =>
      response.url().includes('/api/v1/auth/browser-switch-role') && response.request().method() === 'POST'
    )
    // The role switch replaces the access token in the current document and then hard-navigates
    // to /workbench.  The new document has no in-memory access token, so its first bootstrap call
    // consumes and rotates the new HttpOnly refresh session.  Capture that response before the
    // click: waiting only for `networkidle` can return during the short quiet window before this
    // bootstrap refresh starts, and an immediate deep link would abort the one-shot rotation.
    const bootstrapRefreshPromise = this.page.waitForResponse(
      (response) => response.url().includes('/api/v1/auth/browser-refresh')
        && response.request().method() === 'POST',
      { timeout: 60_000 },
    ).catch(() => null)
    const navigationPromise = this.page.waitForEvent('framenavigated', {
      predicate: (frame) => frame === this.page.mainFrame(),
      timeout: 60_000,
    })
    await target.click()
    const response = await responsePromise
    expect(response.ok(), `staff role switch HTTP ${response.status()}`).toBeTruthy()
    await navigationPromise
    const bootstrapRefresh = await bootstrapRefreshPromise
    expect(bootstrapRefresh, 'staff role switch must finish the new document refresh bootstrap').toBeTruthy()
    expect(bootstrapRefresh.ok(), `staff post-switch refresh HTTP ${bootstrapRefresh.status()}`).toBeTruthy()
    await expect(this.page).toHaveURL(/\/workbench/)

    await expect.poll(
      () => browserRefreshCookie(this.page, 'staff'),
      { timeout: 5_000, message: 'staff role switch must rotate the durable browser session' }
    ).not.toBe(oldRefreshToken)
    const newRefreshToken = await browserRefreshCookie(this.page, 'staff')
    expect(newRefreshToken, 'staff role switch must leave a resumable HttpOnly refresh session').toBeTruthy()
    // The app navigates only after switchAuthContext succeeds. Combining the real switch response,
    // rotated HttpOnly cookie, completed main-frame navigation and caller-side role UI assertion proves the
    // switch without racing response delivery against window.location.replace().
    this.lastAccessToken = ''
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

    await paceBrowserLogin(this.page)
    const responsePromise = this.page.waitForResponse((response) =>
      response.url().includes('/api/v1/auth/browser-login') && response.request().method() === 'POST'
    )
    await this.page.getByRole('button', { name: /进入学生服务门户|登录中/ }).click()
    const response = await responsePromise
    expect(response.ok(), `student login HTTP ${response.status()}`).toBeTruthy()
    this.lastAccessToken = accessTokenFromEnvelope(await response.json())
    expect(this.lastAccessToken, 'student browser-login must return an in-memory access token').toBeTruthy()
    await this.page.waitForURL((url) => !url.pathname.endsWith('/login'), { timeout: 60_000 })
    // Browser First specs often deep-link immediately after login. Let the portal's initial
    // auth/bootstrap traffic settle first so a hard navigation cannot abort a refresh-token
    // rotation after the backend has already consumed the old HttpOnly cookie.
    await this.page.waitForLoadState('networkidle', { timeout: 60_000 })
  }
}

export function decodeJwt(token) {
  const [, payload] = token.split('.')
  if (!payload) throw new Error('Malformed JWT')
  return JSON.parse(Buffer.from(payload.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'))
}
