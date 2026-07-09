/**
 * 岗位实习中心 · 实习协议模板库 API（生产级：仅走真实后端，不回退 mock）。
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

const BASE = '/internship/agreement-templates'

export const agreementTemplateApi = {
  getTemplates(params = {}) {
    return callList(BASE, params)
  },
  getTemplateDetail(id) {
    return call(() => request(`${BASE}/${id}`))
  },
  getStats() {
    return call(() => request(`${BASE}/stats`))
  },
  getVariablePresets() {
    return call(() => request(`${BASE}/variables`))
  },
  createTemplate(body) {
    return call(() => request(BASE, { method: 'POST', body }))
  },
  updateTemplate(id, body) {
    return call(() => request(`${BASE}/${id}`, { method: 'PUT', body }))
  },
  setStatus(id, { action, reason }) {
    return call(() => request(`${BASE}/${id}/status`, { method: 'POST', body: { action, reason } }))
  },
  setDefault(id, on) {
    return call(() => request(`${BASE}/${id}/default`, { method: 'POST', body: { on } }))
  }
}
