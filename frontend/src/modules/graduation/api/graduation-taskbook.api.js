/**
 * 毕业设计中心 · 任务书 / 指导过程 / 中期检查 API（生产级：仅走真实后端，不回退 mock）。
 * 端点 /graduation/gd-taskbooks/*、/gd-guidances/*、/gd-guidance-plans/*、/gd-student-evals/*、/gd-midterms/*。
 */
import { request } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { withGraduationBatch } from '@/modules/graduation/api/graduation-batch-context'

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
    const d = await request(path, { params: withGraduationBatch(params) })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) { return toErr(e) }
}

const TB = '/graduation/gd-taskbooks'
const GD = '/graduation/gd-guidances'
const GP = '/graduation/gd-guidance-plans'
const SE = '/graduation/gd-student-evals'
const MT = '/graduation/gd-midterms'

export const graduationTaskbookApi = {
  getTaskbook(gdStudentId, params = {}) {
    return call(() => request(`${TB}/${gdStudentId}`, { params: withGraduationBatch(params) }))
  },
  issueTaskbook(gdStudentId, body, params = {}) {
    return call(() => request(`${TB}/${gdStudentId}/issue`, { method: 'POST', params: withGraduationBatch(params), body }))
  },
  confirmTaskbook(gdStudentId, body = {}, params = {}) {
    return call(() => request(`${TB}/${gdStudentId}/confirm`, { method: 'POST', params: withGraduationBatch(params), body }))
  },
  changeTaskbook(gdStudentId, body, params = {}) {
    return call(() => request(`${TB}/${gdStudentId}/change`, { method: 'POST', params: withGraduationBatch(params), body }))
  },
  getTaskbookStats(params = {}) {
    return call(() => request(`${TB}/stats`, { params: withGraduationBatch(params) }))
  },
  async downloadTaskbookExport(params = {}) {
    const res = await call(() => request(`${TB}/export`, { method: 'POST', params: withGraduationBatch(params) }))
    if (res.code === 0) downloadXlsxFromApi(res.data, '任务书台账.xlsx')
    return res
  },
  /** 任务书 PDF 导出：返回 { filename, contentBase64, mediaType }，并写下载审计 */
  exportTaskbookPdf(gdStudentId, params = {}) {
    return call(() => request(`${TB}/${gdStudentId}/export-pdf`, { method: 'POST', params: withGraduationBatch(params) }))
  },
  async downloadTaskbookPdf(gdStudentId, params = {}) {
    const res = await this.exportTaskbookPdf(gdStudentId, params)
    if (res.code === 0) downloadXlsxFromApi(res.data)
    return res
  },
  getGuidanceList(params = {}) { return callList(GD, params) },
  createGuidance(gdStudentId, body, params = {}) {
    return call(() => request(`${GD}/${gdStudentId}`, { method: 'POST', params: withGraduationBatch(params), body }))
  },
  voidGuidance(id, reason, params = {}) {
    return call(() => request(`${GD}/records/${id}/void`, { method: 'POST', params: withGraduationBatch(params), body: { reason } }))
  },
  getGuidanceStats(threshold = 3, params = {}) {
    return call(() => request(`${GD}/stats`, { params: withGraduationBatch({ ...params, threshold }) }))
  },
  getGuidancePlans(params = {}) { return callList(GP, params) },
  createGuidancePlan(gdStudentId, body, params = {}) {
    return call(() => request(`${GP}/${gdStudentId}`, { method: 'POST', params: withGraduationBatch(params), body }))
  },
  checkinGuidancePlan(planId, body = {}, params = {}) {
    return call(() => request(`${GP}/${planId}/checkin`, { method: 'POST', params: withGraduationBatch(params), body }))
  },
  cancelGuidancePlan(planId, reason, params = {}) {
    return call(() => request(`${GP}/${planId}/cancel`, { method: 'POST', params: withGraduationBatch(params), body: { reason } }))
  },
  getStudentEvals(params = {}) { return callList(SE, params) },
  createStudentEval(gdStudentId, body, params = {}) {
    return call(() => request(`${SE}/${gdStudentId}`, { method: 'POST', params: withGraduationBatch(params), body }))
  },
  submitStudentEval(evalId, params = {}) {
    return call(() => request(`${SE}/records/${evalId}/submit`, { method: 'POST', params: withGraduationBatch(params) }))
  },
  getMidterm(gdStudentId, params = {}) {
    return call(() => request(`${MT}/${gdStudentId}`, { params: withGraduationBatch(params) }))
  },
  checkMidterm(gdStudentId, body, params = {}) {
    return call(() => request(`${MT}/${gdStudentId}/check`, { method: 'POST', params: withGraduationBatch(params), body }))
  },
  submitRectification(gdStudentId, content, params = {}) {
    return call(() => request(`${MT}/${gdStudentId}/rectify`, {
      method: 'POST', params: withGraduationBatch(params), body: { content },
    }))
  },
  reviewRectification(gdStudentId, body, params = {}) {
    return call(() => request(`${MT}/${gdStudentId}/rectify/review`, { method: 'POST', params: withGraduationBatch(params), body }))
  },
  getMidtermStats(params = {}) {
    return call(() => request(`${MT}/stats`, { params: withGraduationBatch(params) }))
  }
}

export default graduationTaskbookApi
