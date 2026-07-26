/**
 * 毕业设计中心 · 选题轮次/志愿 API
 */
import { request, requestBlob, requestUpload } from '@/services/http/client'
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

const BASE = '/graduation/gd-topic-rounds'

export const gdTopicRoundApi = {
  getRounds(params = {}) {
    return callList(BASE, params)
  },
  getActiveRound(batchId) {
    return call(() => request(`${BASE}/active`, { params: batchId ? { batchId } : {} }))
  },
  createRound(body) {
    return call(() => request(BASE, { method: 'POST', body }))
  },
  openRound(id) {
    return call(() => request(`${BASE}/${id}/open`, { method: 'POST' }))
  },
  closeRound(id) {
    return call(() => request(`${BASE}/${id}/close`, { method: 'POST' }))
  },
  getChoices(roundId, gdStudentId) {
    return call(() => request(`${BASE}/${roundId}/choices`, { params: gdStudentId ? { gdStudentId } : {} }))
  },
  submitChoices(roundId, { gdStudentId, choices }) {
    return call(() => request(`${BASE}/${roundId}/choices`, { method: 'POST', body: { gdStudentId, choices } }))
  },
  matchRound(id) {
    return call(() => request(`${BASE}/${id}/match`, { method: 'POST' }))
  },
  exportRounds(params = {}) {
    return call(() => request(`${BASE}/export`, { method: 'POST', params }))
  },
  async downloadRoundsExport(params = {}) {
    const res = await this.exportRounds(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, '选题轮次台账.xlsx')
    return res
  },
  exportChoices(roundId, params = {}) {
    return call(() => request(`${BASE}/${roundId}/choices/export`, { method: 'POST', params }))
  },
  async downloadChoicesExport(roundId, params = {}) {
    const res = await this.exportChoices(roundId, params)
    if (res.code === 0) downloadXlsxFromApi(res.data, '选题志愿台账.xlsx')
    return res
  },
  async downloadChoiceImportTemplate(roundId) {
    const blob = await requestBlob(`${BASE}/${roundId}/choices/import/template`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '选题志愿导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  },
  async uploadChoiceImportXlsx(roundId, file) {
    try {
      return ok(await requestUpload(`${BASE}/${roundId}/choices/import/xlsx`, file))
    } catch (e) {
      return toErr(e)
    }
  },
  downloadChoiceImportErrors(roundId, rows, errors) {
    return call(() => request(`${BASE}/${roundId}/choices/import/errors-xlsx`, { method: 'POST', body: { rows, errors } }))
  },
  importChoiceConfirm(roundId, rows, previewToken) {
    return call(() => request(`${BASE}/${roundId}/choices/import/confirm`, { method: 'POST', body: { rows, previewToken } }))
  },
  confirmChoice(choiceId) {
    return call(() => request(`${BASE}/choices/${choiceId}/confirm`, { method: 'POST' }))
  },
  rejectChoice(choiceId, reason) {
    return call(() => request(`${BASE}/choices/${choiceId}/reject`, { method: 'POST', body: { reason } }))
  },
  // Batch 3：容量冲突人工复核 / 选题统计 / 归档 / 退选
  getCapacityConflicts(roundId) {
    return callList(`${BASE}/${roundId}/capacity-conflicts`)
  },
  getRoundStats(roundId) {
    return call(() => request(`${BASE}/${roundId}/stats`))
  },
  archiveRound(id) {
    return call(() => request(`${BASE}/${id}/archive`, { method: 'POST' }))
  },
  withdrawChoices(roundId, gdStudentId) {
    return call(() => request(`${BASE}/${roundId}/choices/withdraw`, { method: 'POST', params: { gdStudentId } }))
  }
}

export default gdTopicRoundApi
