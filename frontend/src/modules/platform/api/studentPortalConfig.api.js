/**
 * 学生 PC 门户 · 租户配置（真实后端）。
 * GET/PUT /api/v1/admin/tenants/{tenantId}/student-portal-config
 * 权限由后端强校验：平台运营可配置任意租户，学校管理员仅本校，老师/学生 403；保存写审计。
 */
import { request } from '@/services/http/client'

export const studentPortalConfigApi = {
  get: (tenantId) => request(`/admin/tenants/${tenantId}/student-portal-config`),
  save: (tenantId, body) =>
    request(`/admin/tenants/${tenantId}/student-portal-config`, { method: 'PUT', body })
}

export default studentPortalConfigApi
