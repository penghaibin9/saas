/**
 * 岗位实习中心 · 打卡台账 / 打卡异常 / 补卡审批 API（P1-Stage1，生产级只走真实后端）。
 * 端点 /internship/checkins、/internship/exceptions、/internship/makeups。
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

export const attendanceApi = {
  // 打卡台账
  getCheckins(params = {}) { return callList(`${B}/checkins`, params) },
  exportCheckins(params = {}) { return call(() => request(`${B}/checkins/export`, { method: 'POST', params })) },
  // 打卡异常
  getExceptions(params = {}) { return callList(`${B}/exceptions`, params) },
  getExceptionDetail(id) { return call(() => request(`${B}/exceptions/${id}`)) },
  handleException(id, { action, comment }) {
    return call(() => request(`${B}/exceptions/${id}/handle`, { method: 'POST', body: { action, comment } }))
  },
  exportExceptions(params = {}) { return call(() => request(`${B}/exceptions/export`, { method: 'POST', params })) },
  // 补卡审批
  getMakeups(params = {}) { return callList(`${B}/makeups`, params) },
  getMakeupDetail(id) { return call(() => request(`${B}/makeups/${id}`)) },
  approveMakeup(id, { comment } = {}) {
    return call(() => request(`${B}/makeups/${id}/approve`, { method: 'POST', body: { comment: comment || '' } }))
  },
  rejectMakeup(id, { comment }) {
    return call(() => request(`${B}/makeups/${id}/reject`, { method: 'POST', body: { comment } }))
  },
  exportMakeups(params = {}) { return call(() => request(`${B}/makeups/export`, { method: 'POST', params })) }
}

export default attendanceApi
