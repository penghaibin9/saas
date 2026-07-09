/**
 * 岗位实习中心 · 企业评价 API（P2-B，生产级只走真实后端）。
 * 端点 /internship/enterprise-evals。owner + 数据范围由后端强校验。
 */
import { request } from '@/services/http/client'
export { uploadAttachment, downloadAttachment } from '@/modules/internship/api/guidance-visit.api'

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

const B = '/internship/enterprise-evals'

export const enterpriseEvalApi = {
  getEvals(params = {}) { return callList(B, params) },
  getDetail(id) { return call(() => request(`${B}/${id}`)) },
  create(body) { return call(() => request(B, { method: 'POST', body })) },
  review(id, { action, comment }) {
    return call(() => request(`${B}/${id}/review`, { method: 'POST', body: { action, comment } }))
  },
  exportEvals(params = {}) { return call(() => request(`${B}/export`, { method: 'POST', params })) }
}
