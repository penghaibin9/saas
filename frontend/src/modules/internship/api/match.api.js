/**
 * 岗位实习中心 · 岗位匹配 API（生产级：仅走真实后端）。
 */
import { request, requestUpload, requestBlob } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'

function ok(data) {
  return Promise.resolve({ code: 0, data, message: 'ok' })
}

function fail(message, code = 1) {
  return Promise.resolve({ code, data: null, message })
}

function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}

async function call(fn) {
  try {
    return ok(await fn())
  } catch (e) {
    return toErr(e)
  }
}

async function callList(path, params = {}) {
  try {
    const d = await request(path, { params })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) {
    return toErr(e)
  }
}

const BASE = '/internship/match'

export const matchApi = {
  getIntentions(params = {}) {
    return callList(`${BASE}/intentions`, params)
  },
  createIntention(body) {
    return call(() => request(`${BASE}/intentions`, { method: 'POST', body }))
  },
  updateIntention(id, body) {
    return call(() => request(`${BASE}/intentions/${id}`, { method: 'PUT', body }))
  },
  submitIntention(id) {
    return call(() => request(`${BASE}/intentions/${id}/submit`, { method: 'POST' }))
  },
  withdrawIntention(id) {
    return call(() => request(`${BASE}/intentions/${id}/withdraw`, { method: 'POST' }))
  },
  async downloadIntentionTemplate() {
    const blob = await requestBlob(`${BASE}/intentions/import/template`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '意向导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  },
  async importIntentionsXlsx(file) {
    try {
      return { code: 0, data: await requestUpload(`${BASE}/intentions/import/xlsx`, file), message: 'ok' }
    } catch (e) {
      return { code: e.code || 1, data: null, message: e.message || '上传失败' }
    }
  },
  importIntentionsConfirm(rows) {
    return call(() => request(`${BASE}/intentions/import/confirm`, { method: 'POST', body: { rows } }))
  },
  downloadIntentionImportErrors(rows, errors) {
    return call(() => request(`${BASE}/intentions/import/errors-xlsx`, { method: 'POST', body: { rows, errors } }))
  },
  exportIntentions(params = {}) {
    return call(() => request(`${BASE}/intentions/export`, { method: 'POST', params }))
  },
  async downloadIntentionExport(params = {}) {
    const res = await this.exportIntentions(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, '实习意向台账.xlsx')
    return res
  },

  runMajor() {
    return call(() => request(`${BASE}/run/major`, { method: 'POST' }))
  },
  runEnterprise() {
    return call(() => request(`${BASE}/run/enterprise`, { method: 'POST' }))
  },
  manualMatch(body) {
    return call(() => request(`${BASE}/manual`, { method: 'POST', body }))
  },
  batchMatch(pairs) {
    return call(() => request(`${BASE}/batch`, { method: 'POST', body: { pairs } }))
  },
  getResults(params = {}) {
    return callList(`${BASE}/results`, params)
  },
  getConflicts(params = {}) {
    return callList(`${BASE}/conflicts`, params)
  },
  getStats() {
    return call(() => request(`${BASE}/stats`))
  },
  confirmMatch(id) {
    return call(() => request(`${BASE}/${id}/confirm`, { method: 'POST' }))
  },
  rejectMatch(id, reason = '') {
    return call(() => request(`${BASE}/${id}/reject`, { method: 'POST', body: { reason } }))
  },
  exportMatches(params = {}) {
    return call(() => request(`${BASE}/export`, { method: 'POST', params }))
  },
  async downloadMatchExport(params = {}) {
    const res = await this.exportMatches(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, '岗位匹配台账.xlsx')
    return res
  },

  getStudentOptions(keyword, pageSize = 200) {
    return call(() =>
      request('/internship/intern-students', { params: { page: 1, pageSize, hasPosition: false, keyword: keyword || '' } }).then((d) =>
        (d.items || []).map((s) => ({
          id: s.id,
          name: s.name,
          studentNo: s.studentNo,
          className: s.className,
          label: `${s.name}（${s.studentNo}）`,
          studentId: s.studentId,
          positionId: s.positionId
        }))
      )
    )
  },
  getPositionOptions(keyword, pageSize = 200) {
    return call(() =>
      request('/internship/positions', { params: { page: 1, pageSize, status: 'PUBLISHED', keyword: keyword || '' } }).then((d) =>
        (d.items || []).map((p) => ({
          id: p.id,
          title: p.title,
          companyName: p.companyName,
          label: `${p.title} · ${p.companyName}`,
          companyId: p.companyId,
          remaining: p.remaining
        }))
      )
    )
  },
  getEnterpriseOptions(keyword, pageSize = 200) {
    return call(() =>
      request('/internship/enterprises', { params: { page: 1, pageSize, keyword: keyword || '' } }).then((d) =>
        (d.items || []).map((e) => ({ id: e.id, name: e.name }))
      )
    )
  }
}

export default matchApi
