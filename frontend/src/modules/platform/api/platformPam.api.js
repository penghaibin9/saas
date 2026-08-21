import { request } from '@/services/http/client'

function errorResult(error, fallback = '平台主管访问治理请求失败') {
  return {
    code: error?.code || 1,
    bizCode: error?.bizCode || error?.biz,
    data: null,
    message: error?.message || fallback,
    details: error?.details || null
  }
}

async function real(label, path, options = {}) {
  try {
    return { code: 0, data: await request(path, options), message: 'ok' }
  } catch (error) {
    return errorResult(error, `${label}失败`)
  }
}

export const platformPamApi = Object.freeze({
  listAssignments: () => real('读取平台职责', '/platform/access-assignments'),
  saveAssignment: (body) => real('保存平台职责', '/platform/access-assignments', { method: 'POST', body }),
  revokeAssignment: (id, expectedVersion, reason) => real(
    '撤销平台职责',
    `/platform/access-assignments/${encodeURIComponent(id)}/revoke`,
    { method: 'POST', body: { expectedVersion, reason } }
  ),

  listElevations: () => real('读取临时提升', '/platform/elevation-sessions'),
  createElevation: (body) => real('创建临时提升', '/platform/elevation-sessions', { method: 'POST', body }),
  revokeElevation: (id, expectedVersion, reason) => real(
    '撤销临时提升',
    `/platform/elevation-sessions/${encodeURIComponent(id)}/revoke`,
    { method: 'POST', body: { expectedVersion, reason } }
  ),

  listSupportSessions: (params = {}) => real('读取受控协助', '/platform/support-sessions', { params }),
  createSupportSession: (body) => real('创建受控协助', '/platform/support-sessions', { method: 'POST', body }),
  terminateSupportSession: (id, tenantId, expectedVersion, reason) => real(
    '终止受控协助',
    `/platform/support-sessions/${encodeURIComponent(id)}/terminate`,
    { method: 'POST', body: { tenantId, expectedVersion, reason } }
  ),
  getSupportTenantContext: (tenantId) => real(
    '读取受控学校上下文',
    `/platform/support/tenants/${encodeURIComponent(tenantId)}/context`
  ),
  getSupportTenantAudit: (tenantId, params = {}, mfaAccessToken = '') => real(
    '读取受控学校审计',
    `/platform/support/tenants/${encodeURIComponent(tenantId)}/audit`,
    mfaAccessToken
      ? { params, auth: false, headers: { Authorization: `Bearer ${mfaAccessToken}` } }
      : { params }
  ),

  listReviews: () => real('读取访问复核', '/platform/access-reviews'),
  createReview: (body) => real('创建访问复核', '/platform/access-reviews', { method: 'POST', body }),
  closeReview: (id, expectedVersion, reason, decisions) => real(
    '关闭访问复核',
    `/platform/access-reviews/${encodeURIComponent(id)}/close`,
    { method: 'POST', body: { expectedVersion, reason, decisions } }
  )
})
