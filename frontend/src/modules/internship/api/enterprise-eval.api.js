/**
 * 岗位实习中心 · 企业评价 API。
 * 录入人与审核人分离；当前管理端审核只走版本化端点。
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
  review(id, { action, comment, expectedVersion }) {
    return call(async () => {
      let version = expectedVersion
      if (version == null) {
        const detail = await request(`${B}/${id}`)
        version = detail?.version
      }
      if (version == null) throw { biz: true, code: 'DATA_CONFLICT', message: '企业评价版本缺失，请刷新后重试' }
      return request(`${B}/${id}/review-versioned`, {
        method: 'POST', body: { action, comment, expectedVersion: version }
      })
    })
  },
  exportEvals(params = {}) { return call(() => request(`${B}/export`, { method: 'POST', params })) }
}
