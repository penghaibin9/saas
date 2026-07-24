/**
 * 岗位实习中心 · 实习学生 API（生产级：仅走真实后端，不回退 mock）。
 * 端点 /internship/intern-students/*（避开旧 /internship/students/*）。
 */
import { request, requestBlob, requestUpload } from '@/services/http/client'

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

const BASE = '/internship/intern-students'

export const internStudentApi = {
  getStudents(params = {}) {
    return callList(BASE, params)
  },
  getStudentDetail(id) {
    return call(() => request(`${BASE}/${id}`))
  },
  createStudent(body) {
    return call(() => request(BASE, { method: 'POST', body }))
  },
  updateStudent(id, body) {
    return call(() => request(`${BASE}/${id}`, { method: 'PUT', body }))
  },
  assignPosition(id, { positionId }) {
    return call(() => request(`${BASE}/${id}/assign`, { method: 'POST', body: { positionId } }))
  },
  unassignPosition(id, { reason }) {
    return call(() => request(`${BASE}/${id}/unassign`, { method: 'POST', body: { reason } }))
  },
  setStatus(id, { action, reason }) {
    return call(() => request(`${BASE}/${id}/status`, { method: 'POST', body: { action, reason } }))
  },
  /** 上岗前置检查清单（BUG-010）：岗位/三方协议/保险/指导教师，按批次规则裁定。 */
  getOnboardChecklist(id) {
    return call(() => request(`${BASE}/${id}/onboard-checklist`))
  },
  setEligibility(id, { status, reason }) {
    return call(() => request(`${BASE}/${id}/eligibility`, { method: 'POST', body: { status, reason } }))
  },
  setDestination(id, { destination, reason }) {
    return call(() => request(`${BASE}/${id}/destination`, { method: 'POST', body: { destination, reason } }))
  },
  getStats() {
    return call(() => request(`${BASE}/stats`))
  },
  getAdvisors(keyword = '') {
    return call(() => request(`${BASE}/advisors`, { params: { keyword } }))
  },
  getAssignmentLogs(params = {}) {
    return callList(`${BASE}/assignment-logs`, params)
  },
  assignAdvisor(id, { advisorUserId, reason = '' }) {
    return call(() => request(`${BASE}/${id}/advisor`, { method: 'POST', body: { advisorUserId, reason } }))
  },
  importDryRun(rows, batchId) {
    return call(() => request(`${BASE}/import/dry-run`, { method: 'POST', body: { rows, batchId } }))
  },
  importConfirm(rows, batchId) {
    return call(() => request(`${BASE}/import/confirm`, { method: 'POST', body: { rows, batchId } }))
  },
  exportStudents(params = {}) {
    return call(() => request(`${BASE}/export`, { method: 'POST', params }))
  },
  async downloadImportTemplate() {
    const blob = await requestBlob(`${BASE}/import/template`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '实习学生导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  },
  async uploadImportXlsx(file, batchId) {
    try {
      const q = batchId ? `?batchId=${encodeURIComponent(batchId)}` : ''
      return ok(await requestUpload(`${BASE}/import/xlsx${q}`, file))
    } catch (e) {
      return toErr(e)
    }
  },
  async downloadImportErrors(rows, errors) {
    try {
      const blob = await requestBlob(`${BASE}/import/errors-xlsx`, {
        method: 'POST',
        body: { rows, errors }
      })
      const buf = await blob.arrayBuffer()
      const bytes = new Uint8Array(buf)
      let binary = ''
      for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i])
      return ok({
        contentBase64: btoa(binary),
        filename: 'intern_student_import_errors.xlsx',
        mediaType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      })
    } catch (e) {
      return toErr(e)
    }
  },
  importConfirmRows(rows, batchId) {
    return call(() => request(`${BASE}/import/confirm`, { method: 'POST', body: { rows, batchId } }))
  },
  // 建档用：可选学生（学生主档）；分配用：已上架岗位
  getStudentOptions(keyword) {
    return call(() =>
      request('/students', { params: { page: 1, pageSize: 200, keyword: keyword || '' } }).then((d) =>
        (d.items || []).map((s) => ({ id: s.id || s.studentId, name: s.realName || s.name, studentNo: s.studentNo }))
      )
    )
  },
  getPublishedPositions() {
    return call(() =>
      request('/internship/positions', { params: { page: 1, pageSize: 200, status: 'PUBLISHED' } }).then((d) =>
        (d.items || []).map((p) => ({
          id: p.id, title: p.title, companyName: p.companyName,
          remaining: p.remaining, capacity: `${p.allocatedCount}/${p.headcount}`
        }))
      )
    )
  }
}

export default internStudentApi
