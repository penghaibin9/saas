import { request } from '@/services/http/client'

export const platformP1ClosureApi = Object.freeze({
  getTenantProfile: (tenantId) => request(`/platform/tenants/${encodeURIComponent(tenantId)}/profile`),
  updateTenantProfile: (tenantId, body) => request(`/platform/tenants/${encodeURIComponent(tenantId)}/profile`, {
    method: 'PUT',
    body
  })
})