/**
 * 岗位实习中心 · 统计中心 API（生产级：仅走真实后端，不回退 mock）。
 */
import { request } from '@/services/http/client'
import { normalizeUiError } from '@/utils/presentationSafety'

function ok(data) {
  return Promise.resolve({ code: 0, data, message: 'ok' })
}

function fail(message, code = 1) {
  return Promise.resolve({ code, data: null, message })
}

function toErr(e) {
  return fail(normalizeUiError(e).userMessage,e?.code || 503001)
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
  getMetricDrilldown(key,params={}) {
    return call(()=>request(`${B}/metrics/${encodeURIComponent(key)}/drilldown`,{params}))
  },
  exportMetricDrilldown(key,params={}) {
    return call(()=>request(`${B}/metrics/${encodeURIComponent(key)}/drilldown/export`,{method:'POST',params}))
  },
  getProcurementOverview(params={}) {
    return call(()=>request(`${B}/procurement-overview`,{params}))
  },
  exportProcurementOverview(params={}) {
    return call(()=>request(`${B}/procurement-overview/export`,{method:'POST',params}))
  },
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
  },

  getProcessAnalytics(params = {}) {
    return call(() => request(`${B}/process-analytics`, { params }))
  },

  exportProcessAnalytics(params = {}) {
    return call(() => request(`${B}/process-analytics/export`, { method: 'POST', params }))
  }
}
