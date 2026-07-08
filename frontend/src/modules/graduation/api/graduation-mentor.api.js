/**
 * 毕业设计中心 · 导师管理 + 导师分配 API（生产级：仅走真实后端，不回退 mock）。
 * 端点 /graduation/gd-mentors/*、/graduation/gd-mentor-assignments/*。
 * 独立文件，与毕业设计域其它 api 隔离；不依赖实习/迎新模块。
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

const BASE = '/graduation/gd-mentors'
const ASSIGN_BASE = '/graduation/gd-mentor-assignments'

export const graduationMentorApi = {
  getMentors(params = {}) {
    return callList(BASE, params)
  },
  getMentorDetail(id) {
    return call(() => request(`${BASE}/${id}`))
  },
  createMentor(body) {
    return call(() => request(BASE, { method: 'POST', body }))
  },
  updateMentor(id, body) {
    return call(() => request(`${BASE}/${id}`, { method: 'PUT', body }))
  },
  reviewMentor(id, action, comment) {
    return call(() => request(`${BASE}/${id}/review`, { method: 'POST', body: { action, comment } }))
  },
  disableMentor(id, reason) {
    return call(() => request(`${BASE}/${id}/disable`, { method: 'POST', body: { reason } }))
  },
  enableMentor(id) {
    return call(() => request(`${BASE}/${id}/enable`, { method: 'POST' }))
  },
  archiveMentor(id) {
    return call(() => request(`${BASE}/${id}/archive`, { method: 'POST' }))
  },
  getStats() {
    return call(() => request(`${BASE}/stats`))
  },
  importDryRun(rows) {
    return call(() => request(`${BASE}/import/dry-run`, { method: 'POST', body: { rows } }))
  },
  async downloadImportTemplate() {
    const blob = await requestBlob(`${BASE}/import/template`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = '导师名单导入模板.xlsx'; a.click()
    URL.revokeObjectURL(url)
  },
  async uploadImportXlsx(file) {
    try { return ok(await requestUpload(`${BASE}/import/xlsx`, file)) } catch (e) { return toErr(e) }
  },
  downloadImportErrors(rows, errors) {
    return call(() => request(`${BASE}/import/errors-xlsx`, { method: 'POST', body: { rows, errors } }))
  },
  importConfirm(rows) {
    return call(() => request(`${BASE}/import/confirm`, { method: 'POST', body: { rows } }))
  },
  exportMentors(params = {}) {
    return call(() => request(`${BASE}/export`, { method: 'POST', params }))
  },
  async downloadMentorExport(params = {}) {
    const res = await this.exportMentors(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, '导师名单与工作量台账.xlsx')
    return res
  },
  // 导师分配
  getAssignments(params = {}) {
    return callList(ASSIGN_BASE, params)
  },
  getUnassignedStudents(params = {}) {
    return callList(`${ASSIGN_BASE}/unassigned-students`, params)
  },
  assignMentor(gdStudentId, mentorId, reason) {
    return call(() => request(`${ASSIGN_BASE}/assign`, { method: 'POST', body: { gdStudentId, mentorId, reason } }))
  },
  changeMentor(gdStudentId, newMentorId, reason) {
    return call(() => request(`${ASSIGN_BASE}/change`, { method: 'POST', body: { gdStudentId, newMentorId, reason } }))
  },
  cancelAssignment(id, reason) {
    return call(() => request(`${ASSIGN_BASE}/${id}/cancel`, { method: 'POST', body: { reason } }))
  },
  // Batch 4：导师评价 / 分配冲突检测 / 批量分配 / 批量归档
  getEvals(mentorId) {
    return callList(`${BASE}/${mentorId}/evals`)
  },
  createEval(mentorId, body) {
    return call(() => request(`${BASE}/${mentorId}/evals`, { method: 'POST', body }))
  },
  getConflicts() {
    return call(() => request(`${BASE}/conflicts`))
  },
  batchAssign(assignments) {
    return call(() => request(`${BASE}/batch-assign`, { method: 'POST', body: { assignments } }))
  },
  batchArchive(mentorIds) {
    return call(() => request(`${BASE}/batch-archive`, { method: 'POST', body: { mentorIds } }))
  }
}

export default graduationMentorApi
