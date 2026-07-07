/**
 * 岗位实习中心 · 岗位库 API（生产级：仅走真实后端，不回退 mock）。
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

export const positionApi = {
  getPositions(params = {}) {
    return callList('/internship/positions', params)
  },

  getPositionDetail(id) {
    return call(() => request(`/internship/positions/${id}`))
  },

  createPosition(body) {
    return call(() => request('/internship/positions', { method: 'POST', body }))
  },

  updatePosition(id, body) {
    return call(() => request(`/internship/positions/${id}`, { method: 'PUT', body }))
  },

  setPositionStatus(id, { action, reason }) {
    return call(() => request(`/internship/positions/${id}/status`, { method: 'POST', body: { action, reason } }))
  },

  markPositionRisk(id, { on, note }) {
    return call(() => request(`/internship/positions/${id}/risk`, { method: 'POST', body: { on, note } }))
  },

  getPositionStats() {
    return call(() => request('/internship/positions/stats'))
  },

  importPositionsDryRun(rows) {
    return call(() => request('/internship/positions/import/dry-run', { method: 'POST', body: { rows } }))
  },

  importPositionsConfirm(rows) {
    return call(() => request('/internship/positions/import/confirm', { method: 'POST', body: { rows } }))
  },

  exportPositions(params = {}) {
    return call(() => request('/internship/positions/export', { method: 'POST', params }))
  },

  getEnterpriseOptions() {
    return call(() =>
      request('/internship/enterprises', { params: { page: 1, pageSize: 200 } }).then((d) =>
        (d.items || []).map((e) => ({ id: e.id, name: e.name, coopStatus: e.coopStatus, blacklist: e.blacklist }))
      )
    )
  },

  getEnterpriseMentors(companyId) {
    return call(() =>
      request(`/internship/enterprises/${companyId}/contacts`).then((d) =>
        (d.items || []).filter((c) => c.contactType === 'MENTOR')
      )
    )
  }
}

export default positionApi
