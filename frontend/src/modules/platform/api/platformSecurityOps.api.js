import { request } from '@/services/http/client'

/**
 * Platform P0 security/offboarding API bridge.
 *
 * Keep destructive MFA tokens request-scoped: callers pass the short-lived
 * step-up token only to approveTenantPurge. It is never installed as the
 * browser session token and never persisted in browser storage.
 */
export const platformSecurityOpsApi = {
  getMfaStatus: () => request('/auth/platform-mfa/status'),
  startMfaEnrollment: (password) => request('/auth/platform-mfa/enroll', {
    method: 'POST',
    body: { password: password || undefined }
  }),
  confirmMfaEnrollment: (code) => request('/auth/platform-mfa/confirm', {
    method: 'POST',
    body: { code }
  }),
  stepUpMfa: (code) => request('/auth/platform-mfa/step-up', {
    method: 'POST',
    body: { code }
  }),

  previewTenantOffboarding: (tenantId) => request(`/platform/tenants/${tenantId}/offboarding/preview`),
  getTenantOffboarding: (tenantId) => request(`/platform/tenants/${tenantId}/offboarding`),
  requestTenantOffboarding: (tenantId, body) => request(`/platform/tenants/${tenantId}/offboarding/request`, {
    method: 'POST',
    body
  }),
  confirmTenantFinalExport: (jobId, finalExportSha256) => request(`/platform/tenant-offboarding/${jobId}/final-export`, {
    method: 'POST',
    body: { finalExportSha256 }
  }),
  cancelTenantOffboarding: (jobId, reason) => request(`/platform/tenant-offboarding/${jobId}/cancel`, {
    method: 'POST',
    body: { reason }
  }),
  approveTenantPurge: (jobId, body, mfaAccessToken) => {
    if (!mfaAccessToken) throw new Error('永久销毁前必须完成 MFA 二次认证')
    return request(`/platform/tenant-offboarding/${jobId}/approve-purge`, {
      method: 'POST',
      auth: false,
      headers: { Authorization: `Bearer ${mfaAccessToken}` },
      body
    })
  }
}
