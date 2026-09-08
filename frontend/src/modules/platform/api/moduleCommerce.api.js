import { request } from '@/services/http/client'

export const moduleCommerceApi = {
  getPortfolio: (tenantId) => request(`/platform/commercial/tenants/${tenantId}/modules`),
  acceptDelivery: (tenantId, moduleKey, body) => request(`/platform/commercial/tenants/${tenantId}/modules/${encodeURIComponent(moduleKey)}/delivery-acceptance`, { method: 'POST', body }),
  scheduleCancellation: (tenantId, sourceId, body) => request(`/platform/commercial/tenants/${tenantId}/sources/${sourceId}/cancel-at-period-end`, { method: 'POST', body }),
  resumeRenewal: (tenantId, sourceId, body) => request(`/platform/commercial/tenants/${tenantId}/sources/${sourceId}/resume-renewal`, { method: 'POST', body }),
  previewOffboarding: (tenantId, moduleKey) => request(`/platform/commercial/tenants/${tenantId}/modules/${encodeURIComponent(moduleKey)}/offboarding-preview`),
  requestOffboarding: (tenantId, moduleKey, body) => request(`/platform/commercial/tenants/${tenantId}/modules/${encodeURIComponent(moduleKey)}/offboarding`, { method: 'POST', body }),
  getOffboarding: (jobId) => request(`/platform/commercial/module-offboarding/${jobId}`),
  cancelOffboarding: (jobId, body) => request(`/platform/commercial/module-offboarding/${jobId}/cancel`, { method: 'POST', body }),
  bindExport: (jobId, body) => request(`/platform/commercial/module-offboarding/${jobId}/export`, { method: 'POST', body }),
  acceptExport: (jobId, body) => request(`/platform/commercial/module-offboarding/${jobId}/export-acceptance`, { method: 'POST', body })
}
