/**
 * 岗位实习中心 · 实习请假审批 / 风险处置闭环 API（P1-Stage3，生产级只走真实后端）。
 * 端点 /internship/leaves、/internship/risks。owner + 数据范围由后端强校验。
 */
import { request } from '@/services/http/client'

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

const B = '/internship'

export const leaveApi = {
  getLeaves(params = {}) { return callList(`${B}/leaves`, params) },
  getLeaveDetail(id) { return call(() => request(`${B}/leaves/${id}`)) },
  review(id, { action, comment, expectedVersion, version }) {
    return call(() => request(`${B}/leaves/${id}/review`, {
      method: 'POST', body: { action, comment, expectedVersion: expectedVersion ?? version }
    }))
  },
  exportLeaves(params = {}) { return call(() => request(`${B}/leaves/export`, { method: 'POST', params })) }
}

export const riskApi = {
  getRisks(params = {}) { return callList(`${B}/risks`, params) },
  getRiskDetail(id) { return call(() => request(`${B}/risks/${id}`)) },
  handle(id, { ownerName, deadline, comment, expectedVersion, version }) {
    return call(() => request(`${B}/risks/${id}/handle`, {
      method: 'POST', body: { ownerName, deadline, comment, expectedVersion: expectedVersion ?? version }
    }))
  },
  follow(id, { note, expectedVersion, version }) {
    return call(() => request(`${B}/risks/${id}/follow`, {
      method: 'POST', body: { note, expectedVersion: expectedVersion ?? version }
    }))
  },
  remind(id, { channel = '站内消息' } = {}) {
    return call(() => request(`${B}/risks/${id}/remind`, { method: 'POST', body: { channel } }))
  },
  escalate(id, { level, note, expectedVersion, version }) {
    return call(() => request(`${B}/risks/${id}/escalate`, {
      method: 'POST', body: { level, note, expectedVersion: expectedVersion ?? version }
    }))
  },
  close(id, { result, comment, expectedVersion, version }) {
    return call(() => request(`${B}/risks/${id}/close`, {
      method: 'POST', body: { result, comment, expectedVersion: expectedVersion ?? version }
    }))
  },
  exportRisks(params = {}) { return call(() => request(`${B}/risks/export`, { method: 'POST', params })) }
}

export const complaintApi = {
  getComplaints(params = {}) { return callList(`${B}/complaints`, params) },
  getComplaintDetail(id) { return call(() => request(`${B}/complaints/${id}`)) },
  create(body) { return call(() => request(`${B}/complaints`, { method: 'POST', body })) },
  transition(id, action, body = {}) {
    return call(() => request(`${B}/complaints/${id}/transition`, {
      method: 'POST', body: { ...(body || {}), action }
    }))
  },
  toRisk(id) { return call(() => request(`${B}/complaints/${id}/to-risk`, { method: 'POST' })) }
}
