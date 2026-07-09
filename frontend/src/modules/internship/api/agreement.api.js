/**
 * 岗位实习中心 · 三方协议签署实例 API（P2-A，生产级只走真实后端）。
 * 端点 /internship/agreements。三方确认状态机 + owner + 数据范围由后端强校验。
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

const B = '/internship/agreements'

export const agreementApi = {
  getAgreements(params = {}) { return callList(B, params) },
  getDetail(id) { return call(() => request(`${B}/${id}`)) },
  generate(body) { return call(() => request(B, { method: 'POST', body })) },
  issue(id) { return call(() => request(`${B}/${id}/issue`, { method: 'POST', body: {} })) },
  enterpriseConfirm(id, { confirmBy, fileId }) {
    return call(() => request(`${B}/${id}/enterprise-confirm`, { method: 'POST', body: { confirmBy, fileId } }))
  },
  schoolConfirm(id) { return call(() => request(`${B}/${id}/school-confirm`, { method: 'POST', body: {} })) },
  reject(id, { reason }) { return call(() => request(`${B}/${id}/reject`, { method: 'POST', body: { reason } })) },
  voidAgreement(id, { reason } = {}) { return call(() => request(`${B}/${id}/void`, { method: 'POST', body: { reason: reason || '' } })) },
  archive(id) { return call(() => request(`${B}/${id}/archive`, { method: 'POST', body: {} })) },
  exportAgreements(params = {}) { return call(() => request(`${B}/export`, { method: 'POST', params })) }
}
