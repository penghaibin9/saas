import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const FIXTURE = JSON.parse(fs.readFileSync(
  path.resolve(process.cwd(), 'runtime-fixtures/control-plane-school-iam.json'), 'utf8'
))
const TARGET_PERMISSION = 'internship.recruitment.view'

async function browserApiRaw(page, token, method, requestPath, body) {
  return page.evaluate(async ({ apiBaseUrl, tokenValue, requestMethod, requestPath: p, requestBody }) => {
    const response = await fetch(`${apiBaseUrl}${p}`, {
      method: requestMethod,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${tokenValue}`,
        ...(requestBody === undefined ? {} : { 'Content-Type': 'application/json' })
      },
      body: requestBody === undefined ? undefined : JSON.stringify(requestBody)
    })
    const text = await response.text()
    let json
    try { json = JSON.parse(text) } catch { json = { message: text.slice(0, 1000) } }
    return { status: response.status, json }
  }, {
    apiBaseUrl: config.apiBaseUrl,
    tokenValue: token,
    requestMethod: method,
    requestPath,
    requestBody: body
  })
}

async function browserApi(page, token, method, requestPath, body) {
  const result = await browserApiRaw(page, token, method, requestPath, body)
  expect(result.status, JSON.stringify(result.json)).toBe(200)
  expect(result.json?.code, JSON.stringify(result.json)).toBe(0)
  return result.json?.data
}

function explainPath(userId, permissionCode = TARGET_PERMISSION) {
  return `/system/iam/access-explain/${encodeURIComponent(userId)}?moduleKey=internship&permissionCode=${encodeURIComponent(permissionCode)}`
}

function writeEvidence(payload) {
  const target = path.resolve(process.cwd(), 'test-results/system-effective-access-evidence.json')
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.writeFileSync(target, JSON.stringify(payload, null, 2))
}

test('School IAM EffectiveAccess keeps module, permission, tenant and enterprise planes separate', async ({ browser }) => {
  const demoContext = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '10.254.0.61' } })
  const deniedContext = await browser.newContext({ extraHTTPHeaders: { 'X-Forwarded-For': '10.254.0.62' } })
  const demoPage = await demoContext.newPage()
  const deniedPage = await deniedContext.newPage()
  try {
    const demoLogin = new StaffLoginPage(demoPage, config.staffBaseUrl)
    const deniedLogin = new StaffLoginPage(deniedPage, config.staffBaseUrl)
    await demoLogin.login(config.demoAdmin)
    await deniedLogin.login({
      tenant: FIXTURE.iamDeniedTenantCode,
      username: FIXTURE.iamDeniedAdminLogin,
      password: '123456'
    })
    const demoToken = await demoLogin.token()
    const deniedToken = await deniedLogin.token()

    await demoPage.goto(`${config.staffBaseUrl}/admin/system/access-governance`)
    await expect(demoPage.locator('body')).toContainText('访问治理')

    const catalog = await browserApi(demoPage, demoToken, 'GET', '/system/iam/permission-catalog')
    const assignableCodes = (catalog.assignablePermissions || []).map((item) => item.permissionCode)
    expect(assignableCodes).toContain(TARGET_PERMISSION)
    expect(assignableCodes.some((code) => code.startsWith('platform.'))).toBe(false)
    expect(assignableCodes.some((code) => code.startsWith('enterprise.'))).toBe(false)
    expect(catalog.enterprisePermissionsVisibleButSchoolAssignable).toBe(false)

    const demoAdmin = await browserApi(demoPage, demoToken, 'GET', explainPath(FIXTURE.demoAdminUserId))
    expect(demoAdmin.iamAllowed).toBe(true)
    expect(demoAdmin.allowed).toBe(false)
    expect(demoAdmin.reasonCode).toBe('RESOURCE_CONTEXT_REQUIRED')
    expect(demoAdmin.finalDecision).toBe('DENY')

    const ordinaryTeacher = await browserApi(demoPage, demoToken, 'GET', explainPath(FIXTURE.targetUserId))
    expect(ordinaryTeacher.iamAllowed).toBe(false)
    expect(ordinaryTeacher.reasonCode).toBe('PERMISSION_DENIED')

    const enterpriseDenied = await browserApi(
      demoPage,
      demoToken,
      'GET',
      explainPath(FIXTURE.targetUserId, 'enterprise.internship.company.view')
    )
    expect(enterpriseDenied.iamAllowed).toBe(false)
    expect(enterpriseDenied.reasonCode).toBe('PERMISSION_NOT_SCHOOL_ASSIGNABLE')

    const platformDenied = await browserApi(
      demoPage,
      demoToken,
      'GET',
      explainPath(FIXTURE.targetUserId, 'platform.tenant.view')
    )
    expect(platformDenied.iamAllowed).toBe(false)
    expect(platformDenied.reasonCode).toBe('PERMISSION_NOT_SCHOOL_ASSIGNABLE')

    const crossTenant = await browserApiRaw(
      demoPage,
      demoToken,
      'GET',
      explainPath(FIXTURE.sandboxAdminUserId)
    )
    expect([403, 404], JSON.stringify(crossTenant.json)).toContain(crossTenant.status)
    expect(crossTenant.json?.code).not.toBe(0)

    const unentitledWildcardAdmin = await browserApi(
      deniedPage,
      deniedToken,
      'GET',
      explainPath(FIXTURE.iamDeniedAdminUserId)
    )
    expect(unentitledWildcardAdmin.iamAllowed).toBe(false)
    expect(unentitledWildcardAdmin.reasonCode).toBe('MODULE_NOT_ENTITLED')

    const templates = await browserApi(demoPage, demoToken, 'GET', '/system/iam/role-templates')
    const schoolAdminTemplate = (templates.items || []).find((item) => item.templateCode === 'SCHOOL_ADMIN')
    expect(schoolAdminTemplate).toBeTruthy()
    expect(schoolAdminTemplate.permissions.length).toBe(Number(FIXTURE.tenantPermissionUniverseCount))
    expect(schoolAdminTemplate.permissions.some((code) => code.startsWith('platform.'))).toBe(false)
    expect(schoolAdminTemplate.permissions.some((code) => code.startsWith('enterprise.'))).toBe(false)

    writeEvidence({
      headSha: process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || '',
      realDemoSchoolLogin: true,
      realUnentitledSchoolLogin: true,
      accessGovernanceSurface: true,
      targetPermission: TARGET_PERMISSION,
      demoSchoolAdminIamReason: demoAdmin.reasonCode,
      ordinaryTeacherReason: ordinaryTeacher.reasonCode,
      enterprisePermissionReason: enterpriseDenied.reasonCode,
      platformPermissionReason: platformDenied.reasonCode,
      crossTenantHttpStatus: crossTenant.status,
      unentitledSchoolAdminReason: unentitledWildcardAdmin.reasonCode,
      schoolAdminExplicitPermissionCount: schoolAdminTemplate.permissions.length,
      platformPermissionInSchoolTemplate: false,
      enterprisePermissionInSchoolTemplate: false
    })
  } finally {
    await demoContext.close()
    await deniedContext.close()
  }
})
