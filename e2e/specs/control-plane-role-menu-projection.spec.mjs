import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'

const FIXTURE = JSON.parse(fs.readFileSync(
  path.resolve(process.cwd(), 'runtime-fixtures/control-plane-role-projection.json'),
  'utf8'
))

function cookieName(session) {
  const digest = crypto.createHash('sha256').update(session.browserSessionId).digest('hex').slice(0, 24)
  const prefix = session.channel === 'platform' ? 'gx_platform_refresh_v2_' : 'gx_staff_refresh_v2_'
  return `${prefix}${digest}`
}

async function installRealBrowserSession(context, session) {
  const api = new URL(config.apiBaseUrl)
  await context.addCookies([{
    name: cookieName(session),
    value: session.refreshToken,
    domain: api.hostname,
    path: '/api/v1/auth',
    httpOnly: true,
    secure: false,
    sameSite: 'Strict'
  }])
  await context.addInitScript(({ browserSessionId }) => {
    sessionStorage.setItem('gx_browser_session_id_v2', browserSessionId)
  }, { browserSessionId: session.browserSessionId })
}

async function openWithRotatedSession(page, session) {
  const refresh = page.waitForResponse((response) => (
    response.request().method() === 'POST'
    && new URL(response.url()).pathname === '/api/v1/auth/browser-refresh'
  ), { timeout: 60_000 })
  await page.goto(new URL(session.visiblePath, config.staffBaseUrl).toString())
  const response = await refresh
  expect(response.status(), `${session.roleCode} browser refresh`).toBe(200)
  const payload = await response.json()
  const token = String(payload?.data?.accessToken || '')
  expect(token.split('.')).toHaveLength(3)
  await expect(page).not.toHaveURL(/\/(login|platform-login)(?:\?|$)/)
  return token
}

