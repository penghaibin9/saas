/**
 * 岗位实习中心 · 实习请假审批 / 风险处置闭环 API（P1-Stage3，生产级只走真实后端）。
 * 端点 /internship/leaves、/internship/risks。owner + 数据范围由后端强校验。
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

const B = '/internship'

export const leaveApi = {
  getLeaves(params = {}) { return callList(`${B}/leaves`, params) },
  getLeaveDetail(id) { return call(() => request(`${B}/leaves/${id}`)) },
  review(id, { action, comment }) {
    return call(() => request(`${B}/leaves/${id}/review`, { method: 'POST', body: { action, comment } }))
  },
  exportLeaves(params = {}) { return call(() => request(`${B}/leaves/export`, { method: 'POST', params })) }
}

export const riskApi = {
  getRisks(params = {}) { return callList(`${B}/risks`, params) },
  getRiskDetail(id) { return call(() => request(`${B}/risks/${id}`)) },
  handle(id, { ownerName, deadline, comment }) {
    return call(() => request(`${B}/risks/${id}/handle`, { method: 'POST', body: { ownerName, deadline, comment } }))
  },
  follow(id, { note }) {
    return call(() => request(`${B}/risks/${id}/follow`, { method: 'POST', body: { note } }))
  },
  remind(id, { channel = '站内消息' } = {}) {
    return call(() => request(`${B}/risks/${id}/remind`, { method: 'POST', body: { channel } }))
  },
  escalate(id, { level, note }) {
    return call(() => request(`${B}/risks/${id}/escalate`, { method: 'POST', body: { level, note } }))
  },
  close(id, { result, comment }) {
    return call(() => request(`${B}/risks/${id}/close`, { method: 'POST', body: { result, comment } }))
  },
  exportRisks(params = {}) { return call(() => request(`${B}/risks/export`, { method: 'POST', params })) }
}
