/** 岗位实习合规工作台统一 API。 */
import { getToken, request } from '@/services/http/client'
import { API_BASE_URL, API_PREFIX } from '@/services/http/config'

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

async function parseEnvelope(response, fallback) {
  let payload = null
  try { payload = await response.json() } catch { payload = null }
  if (!response.ok || !payload || payload.code !== 0) {
    throw new Error(payload?.message || fallback)
  }
  return payload.data
}

async function downloadZip(path, fallbackName) {
  const token = getToken()
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  })
  if (!response.ok) {
    let message = '证据包下载失败或你已无权访问'
    try { message = (await response.json())?.message || message } catch { /* binary/empty */ }
    throw new Error(message)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fallbackName || '岗位实习证据包.zip'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

async function uploadEvidence(file, bizType) {
  if (!file) throw new Error('请选择需要上传的文件')
  const token = getToken()
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(
    `${API_BASE_URL}${API_PREFIX}/files/upload?bizType=${encodeURIComponent(bizType)}`,
    { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form }
  )
  return parseEnvelope(response, '材料上传失败，请重试')
}

export const complianceApi = {
  workbench(batchId) { return call(() => request(`${B}/workbench/${batchId}`)) },
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
  revokeConsent(id, body) {
    return call(() => request(`${B}/consents/${id}/revoke`, { method: 'POST', body }))
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
  reviewEmergencyPlan(id, action, body = {}) {
    return call(() => request(`${B}/emergency-plans/${id}/${action}`, { method: 'POST', body }))
  },
  evaluate(internshipId, operation = 'ONBOARD') {
    return call(() => request(`${B}/evaluate/${internshipId}`, { params: { operation } }))
  },
  batchStats(batchId) { return call(() => request(`${B}/batches/${batchId}/stats`)) },
  grantExemption(body) { return call(() => request(`${B}/exemptions`, { method: 'POST', body })) },
  reviewExemption(id, body) {
    return call(() => request(`${B}/exemptions/${id}/review`, { method: 'POST', body }))
  },
  reviewEnterpriseEval(id, body) {
    return call(() => request(`${B}/workbench/enterprise-evals/${id}/review`, { method: 'POST', body }))
  },
  saveStudentEvalAdvisor(id, body) {
    return call(() => request(`${B}/workbench/student-evals/${id}/advisor-comment`, { method: 'POST', body }))
  },
  reviewStudentEval(id, body) {
    return call(() => request(`${B}/workbench/student-evals/${id}/review`, { method: 'POST', body }))
  },
  verifyInsurance(id, body) {
    return call(() => request(`${B}/workbench/insurances/${id}/verify`, { method: 'POST', body }))
  },
  uploadEvidence(file, bizType) { return call(() => uploadEvidence(file, bizType)) },
  generateEvidencePackage(packageType, targetId) {
    return call(() => request(`${B}/evidence-packages/${packageType}/${targetId}`, { method: 'POST' }))
  },
  downloadEvidencePackage(packageId, filename) {
    return downloadZip(`${B}/evidence-packages/${packageId}/download`, filename)
  },
  auditHealth() { return call(() => request(`${B}/audit-outbox/health`)) }
}

export default complianceApi
