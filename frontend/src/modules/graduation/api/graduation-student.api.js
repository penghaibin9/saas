/**
 * 毕业设计中心 · 毕设学生 API（真实后端）。
 * 学校端列表、统计、导出均绑定当前批次；跨批操作由后端二次校验。
 */
import { request, requestBlob, requestUpload } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try { return ok(await fn()) } catch (e) { return toErr(e) }
}
function withBatch(params = {}, required = true) {
  const store = useGraduationBatchStore()
  const batchId = params.batchId || store.selectedBatchId
  if (required && !batchId) throw new Error('请先选择毕业设计批次')
  return batchId ? { ...params, batchId: String(batchId) } : { ...params }
}
async function callList(path, params = {}, required = true) {
  try {
    const d = await request(path, { params: withBatch(params, required) })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) { return toErr(e) }
}

const BASE = '/graduation/gd-students'

export const gdStudentApi = {
  getStudents(params = {}) { return callList(BASE, params) },
  getStudentDetail(id) { return call(() => request(`${BASE}/${id}`)) },
  createStudent(body) { return call(() => request(BASE, { method: 'POST', body })) },
  updateStudent(id, body) { return call(() => request(`${BASE}/${id}`, { method: 'PUT', body })) },
  assignTopic(id, { topicId }) {
    return call(() => request(`${BASE}/${id}/assign-topic`, { method: 'POST', body: { topicId } }))
  },
  unassignTopic(id, { reason }) {
    return call(() => request(`${BASE}/${id}/unassign-topic`, { method: 'POST', body: { reason } }))
  },
  assignAdvisor(id, { advisorName }) {
    return call(() => request(`${BASE}/${id}/assign-advisor`, { method: 'POST', body: { advisorName } }))
  },
  setStage(id, { action, reason }) {
    return call(() => request(`${BASE}/${id}/stage`, { method: 'POST', body: { action, reason } }))
  },
  setRisk(id, { riskLevel, reason }) {
    return call(() => request(`${BASE}/${id}/risk`, { method: 'POST', body: { riskLevel, reason } }))
  },
  setEligibility(id, { status, reason }) {
    return call(() => request(`${BASE}/${id}/eligibility`, { method: 'POST', body: { status, reason } }))
  },
  setStudentGroup(id, { groupName, reason }) {
    return call(() => request(`${BASE}/${id}/group`, { method: 'POST', body: { groupName, reason } }))
  },
  batchSetStudentGroup({ recordIds, groupName, reason }) {
    return call(() => request(`${BASE}/batch-group`, { method: 'POST', body: { recordIds, groupName, reason } }))
  },
  assignDefenseGroup(id, { defenseGroupId, reason }) {
    return call(() => request(`${BASE}/${id}/defense-group`, { method: 'POST', body: { defenseGroupId, reason } }))
  },
  setGradQual(id, { status, note, reason }) {
    return call(() => request(`${BASE}/${id}/grad-qual`, { method: 'POST', body: { status, note, reason } }))
  },
  batchArchive({ recordIds, reason }) {
    return call(() => request(`${BASE}/batch-archive`, { method: 'POST', body: { recordIds, reason } }))
  },
  getStudentGroups() { return call(() => request(`${BASE}/groups`)) },
  getStats(params = {}) {
    return call(() => request(`${BASE}/stats`, { params: withBatch(params) }))
  },
  importDryRun(rows) {
    return call(() => request(`${BASE}/import/dry-run`, { method: 'POST', body: { rows } }))
  },
  async downloadImportTemplate() {
    const blob = await requestBlob(`${BASE}/import/template`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '毕设学生导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  },
  async uploadImportXlsx(file) {
    try { return ok(await requestUpload(`${BASE}/import/xlsx`, file)) } catch (e) { return toErr(e) }
  },
  downloadImportErrors(rows, errors) {
    return call(() => request(`${BASE}/import/errors-xlsx`, { method: 'POST', body: { rows, errors } }))
  },
  importConfirm(rows, previewToken) {
    return call(() => request(`${BASE}/import/confirm`, { method: 'POST', body: { rows, previewToken } }))
  },
  exportStudents(params = {}) {
    return call(() => request(`${BASE}/export`, { method: 'POST', params: withBatch(params) }))
  },
  async downloadExport(params = {}) {
    const res = await this.exportStudents(params)
    if (res.code === 0) {
      const hint = params.filenameHint || params.exportHint
      const filename = res.data?.filename || (hint ? `${String(hint).replace(/\.xlsx$/i, '')}.xlsx` : '毕设学生台账.xlsx')
      downloadXlsxFromApi({ ...(res.data || {}), filename })
    }
    return res
  },
  getStudentOptions(keyword) {
    return call(() =>
      request('/students', { params: { page: 1, pageSize: 200, keyword: keyword || '' } }).then((d) =>
        (d.items || []).map((s) => ({ id: s.id || s.studentId, name: s.realName || s.name, studentNo: s.studentNo }))
      )
    )
  },
  getBatchOptions() {
    return call(() =>
      request('/graduation/batches', { params: { page: 1, pageSize: 200 } }).then((d) =>
        (d.items || []).map((b) => ({ id: b.id, batchName: b.batchName, batchNo: b.batchNo, status: b.status }))
      )
    )
  },
  getConfirmedTopics() { return gdTopicApi.getAssignableTopics() },
  getDefenseGroups() {
    return call(() =>
      request('/graduation/defense-groups', { params: { page: 1, pageSize: 200 } }).then((d) =>
        (d.items || []).map((g) => ({
          id: g.id, groupName: g.groupName, defenseDate: g.defenseDate, location: g.location,
          studentCount: g.studentCount, published: g.published
        }))
      )
    )
  }
}

export default gdStudentApi
