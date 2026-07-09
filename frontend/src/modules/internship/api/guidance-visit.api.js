/**
 * 岗位实习中心 · 指导记录 / 教师巡访 API（P1-Stage2，生产级只走真实后端）。
 * 端点 /internship/guidances、/internship/visits。
 * owner + 数据范围由后端强校验，前端仅负责交互与提示。
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

export const guidanceVisitApi = {
  // 指导记录
  getGuidances(params = {}) { return callList(`${B}/guidances`, params) },
  getGuidanceDetail(id) { return call(() => request(`${B}/guidances/${id}`)) },
  createGuidance(body) { return call(() => request(`${B}/guidances`, { method: 'POST', body })) },
  voidGuidance(id, { reason } = {}) {
    return call(() => request(`${B}/guidances/${id}/void`, { method: 'POST', body: { reason: reason || '' } }))
  },
  exportGuidances(params = {}) { return call(() => request(`${B}/guidances/export`, { method: 'POST', params })) },
  // 教师巡访
  getVisits(params = {}) { return callList(`${B}/visits`, params) },
  getVisitDetail(id) { return call(() => request(`${B}/visits/${id}`)) },
  createVisit(body) { return call(() => request(`${B}/visits`, { method: 'POST', body })) },
  rectifyVisit(id, { status, note }) {
    return call(() => request(`${B}/visits/${id}/rectify`, { method: 'POST', body: { status, note } }))
  },
  exportVisits(params = {}) { return call(() => request(`${B}/visits/export`, { method: 'POST', params })) }
}

export default guidanceVisitApi
