import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'

const FIXTURE = JSON.parse(fs.readFileSync(
  path.resolve(process.cwd(), 'runtime-fixtures/module-commerce-m2.json'),
  'utf8'
))

const CORE = {
  internship: {
    label: '岗位实习中心',
    route: '/admin/internship',
    api: '/internship/dashboard',
    contextKeys: ['internship'],
  },
  graduationDesign: {
    label: '毕业设计中心',
    route: '/admin/graduation',
    api: '/graduation/dashboard',
    contextKeys: ['graduationDesign', 'graduation'],
  },
  studentAffairs: {
    label: '学工中心',
    route: '/admin/student-affairs/dashboard',
    api: '/student-affairs/dashboard',
    contextKeys: ['studentAffairs'],
  },
  academicAffairs: {
    label: '教务中心',
    route: '/admin/academic-affairs',
    api: '/academic-affairs/dashboard',
    contextKeys: ['academicAffairs', 'academicLegacy'],
  },
}

function cookieName(session) {
  const digest = crypto.createHash('sha256').update(session.browserSessionId).digest('hex').slice(0, 24)
  return `gx_staff_refresh_v2_${digest}`
}

async function installSession(context, session) {
  const api = new URL(config.apiBaseUrl)
  await context.addCookies([{
    name: cookieName(session),
    value: session.refreshToken,
    domain: api.hostname,
    path: '/api/v1/auth',
    httpOnly: true,
    secure: false,
    sameSite: 'Strict',
  }])
  await context.addInitScript(({ browserSessionId }) => {
    sessionStorage.setItem('gx_browser_session_id_v2', browserSessionId)
  }, { browserSessionId: session.browserSessionId })
}

async function openWorkbench(page) {
  const refresh = page.waitForResponse((response) => (
    response.request().method() === 'POST'
    && new URL(response.url()).pathname === '/api/v1/auth/browser-refresh'
  ), { timeout: 60_000 })
  await page.goto(new URL('/workbench', config.staffBaseUrl).toString())
  const response = await refresh
  expect(response.status()).toBe(200)
  const body = await response.json()
  expect(body?.code).toBe(0)
  const token = String(body?.data?.accessToken || '')
  expect(token.split('.')).toHaveLength(3)
  await expect(page).not.toHaveURL(/\/(login|platform-login)(?:\?|$)/)
  return token
}

async function apiRaw(page, token, requestPath) {
  return page.evaluate(async ({ apiBaseUrl, tokenValue, pathValue }) => {
    const response = await fetch(`${apiBaseUrl}${pathValue}`, {
      headers: { Accept: 'application/json', Authorization: `Bearer ${tokenValue}` },
    })
    const text = await response.text()
    let json
    try { json = JSON.parse(text) } catch { json = { message: text.slice(0, 1000) } }
    return { status: response.status, json }
  }, { apiBaseUrl: config.apiBaseUrl, tokenValue: token, pathValue: requestPath })
}

function dataOf(result) {
  expect(result.status, JSON.stringify(result.json)).toBe(200)
  expect(result.json?.code, JSON.stringify(result.json)).toBe(0)
  return result.json?.data
}

function hasAny(set, candidates) {
  return candidates.some((item) => set.has(item))
}

async function assertRoute(page, route, expectedAllowed) {
  await page.goto(new URL(route, config.staffBaseUrl).toString())
  await expect.poll(async () => {
    const final = new URL(page.url())
    const body = await page.locator('body').innerText().catch(() => '')
    const denied = final.pathname === '/security/403' || /403|无权限|禁止访问|没有权限/.test(body)
    return expectedAllowed ? !denied && !/\/(login|platform-login)$/.test(final.pathname) : denied
  }, {
    message: `${route} expectedAllowed=${expectedAllowed} final=${page.url()}`,
    timeout: 30_000,
  }).toBe(true)
}

