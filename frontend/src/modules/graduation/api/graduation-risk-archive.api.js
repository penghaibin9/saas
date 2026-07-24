/**
 * 毕业设计中心 · 问题预警 / 毕设归档 / 毕设统计 API（生产级：仅走真实后端，不回退 mock）。
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

const RISK = '/graduation/gd-risks'
const ARCHIVE = '/graduation/gd-archives'
const STATS = '/graduation/gd-stats'

export const graduationRiskArchiveApi = {
  scanRisks() { return call(() => request(`${RISK}/scan`, { method: 'POST' })) },
  getRiskList(params = {}) { return callList(RISK, params) },
  /** 按学生取归档记录（不存在则后端返回待生成态） */
  getArchiveByStudent(gdStudentId) { return call(() => request(ARCHIVE + '/' + gdStudentId)) },
  getRiskStats() { return call(() => request(`${RISK}/stats`)) },
  acceptRisk(id, assignee) { return call(() => request(`${RISK}/${id}/accept`, { method: 'POST', body: { assignee } })) },
  processRisk(id, note) { return call(() => request(`${RISK}/${id}/process`, { method: 'POST', body: { note } })) },
  closeRisk(id, reason) { return call(() => request(`${RISK}/${id}/close`, { method: 'POST', body: { reason } })) },

  getArchiveList(params = {}) { return callList(ARCHIVE, params) },
  getArchiveStats() { return call(() => request(`${ARCHIVE}/stats`)) },
  batchGenerateArchive() { return call(() => request(`${ARCHIVE}/batch-generate`, { method: 'POST' })) },
  batchFileArchive() { return call(() => request(`${ARCHIVE}/batch-file`, { method: 'POST', body: {} })) },
  generateArchive(gdStudentId) { return call(() => request(`${ARCHIVE}/${gdStudentId}/generate`, { method: 'POST' })) },
  submitArchive(gdStudentId) { return call(() => request(`${ARCHIVE}/${gdStudentId}/submit`, { method: 'POST' })) },
  fileArchive(gdStudentId, archiveBatchNo) { return call(() => request(`${ARCHIVE}/${gdStudentId}/file`, { method: 'POST', body: { archiveBatchNo } })) },
  rejectArchive(gdStudentId, reason) { return call(() => request(`${ARCHIVE}/${gdStudentId}/reject`, { method: 'POST', body: { reason } })) },
  exportArchives(params = {}) {
    return call(() => request(`${ARCHIVE}/export`, { method: 'POST', params }))
  },
  async downloadArchiveExport(params = {}) {
    const res = await this.exportArchives(params)
    if (res.code === 0) {
      const hint = params.filenameHint || params.exportHint
      const filename = res.data?.filename || (hint ? `${String(hint).replace(/\.xlsx$/i, '')}.xlsx` : '毕设归档台账.xlsx')
      downloadXlsxFromApi({ ...(res.data || {}), filename })
    }
    return res
  },

  getOverviewStats() { return call(() => request(`${STATS}/overview`)) },
  getCollegeComparison() { return call(() => request(`${STATS}/college-comparison`)) }
}

export default graduationRiskArchiveApi
