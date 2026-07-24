/**
 * 岗位实习 P2 合规证据链 API（合规模板 / 考察 / 知情 / 安全 / 备案 / 事故 / 评估 / 证据包）。
 */
import { request } from '@/services/http/client'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try { return ok(await fn()) } catch (e) { return toErr(e) }
}

const B = '/internship/compliance'

export const complianceApi = {
  listTemplates() { return call(() => request(`${B}/templates`)) },
  createTemplate(body) { return call(() => request(`${B}/templates`, { method: 'POST', body })) },
  activateTemplate(id, body = {}) {
    return call(() => request(`${B}/templates/${id}/activate`, { method: 'POST', body }))
  },
  listInspections(companyId) { return call(() => request(`${B}/inspections/${companyId}`)) },
  createInspection(body) { return call(() => request(`${B}/inspections`, { method: 'POST', body })) },
  submitInspection(id) {
    return call(() => request(`${B}/inspections/${id}/submit`, { method: 'POST', body: {} }))
  },
  reviewInspection(id, action, body = {}) {
    return call(() => request(`${B}/inspections/${id}/${action}`, { method: 'POST', body }))
  },
  createConsent(body) { return call(() => request(`${B}/consents`, { method: 'POST', body })) },
  confirmConsent(id, body) {
    return call(() => request(`${B}/consents/${id}/confirm`, { method: 'POST', body }))
  },
  listSafetyCourses(batchId) { return call(() => request(`${B}/safety/${batchId}`)) },
  createSafetyCourse(body) { return call(() => request(`${B}/safety`, { method: 'POST', body })) },
  ensureSafetyCompletion(body) {
    return call(() => request(`${B}/safety/completions`, { method: 'POST', body }))
  },
  reviewSafetyCompletion(id, body) {
    return call(() => request(`${B}/safety/completions/${id}/review`, { method: 'POST', body }))
  },
  createFiling(body) { return call(() => request(`${B}/filings`, { method: 'POST', body })) },
  reviewFiling(id, level, action, body = {}) {
    return call(() => request(`${B}/filings/${id}/${level}/${action}`, { method: 'POST', body }))
  },
  reportIncident(body) { return call(() => request(`${B}/incidents`, { method: 'POST', body })) },
  transitionIncident(id, body) {
    return call(() => request(`${B}/incidents/${id}/transition`, { method: 'POST', body }))
  },
  createEmergencyPlan(body) {
    return call(() => request(`${B}/emergency-plans`, { method: 'POST', body }))
  },
  reviewEmergencyPlan(id, action) {
    return call(() => request(`${B}/emergency-plans/${id}/${action}`, { method: 'POST', body: {} }))
  },
  evaluate(internshipId, operation = 'ONBOARD') {
    return call(() => request(`${B}/evaluate/${internshipId}`, { params: { operation } }))
  },
  batchStats(batchId) { return call(() => request(`${B}/batches/${batchId}/stats`)) },
  grantExemption(body) { return call(() => request(`${B}/exemptions`, { method: 'POST', body })) },
  generateEvidencePackage(packageType, targetId) {
    return call(() => request(`${B}/evidence-packages/${packageType}/${targetId}`, { method: 'POST' }))
  }
}

export default complianceApi