function writeEvidence(rows) {
  const target = path.resolve(process.cwd(), 'test-results/module-commerce-m2-evidence.json')
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.writeFileSync(target, JSON.stringify({
    schemaVersion: 1,
    card: 'PLAT-M2-16-COMBINATIONS',
    headSha: process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || '',
    realBrowser: true,
    realApi: true,
    isolatedMySql: true,
    mockSuccess: false,
    legacyFeatureOverrideUsed: false,
    comboCount: rows.length,
    combinations: rows,
  }, null, 2))
}

test('M2 sixteen commercial module combinations stay exact across browser, route and API gates', async ({ browser }) => {
  const expectedSha = process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || ''
  expect(FIXTURE.headSha).toBe(expectedSha)
  expect(FIXTURE.realPaidOrderItemSources).toBe(true)
  expect(FIXTURE.legacyFeatureOverrideUsed).toBe(false)
  expect(FIXTURE.sessions).toHaveLength(16)
  const evidence = []

  for (const [index, session] of FIXTURE.sessions.entries()) {
    const selected = new Set(session.selectedModules || [])
    const context = await browser.newContext({
      extraHTTPHeaders: { 'X-Forwarded-For': `10.253.16.${index + 20}` },
    })
    try {
      await installSession(context, session)
      const page = await context.newPage()
      const token = await openWorkbench(page)

      const currentContext = dataOf(await apiRaw(page, token, '/rbac/current-context'))
      expect(currentContext.moduleAccessHealthy).toBe(true)
      const moduleEntitlements = new Set(currentContext.moduleEntitlements || [])
      for (const [moduleKey, contract] of Object.entries(CORE)) {
        const expected = selected.has(moduleKey)
        expect(hasAny(moduleEntitlements, contract.contextKeys), `${session.mask}:${moduleKey}:context`).toBe(expected)
      }

      const railLabels = await page.locator('.bpl-rail__lb').allInnerTexts()
      for (const [moduleKey, contract] of Object.entries(CORE)) {
        expect(railLabels.includes(contract.label), `${session.mask}:${moduleKey}:rail`).toBe(selected.has(moduleKey))
      }

      const row = {
        mask: session.mask,
        tenantId: session.tenantId,
        selectedModules: [...selected].sort(),
        currentContextCoreExact: true,
        railCoreExact: true,
        routes: {},
        apis: {},
        employmentDenied: false,
        apiAccessDenied: false,
        platformPlaneDenied: false,
      }

      for (const [moduleKey, contract] of Object.entries(CORE)) {
        const expected = selected.has(moduleKey)
        await assertRoute(page, contract.route, expected)
        row.routes[moduleKey] = expected ? 'ALLOWED' : 'DENIED'

        const result = await apiRaw(page, token, contract.api)
        if (expected) {
          expect(result.status, `${session.mask}:${moduleKey}:${JSON.stringify(result.json)}`).toBe(200)
          expect(result.json?.code, JSON.stringify(result.json)).toBe(0)
          row.apis[moduleKey] = 'ALLOWED'
        } else {
          expect(result.status, `${session.mask}:${moduleKey}:${JSON.stringify(result.json)}`).toBe(403)
          expect(result.json?.code, JSON.stringify(result.json)).not.toBe(0)
          row.apis[moduleKey] = 'DENIED'
        }
      }

      const employment = await apiRaw(page, token, '/employment/dashboard')
      expect(employment.status, JSON.stringify(employment.json)).toBe(403)
      row.employmentDenied = true

      const apiAccess = await apiRaw(page, token, '/system/integrations')
      expect(apiAccess.status, JSON.stringify(apiAccess.json)).toBe(403)
      row.apiAccessDenied = true

      const platform = await apiRaw(page, token, '/platform/context')
      expect([401, 403, 404], JSON.stringify(platform.json)).toContain(platform.status)
      row.platformPlaneDenied = true

      expect(session.commercialFeatureKeys.includes('employment')).toBe(false)
      expect(session.commercialFeatureKeys.includes('apiAccess')).toBe(false)
      evidence.push(row)
    } finally {
      await context.close()
    }
  }

  writeEvidence(evidence)
  expect(evidence).toHaveLength(16)
})
