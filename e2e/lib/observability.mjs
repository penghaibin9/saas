import fs from 'node:fs/promises'
import path from 'node:path'
import { test as base, expect } from '@playwright/test'
import { config } from './config.mjs'
import { browserSessionForAccessToken } from './api-fixture.mjs'

const SECRET_KEY = /(authorization|cookie|set-cookie|password|token|secret)/i
const bootstrapSessionByPage = new WeakMap()

function redact(value, depth = 0) {
  if (depth > 5) return '[truncated]'
  if (Array.isArray(value)) return value.slice(0, 50).map((item) => redact(item, depth + 1))
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [
      key,
      SECRET_KEY.test(key) ? '[redacted]' : redact(item, depth + 1)
    ]))
  }
  if (typeof value === 'string' && value.length > 2_000) return `${value.slice(0, 2_000)}…`
  return value
}

function safeJson(text) {
  if (!text) return null
  try { return redact(JSON.parse(text)) } catch { return String(text).slice(0, 2_000) }
}

function testClientIp(testInfo) {
  const seed = [...String(testInfo.testId || testInfo.title)].reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return `10.253.${Math.floor(seed / 200) % 200}.${20 + (seed % 200)}`
}

function safeLabel(label) {
  return String(label || 'page').replace(/[^a-zA-Z0-9_-]+/g, '-').replace(/^-+|-+$/g, '') || 'page'
}

function browserChannel(session, source) {
  const userType = String(session?.userType || '').toUpperCase()
  const roleCode = String(session?.roleCode || '').toUpperCase()
  if (userType.startsWith('PLATFORM_') || roleCode === 'PLATFORM_SUPER_ADMIN') return 'platform'
  if (userType === 'STUDENT' || roleCode === 'STUDENT' || source.includes('sp_token_v1')) return 'student'
  return 'staff'
}

function refreshTokenFromSetCookie(headers, cookieName) {
  const prefix = `${cookieName}=`
  for (const header of headers || []) {
    if (String(header?.name || '').toLowerCase() !== 'set-cookie') continue
    const value = String(header?.value || '')
    if (!value.startsWith(prefix)) continue
    const token = value.slice(prefix.length).split(';', 1)[0]
    if (token) return token
  }
  return ''
}

async function syncSecureE2EBootstrap(page, response = null) {
  const bootstrap = bootstrapSessionByPage.get(page)
  if (!bootstrap) return

  // Refresh tokens are one-time and rotate on every successful browser refresh. Capture the
  // authoritative replacement directly from Set-Cookie before another isolated test context can
  // reuse the now-consumed predecessor. Cookie enumeration remains a fallback for final cleanup.
  if (response) {
    const headers = await response.headersArray().catch(() => [])
    const rotated = refreshTokenFromSetCookie(headers, bootstrap.cookieName)
    if (rotated) {
      bootstrap.session.refreshToken = rotated
      return
    }
  }

  const cookies = await page.context().cookies().catch(() => [])
  const matches = cookies.filter((cookie) => cookie.name === bootstrap.cookieName && cookie.value)
  const current = matches.at(-1)
  if (current?.value) bootstrap.session.refreshToken = current.value
}

async function navigateWithSecureBootstrap(page, navigate) {
  const bootstrap = bootstrapSessionByPage.get(page)
  if (!bootstrap) return navigate()

  // Every full navigation destroys the app's in-memory access token, so the next document must
  // finish one real browser-refresh before a visual spec is allowed to trigger another reload or
  // goto. Without this barrier, a second navigation can abort the first response after the server
  // has already consumed its one-time refresh token, leaving the browser with the spent cookie.
  const refreshSettled = page.waitForResponse(
    (response) => response.url().includes('/api/v1/auth/browser-refresh') && response.request().method() === 'POST',
    { timeout: 15_000 }
  ).catch(() => null)
  const result = await navigate()
  const response = await refreshSettled
  if (response?.ok()) await syncSecureE2EBootstrap(page, response)
  return result
}