async function browserApiRaw(page, token, requestPath, { method = 'GET', body } = {}) {
  return page.evaluate(async ({ apiBaseUrl, tokenValue, pathValue, methodValue, bodyValue }) => {
    const response = await fetch(`${apiBaseUrl}${pathValue}`, {
      method: methodValue,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${tokenValue}`,
        ...(bodyValue === undefined ? {} : { 'Content-Type': 'application/json' })
      },
      ...(bodyValue === undefined ? {} : { body: JSON.stringify(bodyValue) })
    })
    const text = await response.text()
    let json
    try { json = JSON.parse(text) } catch { json = { message: text.slice(0, 1000) } }
    return { status: response.status, json }
  }, {
    apiBaseUrl: config.apiBaseUrl,
    tokenValue: token,
    pathValue: requestPath,
    methodValue: method,
    bodyValue: body
  })
}

async function passwordRelogAsRole(page, roleCode) {
  const browserSessionId = `w12-relog-${roleCode.toLowerCase()}-${Date.now()}`
  await page.goto(new URL('/login', config.staffBaseUrl).toString())
  await page.evaluate(({ id }) => {
    sessionStorage.setItem('gx_browser_session_id_v2', id)
  }, { id: browserSessionId })
  const switchedToken = await page.evaluate(async ({ apiBaseUrl, browserSessionId: id, fixture, targetRole }) => {
    const call = async (pathValue, options = {}) => {
      const response = await fetch(`${apiBaseUrl}${pathValue}`, {
        credentials: 'include',
        ...options,
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-Browser-Session': 'staff',
          'X-Browser-Session-Id': id,
          ...(options.headers || {})
        }
      })
      const json = await response.json()
      if (response.status !== 200 || json?.code !== 0) {
        throw new Error(`${pathValue}: ${response.status} ${JSON.stringify(json)}`)
      }
      return json.data
    }
    const loggedIn = await call('/auth/browser-login', {
      method: 'POST',
      body: JSON.stringify({
        tenantCode: fixture.schoolTenantCode,
        loginName: fixture.schoolLogin,
        password: fixture.schoolPassword,
        clientType: 'PC'
      })
    })
    const me = await call('/auth/me', {
      headers: { Authorization: `Bearer ${loggedIn.accessToken}` }
    })
    const context = (me.contexts || []).find((item) => item.roleCode === targetRole)
    if (!context) throw new Error(`role context not found after password login: ${targetRole}`)
    const switched = await call('/auth/browser-switch-role', {
      method: 'POST',
      headers: { Authorization: `Bearer ${loggedIn.accessToken}` },
      body: JSON.stringify({ contextId: context.contextId, clientType: 'PC' })
    })
    return String(switched.accessToken || '')
  }, {
    apiBaseUrl: config.apiBaseUrl,
    browserSessionId,
    fixture: FIXTURE,
    targetRole: roleCode
  })
  expect(switchedToken.split('.')).toHaveLength(3)
  const refresh = page.waitForResponse((response) => (
    response.request().method() === 'POST'
    && new URL(response.url()).pathname === '/api/v1/auth/browser-refresh'
  ), { timeout: 60_000 })
  await page.goto(new URL('/workbench', config.staffBaseUrl).toString())
  const refreshResponse = await refresh
  expect(refreshResponse.status(), `${roleCode} refresh after password relog`).toBe(200)
  const payload = await refreshResponse.json()
  return String(payload?.data?.accessToken || '')
}

function responseData(result) {
  expect(result.status, JSON.stringify(result.json)).toBe(200)
  expect(result.json?.code, JSON.stringify(result.json)).toBe(0)
  return result.json?.data
}

async function assertDirectUrlDenied(page, session) {
  const target = new URL(session.hiddenPath, config.staffBaseUrl)
  await page.goto(target.toString())
  await expect.poll(async () => {
    const finalUrl = new URL(page.url())
    const body = await page.locator('body').innerText().catch(() => '')
    return finalUrl.pathname !== target.pathname || /403|无权限|禁止访问|没有权限/.test(body)
  }, {
    message: `${session.roleCode} direct URL unexpectedly entered ${target.pathname}`,
    timeout: 30_000
  }).toBe(true)
}

function writeEvidence(rows) {
  const target = path.resolve(process.cwd(), 'test-results/control-plane-role-projection-evidence.json')
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.writeFileSync(target, JSON.stringify({
    schemaVersion: 1,
    card: 'CTRL-IAM-W12-ROLE-MENU-PROJECTION',
    headSha: process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || '',
    roleCount: rows.length,
    realSignedBrowserSessions: true,
    mockSuccess: false,
    roles: rows
  }, null, 2))
}

test('W12 real Browser Role/Menu Projection Seal covers every school role, platform duty and Product-IAM root', async ({ browser }) => {
  expect(FIXTURE.headSha).toBe(process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || '')
  expect(FIXTURE.sessions).toHaveLength(14)
  const evidence = []

  for (const [index, session] of FIXTURE.sessions.entries()) {
    const context = await browser.newContext({
      extraHTTPHeaders: { 'X-Forwarded-For': `10.254.12.${index + 10}` }
    })
    try {
      await installRealBrowserSession(context, session)
      const page = await context.newPage()
      const token = await openWithRotatedSession(page, session)

      await expect(page.locator('.bpl-rail__lb').filter({ hasText: session.visibleGroup }).first()).toBeVisible()
      await expect(page.locator('.bpl-rail__lb').filter({ hasText: session.hiddenGroup })).toHaveCount(0)

      const visibleRail = page.locator('.bpl-rail__item').filter({ hasText: session.visibleGroup }).first()
      await visibleRail.click()
      await expect(page).not.toHaveURL(/\/security\/403|\/(login|platform-login)(?:\?|$)/)

      const me = responseData(await browserApiRaw(page, token, '/auth/me'))
      expect(me.currentRole?.roleCode).toBe(session.roleCode)

      let dataScope
      let positiveApi
      let crossPlane
      const golden = {}
      if (session.plane === 'SCHOOL') {
        dataScope = String(me.currentRole?.dataScope || '')
        expect(dataScope).toBe(session.expectedDataScope)
        positiveApi = '/auth/me'
        crossPlane = await browserApiRaw(page, token, '/platform/context')
        if (session.roleCode === 'SCHOOL_ADMIN') {
          const productIamDenied = await browserApiRaw(page, token, '/platform/product-iam/source')
          expect([401, 403, 404], JSON.stringify(productIamDenied.json)).toContain(productIamDenied.status)
          golden.schoolAdminProductIamDenied = true
        }
      } else {
        const platform = responseData(await browserApiRaw(page, token, '/platform/context'))
        expect(platform.principalPlane).toBe('PLATFORM')
        expect(platform.roleCode).toBe(session.roleCode)
        expect(Array.isArray(platform.duties) && platform.duties.length > 0).toBe(true)
        dataScope = 'PLATFORM_CAPABILITY'
        positiveApi = '/platform/context'
        crossPlane = await browserApiRaw(page, token, '/system/iam/summary')
        if (session.roleCode === 'PLATFORM_SUPER_ADMIN') {
          const source = responseData(await browserApiRaw(page, token, '/platform/product-iam/source'))
          const current = (source.roleTemplates || []).find((item) => item.templateCode === 'ACADEMIC_ADMIN')
          expect(current).toBeTruthy()
          expect(current.templateVersion).toBeGreaterThan(0)
          expect((current.permissionCodes || []).length).toBeGreaterThan(0)
          expect((current.menuPreview || []).length).toBeGreaterThan(0)

          const currentCodes = new Set(current.permissionCodes || [])
          // A failed/retried exact-head run may leave an unpublished draft in the isolated DB.
          // Select a permission absent from both published truth and the latest version so the
          // new draft always has a real added-permission/menu impact instead of a retry false negative.
          const versions = responseData(await browserApiRaw(
            page,
            token,
            '/platform/product-iam/school-role-templates/ACADEMIC_ADMIN'
          ))
          const latestCodes = new Set((versions.items?.[0]?.permissions) || [])
          const alreadyUsedCodes = new Set([...currentCodes, ...latestCodes])
          const catalog = new Map((source.permissions || []).map((item) => [item.permissionCode, item]))
          const candidateSurface = (source.navigationSurfaces || []).find((item) => {
            const code = String(item.permissionKey || '')
            const permission = catalog.get(code)
            return code && !alreadyUsedCodes.has(code) && !item.platformOnly && !item.hidden && !item.disabled
              && ['implemented', 'partial'].includes(String(item.status || ''))
              && permission?.plane === 'TENANT' && permission?.lifecycle === 'ACTIVE'
              && permission?.tenantAssignable && permission?.customRoleAssignable
              && !code.startsWith('system.')
          })
          expect(candidateSurface, 'ACADEMIC_ADMIN needs one safe menu permission for GJ-02').toBeTruthy()
          const permissionCodes = [...currentCodes, candidateSurface.permissionKey].sort()
          const draft = responseData(await browserApiRaw(
            page,
            token,
            '/platform/product-iam/school-role-templates/ACADEMIC_ADMIN/drafts',
            {
              method: 'POST',
              body: {
                templateName: '教务管理员',
                permissionCodes,
                reason: 'IAM GJ-02 exact-head browser publish proof'
              }
            }
          ))
          const impact = responseData(await browserApiRaw(
            page,
            token,
            `/platform/product-iam/school-role-templates/ACADEMIC_ADMIN/drafts/${encodeURIComponent(draft.id)}/impact`
          ))
          expect(impact.addedPermissions).toContain(candidateSurface.permissionKey)
          expect((impact.menuAdded || []).length).toBeGreaterThan(0)
          expect(impact.sourceDigest).toBe(source.sourceDigest)
          expect(impact.navigationDigest).toBe(source.navigationDigest)

          const publishBody = {
            expectedVersion: Number(draft.version),
            reason: 'IAM GJ-02 MFA publish exact-head proof',
            permissionDigest: draft.permissionDigest,
            sourceDigest: impact.sourceDigest,
            navigationDigest: impact.navigationDigest
          }
          const publishPath = `/platform/product-iam/school-role-templates/ACADEMIC_ADMIN/drafts/${encodeURIComponent(draft.id)}/publish`
          const stale = await browserApiRaw(page, token, publishPath, {
            method: 'POST',
            body: { ...publishBody, expectedVersion: Number(draft.version) - 1 }
          })
          expect(stale.status).toBe(409)
          expect(stale.json?.code).not.toBe(0)
          const published = responseData(await browserApiRaw(page, token, publishPath, {
            method: 'POST',
            body: publishBody
          }))
          expect(published.publishStatus).toBe('PUBLISHED')
          expect(Number(published.templateVersion)).toBeGreaterThan(Number(current.templateVersion))

          const schoolContext = await browser.newContext({
            extraHTTPHeaders: { 'X-Forwarded-For': '10.254.12.240' }
          })
          try {
            await installRealBrowserSession(schoolContext, FIXTURE.schoolAdminGoldenSession)
            const schoolPage = await schoolContext.newPage()
            const schoolToken = await openWithRotatedSession(schoolPage, FIXTURE.schoolAdminGoldenSession)
            const roleList = responseData(await browserApiRaw(
              schoolPage,
              schoolToken,
              '/system/roles?keyword=E2E_CUSTOM_MENU&page=1&page_size=20'
            ))
            const customRole = (roleList.list || []).find((item) => item.code === 'E2E_CUSTOM_MENU')
            expect(customRole).toBeTruthy()
            const beforeCustom = responseData(await browserApiRaw(
              schoolPage,
              schoolToken,
              `/system/roles/${encodeURIComponent(customRole.id)}`
            ))
            expect(beforeCustom.permissionCodes).toContain(FIXTURE.customPermission)
            expect(beforeCustom.permissionCodes).toContain(FIXTURE.legacyPreservedPermission)
            const preservedLegacy = (beforeCustom.readOnlyPreservedPermissions || []).find(
              (item) => item.permissionCode === FIXTURE.legacyPreservedPermission
            )
            expect(preservedLegacy).toBeTruthy()
            expect(preservedLegacy.editable).toBe(false)
            expect(preservedLegacy.reason).toContain('只读保留')
            expect(Number(beforeCustom.version)).toBeGreaterThanOrEqual(0)

            const pinnedImpact = responseData(await browserApiRaw(
              schoolPage,
              schoolToken,
              `/system/iam/role-templates/${encodeURIComponent(published.id)}/impact`
            ))
            const pinnedCustom = (pinnedImpact.roles || []).find((item) => item.roleCode === 'E2E_CUSTOM_MENU')
            expect(pinnedCustom).toBeTruthy()
            expect(pinnedCustom.automaticUpgrade).toBe(false)
            expect(pinnedCustom.memberCount).toBeGreaterThan(0)
            expect(pinnedImpact.affectedUserCount).toBeGreaterThan(0)
            const afterPublishCustom = responseData(await browserApiRaw(
              schoolPage,
              schoolToken,
              `/system/roles/${encodeURIComponent(customRole.id)}`
            ))
            expect(afterPublishCustom.permissionCodes).toEqual(beforeCustom.permissionCodes)

            const explanation = responseData(await browserApiRaw(
              schoolPage,
              schoolToken,
              `/system/iam/access-explain/${encodeURIComponent(FIXTURE.customRoleGoldenSession.userId)}`
                + '?moduleKey=internship&permissionCode=internship.recruitment.view'
            ))
            expect(explanation.subject?.userId).toBe(String(FIXTURE.customRoleGoldenSession.userId))
            expect(['ALLOW', 'DENY']).toContain(explanation.finalDecision)
            expect((explanation.roles || []).length).toBeGreaterThan(0)

            responseData(await browserApiRaw(
              schoolPage,
              schoolToken,
              '/internship/recruitment-campaigns?page=1&pageSize=1'
            ))
            const savePath = `/system/roles/${encodeURIComponent(customRole.id)}/permissions`
            const saveBody = {
              permissionCodes: [],
              scopeCode: beforeCustom.scopeCode || 'ASSIGNED',
              scopeTarget: {},
              expectedVersion: Number(beforeCustom.version),
              reason: 'IAM GJ-04 browser custom role menu convergence proof',
              requestId: crypto.randomUUID()
            }
            const staleCustom = await browserApiRaw(schoolPage, schoolToken, savePath, {
              method: 'PUT',
              body: { ...saveBody, expectedVersion: Number(beforeCustom.version) - 1, requestId: crypto.randomUUID() }
            })
            expect(staleCustom.status).toBe(409)
            const savedCustom = responseData(await browserApiRaw(schoolPage, schoolToken, savePath, {
              method: 'PUT',
              body: saveBody
            }))
            expect(savedCustom.removedPermissionCodes).toContain(FIXTURE.customPermission)
            expect(savedCustom.readOnlyPreservedPermissionCodes).toContain(FIXTURE.legacyPreservedPermission)
            expect(savedCustom.affectedMemberCount).toBeGreaterThan(0)
            expect(savedCustom.cacheInvalidated).toBe(true)

            const customContext = await browser.newContext({
              extraHTTPHeaders: { 'X-Forwarded-For': '10.254.12.241' }
            })
            try {
              const customPage = await customContext.newPage()
              const customToken = await passwordRelogAsRole(customPage, 'E2E_CUSTOM_MENU')
              const revokedApi = await browserApiRaw(
                customPage,
                customToken,
                '/internship/recruitment-campaigns?page=1&pageSize=1'
              )
              expect([401, 403], JSON.stringify(revokedApi.json)).toContain(revokedApi.status)
              await customPage.goto(new URL(FIXTURE.customPermissionPath, config.staffBaseUrl).toString())
              await expect.poll(async () => {
                const finalUrl = new URL(customPage.url())
                const body = await customPage.locator('body').innerText().catch(() => '')
                return finalUrl.pathname !== FIXTURE.customPermissionPath
                  || /403|无权限|禁止访问|没有权限/.test(body)
              }, { timeout: 30_000 }).toBe(true)
            } finally {
              await customContext.close()
            }

            golden.roleTemplatePinnedCustomUnaffected = true
            golden.customRoleSaveAndRelog = true
            golden.customRoleStaleVersionDenied = true
            golden.legacyPermissionReadOnlyPreserved = true
            golden.accessExplainFinalDecision = true
          } finally {
            await schoolContext.close()
          }

          await page.goto(new URL('/admin/platform/product-iam', config.staffBaseUrl).toString())
          await expect(page.getByText('产品身份与权限', { exact: true }).first()).toBeVisible()
          await expect(page.getByText('岗位实习模块边界正常', { exact: true })).toBeVisible()
          golden.productIamRootBrowser = true
          golden.productIamTemplateVisible = true
          golden.roleTemplatePublishMfa = true
          golden.roleTemplateMenuImpact = true
          golden.staleTemplateVersionDenied = true
        }
      }
      expect([401, 403, 404], JSON.stringify(crossPlane.json)).toContain(crossPlane.status)
      expect(crossPlane.json?.code).not.toBe(0)

      const crossTenant = await browserApiRaw(
        page,
        token,
        `/system/users/${encodeURIComponent(FIXTURE.crossTenantUserId)}`
      )
      expect([403, 404], JSON.stringify(crossTenant.json)).toContain(crossTenant.status)
      expect(crossTenant.json?.code).not.toBe(0)

      await assertDirectUrlDenied(page, session)
      evidence.push({
        roleCode: session.roleCode,
        plane: session.plane,
        realBrowserRefresh: true,
        menuVisible: true,
        menuHidden: true,
        realClick: true,
        directUrlDenied: true,
        positiveApi,
        positiveApiAllowed: true,
        crossPlaneDenied: true,
        crossTenantDenied: true,
        dataScope,
        expectedPermissionCount: session.expectedPermissionCount,
        ...golden
      })
    } finally {
      await context.close()
    }
  }

  writeEvidence(evidence)
})
