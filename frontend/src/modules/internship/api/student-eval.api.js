/**
 * 岗位实习中心 · 学生鉴定/自评 API（P2-C，生产级只走真实后端）。
 * 教师端 /internship/student-evals（列表/详情/意见/审核/导出）。学生自评走 mobile。
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

const B = '/internship/student-evals'

export const studentEvalApi = {
  getEvals(params = {}) { return callList(B, params) },
  getDetail(id) { return call(() => request(`${B}/${id}`)) },
  advisorComment(id, { advisorOpinion, mentorOpinion }) {
    return call(() => request(`${B}/${id}/advisor-comment`, { method: 'POST', body: { advisorOpinion, mentorOpinion } }))
  },
  review(id, { action, comment }) {
    return call(() => request(`${B}/${id}/review`, { method: 'POST', body: { action, comment } }))
  },
  exportEvals(params = {}) { return call(() => request(`${B}/export`, { method: 'POST', params })) }
}
