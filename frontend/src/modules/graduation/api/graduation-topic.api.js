/**
 * 毕业设计中心 · 题目库 API（生产级：/graduation/gd-topics/*）
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

const BASE = '/graduation/gd-topics'

export const gdTopicApi = {
  getTopics(params = {}) {
    return callList(BASE, params)
  },
  getTopicDetail(id) {
    return call(() => request(`${BASE}/${id}`))
  },
  getAssignedStudents(id) {
    return call(() => request(`${BASE}/${id}/assigned-students`))
  },
  createTopic(body) {
    return call(() => request(BASE, { method: 'POST', body }))
  },
  updateTopic(id, body) {
    return call(() => request(`${BASE}/${id}`, { method: 'PUT', body }))
  },
  submitReview(id) {
    return call(() => request(`${BASE}/${id}/submit-review`, { method: 'POST' }))
  },
  reviewTopic(id, { action, comment }) {
    return call(() => request(`${BASE}/${id}/review`, { method: 'POST', body: { action, comment } }))
  },
  disableTopic(id, { reason }) {
    return call(() => request(`${BASE}/${id}/disable`, { method: 'POST', body: { reason } }))
  },
  enableTopic(id) {
    return call(() => request(`${BASE}/${id}/enable`, { method: 'POST' }))
  },
  archiveTopic(id, { reason }) {
    return call(() => request(`${BASE}/${id}/archive`, { method: 'POST', body: { reason } }))
  },
  getStats(params = {}) {
    return call(() => request(`${BASE}/stats`, { params }))
  },
  getCategoryStats(params = {}) {
    return call(() => request(`${BASE}/category-stats`, { params }))
  },
  getTopicHistory(params = {}) {
    return callList(`${BASE}/history`, params)
  },
  exportTopicHistory(params = {}) {
    return call(() => request(`${BASE}/history/export`, { method: 'POST', params }))
  },
  async downloadHistoryExport(params = {}) {
    const res = await this.exportTopicHistory(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, '题目操作历史.xlsx')
    return res
  },
  updateAttachments(id, attachments) {
    return call(() => request(`${BASE}/${id}/attachments`, { method: 'PUT', body: { attachments } }))
  },
  updateCapacity(id, capacity) {
    return call(() => request(`${BASE}/${id}/capacity`, { method: 'PUT', body: { capacity } }))
  },
  importDryRun(rows) {
    return call(() => request(`${BASE}/import/dry-run`, { method: 'POST', body: { rows } }))
  },
  async downloadImportTemplate() {
    const blob = await requestBlob(`${BASE}/import/template`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '题目库导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  },
  async uploadImportXlsx(file) {
    try {
      return ok(await requestUpload(`${BASE}/import/xlsx`, file))
    } catch (e) {
      return toErr(e)
    }
  },
  downloadImportErrors(rows, errors) {
    return call(() => request(`${BASE}/import/errors-xlsx`, { method: 'POST', body: { rows, errors } }))
  },
  importConfirm(rows, previewToken) {
    return call(() => request(`${BASE}/import/confirm`, { method: 'POST', body: { rows, previewToken } }))
  },
  exportTopics(params = {}) {
    return call(() => request(`${BASE}/export`, { method: 'POST', params }))
  },
  async downloadExport(params = {}) {
    const res = await this.exportTopics(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, '题目库台账.xlsx')
    return res
  },
  getBatchOptions() {
    return call(() =>
      request('/graduation/batches', { params: { page: 1, pageSize: 200 } }).then((d) =>
        (d.items || []).map((b) => ({ id: b.id, batchName: b.batchName, batchNo: b.batchNo }))
      )
    )
  },
  getAssignableTopics() {
    return call(() =>
      request(BASE, {
        params: { page: 1, pageSize: 200, reviewStatus: 'APPROVED', status: 'CONFIRMED', isFull: false, archiveView: 'active' }
      }).then((d) =>
        (d.items || []).map((t) => ({
          id: t.id, title: t.title, advisorName: t.advisorName,
          remaining: t.remaining, capacity: `${t.selected}/${t.capacity}`
        }))
      )
    )
  }
}

export default gdTopicApi
