import { request } from '@/services/http/client'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}
async function call(fn) { try { return ok(await fn()) } catch (e) { return toErr(e) } }
async function callList(path, params = {}) {
  try {
    const d = await request(path, { params })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) { return toErr(e) }
}

export const planApi = {
  getBatchPlan(batchId) { return call(() => request(`/internship/plans/batch/${batchId}`)) },
  saveBatchPlan(batchId, body) { return call(() => request(`/internship/plans/batch/${batchId}`, { method: 'PUT', body })) },
  publishBatchPlan(batchId) { return call(() => request(`/internship/plans/batch/${batchId}/publish`, { method: 'POST', body: {} })) },
  getPlanAcks(params = {}) { return callList('/internship/plan-acks', params) },
  getTaskProgress(params = {}) { return callList('/internship/plan-task-progress', params) },
  reviewTaskProgress(id, body) {
    return call(() => request(`/internship/plan-task-progress/${id}/review`, { method: 'POST', body }))
  },
  getTaskSummary(batchId) { return call(() => request(`/internship/plans/batch/${batchId}/task-summary`)) }
}

export const insuranceApi = {
  getInsurances(params = {}) { return callList('/internship/insurances', params) },
  verify(id, { action, comment }) {
    return call(() => request(`/internship/insurances/${id}/verify`, { method: 'POST', body: { action, comment } }))
  }
}
