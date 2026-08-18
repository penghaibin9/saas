import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const SELF_REVIEW_TEXT = '我已确认本次安全变更的影响并愿意承担责任'
const TARGET_PERMISSION = 'internship.recruitment.view'
const FIXTURE = JSON.parse(fs.readFileSync(
  path.resolve(process.cwd(), 'runtime-fixtures/control-plane-school-iam.json'), 'utf8'
))

async function browserApi(page, token, method, requestPath, body, expectedStatus = 200) {
  const result = await page.evaluate(async ({ apiBaseUrl, tokenValue, requestMethod, requestPath: p, requestBody }) => {
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
  expect(result.status, JSON.stringify(result.json)).toBe(expectedStatus)
  if (expectedStatus >= 200 && expectedStatus < 300) {
    expect(result.json?.code, JSON.stringify(result.json)).toBe(0)
  }
  return result.json?.data
}

function explainPath(userId, permissionCode = TARGET_PERMISSION) {
  return `/system/iam/access-explain/${encodeURIComponent(userId)}?moduleKey=internship&permissionCode=${encodeURIComponent(permissionCode)}`
}

function writeEvidence(payload) {
  const target = path.resolve(process.cwd(), 'test-results/system-role-security-change-evidence.json')
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.writeFileSync(target, JSON.stringify(payload, null, 2))
}

test.describe.serial('School IAM · Custom Role → SecurityChange → RolePermission', () => {
  test('draft/review do not change runtime; activation materializes; rollback removes it', async ({ page }, testInfo) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login({
      tenant: FIXTURE.iamTenantCode,
      username: FIXTURE.iamAdminLogin,
      password: '123456'
    })
    const token = await login.token()
    expect(token).toBeTruthy()

    await page.goto(`${config.staffBaseUrl}/admin/system/security-changes`)
    await expect(page.locator('body')).toContainText('安全变更')

    const summary = await browserApi(page, token, 'GET', '/system/iam/summary')
    expect(summary.enterpriseRoleAdministration).toBe('DENIED_FROM_SCHOOL_IAM')

    const templateData = await browserApi(page, token, 'GET', '/system/iam/role-templates')
    const schoolAdminTemplate = (templateData.items || []).find((item) => item.templateCode === 'SCHOOL_ADMIN')
    expect(schoolAdminTemplate, JSON.stringify(templateData)).toBeTruthy()
    expect(schoolAdminTemplate.permissions).toContain(TARGET_PERMISSION)
    expect(schoolAdminTemplate.permissions.some((code) => code.startsWith('platform.'))).toBeFalsy()
    expect(schoolAdminTemplate.permissions.some((code) => code.startsWith('enterprise.'))).toBeFalsy()

    const users = await browserApi(page, token, 'GET', `/system/users?keyword=${encodeURIComponent(FIXTURE.iamTargetLogin)}&page=1&page_size=20`)
    const target = (users.list || []).find((item) => item.loginName === FIXTURE.iamTargetLogin)
    expect(target, JSON.stringify(users)).toBeTruthy()
    expect(String(target.id)).toBe(String(FIXTURE.iamTargetUserId))

    const runId = String(process.env.GITHUB_RUN_ID || Date.now()).replace(/\D/g, '').slice(-10)
    const suffix = `${runId}_${testInfo.retry}`
    const roleCode = `B8_IAM_E2E_${suffix}`
    const cloned = await browserApi(page, token, 'POST', '/system/custom-roles/clone', {
      templateCode: 'SCHOOL_ADMIN',
      roleCode,
      permissionCodes: []
    })
    expect(cloned.roleCode).toBe(roleCode)
    expect(cloned.sourceTemplate).toBe('SCHOOL_ADMIN')
    expect(cloned.roleType).toBe('CUSTOM')
    expect(cloned.permissionCodes).toEqual([])

    await browserApi(page, token, 'PUT', `/system/users/${target.id}/roles`, {
      roleCodes: ['ACADEMIC_TEACHER', roleCode]
    })
    const assignedDetail = await browserApi(page, token, 'GET', `/system/users/${target.id}`)
    expect((assignedDetail.roles || []).map((item) => item.code)).toContain(roleCode)

    const before = await browserApi(page, token, 'GET', explainPath(target.id))
    expect(before.iamAllowed).toBe(false)
    expect(before.reasonCode).toBe('PERMISSION_DENIED')

    const revBefore = await browserApi(page, token, 'GET', '/system/security-revision')
    const initialRevision = Number(revBefore.currentRevision || 0)

    let change = await browserApi(page, token, 'POST', '/system/security-changes', {
      title: `B8 学校 IAM 权限变更 ${suffix}`,
      reason: '验证学校 IAM 安全变更仅在激活后进入运行时权限',
      riskLevel: 'HIGH'
    })
    const changeSetId = change.changeSetId
    expect(change.status).toBe('DRAFT')

    await browserApi(page, token, 'POST', `/system/security-changes/${changeSetId}/items`, {
      targetType: 'CUSTOM_ROLE',
      targetId: roleCode,
      after: { permissionCodes: [TARGET_PERMISSION] }
    })

    change = await browserApi(page, token, 'POST', `/system/security-changes/${changeSetId}/transition`, {
      targetStatus: 'PENDING_REVIEW',
      reason: '提交真实浏览器复核',
      expectedVersion: change.version
    })
    expect(change.status).toBe('PENDING_REVIEW')
    expect((await browserApi(page, token, 'GET', explainPath(target.id))).reasonCode).toBe('PERMISSION_DENIED')
    expect(Number((await browserApi(page, token, 'GET', '/system/security-revision')).currentRevision || 0)).toBe(initialRevision)

    change = await browserApi(page, token, 'POST', `/system/security-changes/${changeSetId}/transition`, {
      targetStatus: 'APPROVED',
      reason: '管理员已复核影响范围并确认继续',
      expectedVersion: change.version,
      selfReviewAck: SELF_REVIEW_TEXT
    })
    expect(change.status).toBe('APPROVED')
    expect((await browserApi(page, token, 'GET', explainPath(target.id))).reasonCode).toBe('PERMISSION_DENIED')
    expect(Number((await browserApi(page, token, 'GET', '/system/security-revision')).currentRevision || 0)).toBe(initialRevision)

    change = await browserApi(page, token, 'POST', `/system/security-changes/${changeSetId}/transition`, {
      targetStatus: 'ACTIVATED',
      reason: '生产级 E2E 验证激活事务',
      expectedVersion: change.version
    })
    expect(change.status).toBe('ACTIVATED')
    expect(change.runtimeMaterialized).toBe(true)
    expect(change.cacheInvalidated).toBe(true)

    const after = await browserApi(page, token, 'GET', explainPath(target.id))
    expect(after.iamAllowed).toBe(true)
    expect(after.allowed).toBe(false)
    expect(after.finalDecision).toBe('DENY')
    expect(after.reasonCode).toBe('RESOURCE_CONTEXT_REQUIRED')
    const revActivated = Number((await browserApi(page, token, 'GET', '/system/security-revision')).currentRevision || 0)
    expect(revActivated).toBe(initialRevision + 1)

    const impact = await browserApi(page, token, 'GET', `/system/iam/role-templates/${schoolAdminTemplate.id}/impact`)
    const affected = (impact.roles || []).find((item) => item.roleCode === roleCode)
    expect(affected, JSON.stringify(impact)).toBeTruthy()
    expect(affected.automaticUpgrade).toBe(false)
    expect(affected.runtimeVsRecorded.addedInRuntime).toEqual([])
    expect(affected.runtimeVsRecorded.removedFromRuntime).toEqual([])

    change = await browserApi(page, token, 'POST', `/system/security-changes/${changeSetId}/transition`, {
      targetStatus: 'ROLLED_BACK',
      reason: 'E2E 完成后验证 before 快照回滚',
      expectedVersion: change.version
    })
    expect(change.status).toBe('ROLLED_BACK')
    expect(change.runtimeMaterialized).toBe(true)
    const rolledBack = await browserApi(page, token, 'GET', explainPath(target.id))
    expect(rolledBack.iamAllowed).toBe(false)
    expect(rolledBack.reasonCode).toBe('PERMISSION_DENIED')
    const revRolledBack = Number((await browserApi(page, token, 'GET', '/system/security-revision')).currentRevision || 0)
    expect(revRolledBack).toBe(initialRevision + 2)

    await page.reload()
    await expect(page.locator('body')).toContainText(`B8 学校 IAM 权限变更 ${suffix}`)

    writeEvidence({
      headSha: process.env.E2E_EXPECTED_SHA || process.env.GITHUB_SHA || '',
      realBrowserLogin: true,
      schoolIamSurface: true,
      canonicalCustomRoleClone: true,
      canonicalRoleAssignment: true,
      sourceTemplate: cloned.sourceTemplate,
      sourceTemplateVersion: cloned.sourceTemplateVersion,
      targetPermission: TARGET_PERMISSION,
      beforeReasonCode: before.reasonCode,
      reviewRuntimeUnchanged: true,
      activationReasonCode: after.reasonCode,
      activationRuntimeMaterialized: true,
      activationRevisionDelta: 1,
      rollbackReasonCode: rolledBack.reasonCode,
      rollbackRevisionDelta: 2,
      pinnedAutomaticUpgrade: affected.automaticUpgrade,
      platformPermissionInSchoolTemplate: false,
      enterprisePermissionInSchoolTemplate: false
    })
  })
})
