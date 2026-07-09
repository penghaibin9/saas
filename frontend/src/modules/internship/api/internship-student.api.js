/**
 * 岗位实习中心 · 实习学生 API（生产级：仅走真实后端，不回退 mock）。
 * 端点 /internship/intern-students/*（避开旧 /internship/students/*）。
 */
import { request } from '@/services/http/client'

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
  setEligibility(id, { status, reason }) {
    return call(() => request(`${BASE}/${id}/eligibility`, { method: 'POST', body: { status, reason } }))
  },
  setDestination(id, { destination, reason }) {
    return call(() => request(`${BASE}/${id}/destination`, { method: 'POST', body: { destination, reason } }))
  },
  getStats() {
    return call(() => request(`${BASE}/stats`))
  },
  importDryRun(rows) {
    return call(() => request(`${BASE}/import/dry-run`, { method: 'POST', body: { rows } }))
  },
  importConfirm(rows) {
    return call(() => request(`${BASE}/import/confirm`, { method: 'POST', body: { rows } }))
  },
  exportStudents(params = {}) {
    return call(() => request(`${BASE}/export`, { method: 'POST', params }))
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
