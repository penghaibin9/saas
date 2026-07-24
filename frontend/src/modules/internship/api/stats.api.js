/**
 * 岗位实习中心 · 统计中心 API（生产级：仅走真实后端，不回退 mock）。
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

const B = '/internship/stats'

export const statsApi = {
  getOverview(params = {}) {
    return call(() => request(`${B}/overview`, { params }))
  },

  getDimensions(params = {}) {
    return call(() => request(`${B}/dimensions`, { params }))
  },

  getTrends(params = {}) {
    return call(() => request(`${B}/trends`, { params }))
  },

  exportStats(params = {}) {
    return call(() => request(`${B}/export`, { method: 'POST', params }))
  }
}
