/**
 * 毕业设计中心 · 选题变更申请 API（生产级：仅走真实后端，不回退 mock）。
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
async function callList(path, params = {}) {
  try {
    const d = await request(path, { params })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) { return toErr(e) }
}

const BASE = '/graduation/gd-topic-change-requests'

export const gdTopicChangeApi = {
  getChangeRequests(params = {}) {
    return callList(BASE, params)
  },
  getChangeRequestDetail(id) {
    return call(() => request(`${BASE}/${id}`))
  },
  createChangeRequest(body) {
    return call(() => request(BASE, { method: 'POST', body }))
  },
  reviewChangeRequest(id, { action, comment }) {
    return call(() => request(`${BASE}/${id}/review`, { method: 'POST', body: { action, comment } }))
  }
}

export default gdTopicChangeApi
