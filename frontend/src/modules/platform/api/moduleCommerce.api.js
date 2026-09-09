import { request } from '@/services/http/client'

export const moduleCommerceApi = {
  listSaleSkus: (params) => request('/platform/commercial/skus', { params }),
  publishSku: (body) => request('/platform/commercial/skus', { method: 'POST', body }),
  listSalesTenants: (params) => request('/platform/commercial/sales-tenants', { params }),
  getSalesContext: (tenantId) => request(`/platform/commercial/sales-tenants/${encodeURIComponent(tenantId)}/context`),
  previewSalesOrder: (body) => request('/platform/commercial/sales-order-preview', { method: 'POST', body }),
  createSalesOrder: (body, key) => request('/platform/commercial/sales-orders', { method: 'POST', body, headers: { 'Idempotency-Key': key }, timeoutMs: 15000 }),
  listSalesOrders: (params) => request('/platform/commercial/sales-orders', { params }),
  getSalesOrder: (tenantId, orderId) => request(`/platform/commercial/sales-orders/${encodeURIComponent(orderId)}`, { params: { tenantId } }),
  exportSalesOrders: (body) => request('/platform/commercial/sales-orders-export', { method: 'POST', body, timeoutMs: 30000 }),
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