async function installSecureE2EBootstrap(page) {
  // Older visual specs used addInitScript(sessionStorage.setItem(...)) to bootstrap a page.
  // Production code now deletes those legacy keys by design. Intercept only that E2E pattern and
  // translate the API fixture's refresh token into a real HttpOnly browser cookie. The app then
  // obtains its access token through its own /browser-refresh path; product source never reads
  // Web Storage. Browser refresh tokens rotate on every use, so persist the browser's actual
  // HttpOnly replacement cookie back into the E2E session before the next isolated test context.
  const nativeAddInitScript = page.addInitScript.bind(page)
  const nativeGoto = page.goto.bind(page)
  const nativeReload = page.reload.bind(page)

  page.goto = (...args) => navigateWithSecureBootstrap(page, () => nativeGoto(...args))
  page.reload = (...args) => navigateWithSecureBootstrap(page, () => nativeReload(...args))

  page.addInitScript = async (script, arg) => {
    const source = typeof script === 'function' ? String(script) : String(script?.content || script || '')
    const accessToken = String(typeof arg === 'string' ? arg : (arg?.token || ''))
    const legacyBootstrap = accessToken && /(gx_pc_token_v1|sp_token_v1)/.test(source)
    if (!legacyBootstrap) return nativeAddInitScript(script, arg)

    const session = browserSessionForAccessToken(accessToken)
    if (!session?.refreshToken) {
      throw new Error('Legacy E2E bootstrap has no matching refresh session; use real browser login')
    }
    const channel = browserChannel(session, source)
    const base = new URL(channel === 'student' ? config.studentBaseUrl : config.staffBaseUrl)
    const cookieName = `gx_${channel}_refresh_v1`
    bootstrapSessionByPage.set(page, { session, cookieName })

    const onResponse = async (response) => {
      if (!response.ok() || !response.url().includes('/api/v1/auth/browser-refresh')) return
      await syncSecureE2EBootstrap(page, response)
    }
    page.on('response', onResponse)

    await page.context().addCookies([{
      name: cookieName,
      value: session.refreshToken,
      domain: base.hostname,
      path: '/api/v1/auth',
      httpOnly: true,
      secure: base.protocol === 'https:',
      sameSite: 'Strict'
    }])
  }
}

export async function attachObservability(page, testInfo, { label = 'page', clientIp = '' } = {}) {
  const network = []
  const consoleErrors = []
  const pageErrors = []
  const started = new Map()
  const prefix = safeLabel(label)
  let finalized = false

  if (clientIp) await page.setExtraHTTPHeaders({ 'X-Forwarded-For': clientIp })

  page.on('request', (request) => {
    if (!request.url().includes('/api/')) return
    started.set(request, Date.now())
    network.push({
      type: 'request',
      at: new Date().toISOString(),
      method: request.method(),
      url: request.url(),
      headers: redact(request.headers()),
      body: safeJson(request.postData())
    })
  })
  page.on('response', (response) => {
    const request = response.request()
    if (!request.url().includes('/api/')) return
    network.push({
      type: 'response',
      at: new Date().toISOString(),
      method: request.method(),
      url: response.url(),
      status: response.status(),
      durationMs: started.has(request) ? Date.now() - started.get(request) : null
    })
  })
  page.on('requestfailed', (request) => {
    if (!request.url().includes('/api/')) return
    network.push({
      type: 'requestfailed',
      at: new Date().toISOString(),
      method: request.method(),
      url: request.url(),
      failure: request.failure()
    })
  })
  page.on('console', (message) => {
    if (message.type() !== 'error') return
    const text = message.text()
    if (/favicon|source map|Vue Devtools/i.test(text)) return
    consoleErrors.push({ at: new Date().toISOString(), text })
  })
  page.on('pageerror', (error) => {
    pageErrors.push({ at: new Date().toISOString(), message: error.message, stack: error.stack })
  })

  return async function finalizeObservability() {
    if (finalized) return
    finalized = true
    const dir = testInfo.outputDir
    await fs.mkdir(dir, { recursive: true })
    const write = async (suffix, data) => {
      const name = `${prefix}-${suffix}`
      const file = path.join(dir, name)
      await fs.writeFile(file, data, 'utf8')
      await testInfo.attach(name, {
        path: file,
        contentType: name.endsWith('.json') ? 'application/json' : 'text/plain'
      })
    }
    await write('api-network.json', JSON.stringify(network, null, 2))
    await write('console-errors.json', JSON.stringify(consoleErrors, null, 2))
    await write('page-errors.json', JSON.stringify(pageErrors, null, 2))
    if (pageErrors.length) {
      throw new Error(
        `${prefix} had unhandled browser page errors: ${pageErrors.map((item) => item.message).join(' | ')}`
      )
    }
  }
}

export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    // The backend still enforces its real 10 logins/minute/IP guard. Each legitimate
    // Playwright test receives a distinct trusted-proxy client IP so serial role flows
    // do not incorrectly throttle one another on the shared GitHub runner loopback.
    await installSecureE2EBootstrap(page)
    const finalize = await attachObservability(page, testInfo, {
      label: 'default-page',
      clientIp: testClientIp(testInfo)
    })
    try {
      await use(page)
    } finally {
      await syncSecureE2EBootstrap(page)
      await finalize()
    }
  }
})

export { expect }