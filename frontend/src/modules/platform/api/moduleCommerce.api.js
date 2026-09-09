import { request } from '@/services/http/client'

const financeBase = (tenantId) => `/platform/commercial/tenants/${encodeURIComponent(tenantId)}`

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
  getExitReview: (tenantId, jobId, params) => request(`${financeBase(tenantId)}/module-offboarding/${encodeURIComponent(jobId)}/exit-review`, { params }),
  getOffboarding: (jobId) => request(`/platform/commercial/module-offboarding/${jobId}`),
  cancelOffboarding: (jobId, body) => request(`/platform/commercial/module-offboarding/${jobId}/cancel`, { method: 'POST', body }),
  bindExport: (jobId, body) => request(`/platform/commercial/module-offboarding/${jobId}/export`, { method: 'POST', body }),
  acceptExport: (jobId, body) => request(`/platform/commercial/module-offboarding/${jobId}/export-acceptance`, { method: 'POST', body }),

  listFinanceOrders: (tenantId, params = {}) => request(`${financeBase(tenantId)}/finance-orders`, { params }),
  listRefunds: (tenantId, params = {}) => request(`${financeBase(tenantId)}/refunds`, { params }),
  requestRefund: (tenantId, body, key) => request(`${financeBase(tenantId)}/refunds`, {
    method: 'POST', body, headers: { 'Idempotency-Key': key }, timeoutMs: 15000
  }),
  approveRefund: (tenantId, caseId, body) => request(`${financeBase(tenantId)}/refunds/${encodeURIComponent(caseId)}/approve`, { method: 'POST', body }),
  rejectRefund: (tenantId, caseId, body) => request(`${financeBase(tenantId)}/refunds/${encodeURIComponent(caseId)}/reject`, { method: 'POST', body }),
  settleRefund: (tenantId, caseId, body) => request(`${financeBase(tenantId)}/refunds/${encodeURIComponent(caseId)}/settle`, { method: 'POST', body }),
  listInvoices: (tenantId, params = {}) => request(`${financeBase(tenantId)}/invoices`, { params }),
  requestInvoice: (tenantId, body, key) => request(`${financeBase(tenantId)}/invoices`, {
    method: 'POST', body, headers: { 'Idempotency-Key': key }, timeoutMs: 15000
  }),
  issueInvoice: (tenantId, invoiceCaseId, body) => request(`${financeBase(tenantId)}/invoices/${encodeURIComponent(invoiceCaseId)}/issue`, { method: 'POST', body }),
  voidInvoice: (tenantId, invoiceCaseId, body) => request(`${financeBase(tenantId)}/invoices/${encodeURIComponent(invoiceCaseId)}/void`, { method: 'POST', body }),

  getOperationsOverview: (tenantId) => request(`${financeBase(tenantId)}/operations`),
  listAfterSales: (tenantId, params = {}) => request(`${financeBase(tenantId)}/after-sales`, { params }),
  createAfterSalesTicket: (tenantId, refundCaseId, body) => request(`${financeBase(tenantId)}/refunds/${encodeURIComponent(refundCaseId)}/after-sales-ticket`, { method: 'POST', body }),
  listServiceCosts: (tenantId, params = {}) => request(`${financeBase(tenantId)}/service-costs`, { params }),
  recordServiceCost: (tenantId, body, key) => request(`${financeBase(tenantId)}/service-costs`, {
    method: 'POST', body, headers: { 'Idempotency-Key': key }, timeoutMs: 15000
  }),
  getSlaPolicy: (tenantId) => request(`${financeBase(tenantId)}/sla-policy`),
  updateSlaPolicy: (tenantId, body) => request(`${financeBase(tenantId)}/sla-policy`, { method: 'PUT', body }),
  resetSlaPolicy: (tenantId, body) => request(`${financeBase(tenantId)}/sla-policy/reset`, { method: 'POST', body }),

  listRenewalCandidates: (tenantId, params = {}) => request(`${financeBase(tenantId)}/renewal-candidates`, { params }),
  createRenewalFollowup: (tenantId, sourceId, body) => request(`${financeBase(tenantId)}/sources/${encodeURIComponent(sourceId)}/renewal-followup`, { method: 'POST', body })
}
