/**
 * 毕业设计中心 · 任务书 / 指导过程 / 中期检查 API（生产级：仅走真实后端，不回退 mock）。
 * 端点 /graduation/gd-taskbooks/*、/gd-guidances/*、/gd-midterms/*。
 */
import { request } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'

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

const TB = '/graduation/gd-taskbooks'
const GD = '/graduation/gd-guidances'
const MT = '/graduation/gd-midterms'

export const graduationTaskbookApi = {
  getTaskbook(gdStudentId) { return call(() => request(`${TB}/${gdStudentId}`)) },
  issueTaskbook(gdStudentId, body) { return call(() => request(`${TB}/${gdStudentId}/issue`, { method: 'POST', body })) },
  confirmTaskbook(gdStudentId) { return call(() => request(`${TB}/${gdStudentId}/confirm`, { method: 'POST' })) },
  changeTaskbook(gdStudentId, body) { return call(() => request(`${TB}/${gdStudentId}/change`, { method: 'POST', body })) },
  getTaskbookStats() { return call(() => request(`${TB}/stats`)) },
  async downloadTaskbookExport(params = {}) {
    const res = await call(() => request(`${TB}/export`, { method: 'POST', params }))
    if (res.code === 0) downloadXlsxFromApi(res.data, '任务书台账.xlsx')
    return res
  },
  getGuidanceList(params = {}) { return callList(GD, params) },
  createGuidance(gdStudentId, body) { return call(() => request(`${GD}/${gdStudentId}`, { method: 'POST', body })) },
  voidGuidance(id, reason) { return call(() => request(`${GD}/records/${id}/void`, { method: 'POST', body: { reason } })) },
  getGuidanceStats(threshold = 3) { return call(() => request(`${GD}/stats`, { params: { threshold } })) },
  getMidterm(gdStudentId) { return call(() => request(`${MT}/${gdStudentId}`)) },
  checkMidterm(gdStudentId, body) { return call(() => request(`${MT}/${gdStudentId}/check`, { method: 'POST', body })) },
  submitRectification(gdStudentId, content) { return call(() => request(`${MT}/${gdStudentId}/rectify`, { method: 'POST', body: { content } })) },
  reviewRectification(gdStudentId, body) { return call(() => request(`${MT}/${gdStudentId}/rectify/review`, { method: 'POST', body })) },
  getMidtermStats() { return call(() => request(`${MT}/stats`)) }
}

export default graduationTaskbookApi
