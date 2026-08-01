import {
  fetchMyAuthContexts,
  getToken,
  request,
  requestBlob,
  requestUpload
} from '@/services/http/client'
import { API_BASE_URL, API_PREFIX } from '@/services/http/config'

function saveBlob(blob, filename) {
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename || '数据交换回执.xlsx'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(href)
}

function createIdempotencyKey(jobId, expectedVersion) {
  const random = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
  return `data-exchange-confirm:${jobId}:v${expectedVersion}:${random}`
}

async function governedJsonRequest(path, { method = 'GET', params, body, headers = {} } = {}, retried = false) {
  const qs = params
    ? '?' + Object.entries(params)
      .filter(([, value]) => value !== undefined && value !== null && value !== '')
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
      .join('&')
    : ''
  const token = getToken()
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}${qs}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers
    },
    body: body ? JSON.stringify(body) : undefined
  })
  if (response.status === 401 && !retried) {
    // 复用统一客户端完成 refresh-token 单飞轮换，再用新 access token 重试带幂等头请求。
    await fetchMyAuthContexts()
    return governedJsonRequest(path, { method, params, body, headers }, true)
  }
  const payload = await response.json().catch(() => null)
  if (!payload || typeof payload.code !== 'number') {
    throw new Error(`响应结构异常（HTTP ${response.status}）`)
  }
  if (payload.code !== 0) {
    const error = new Error(payload.message || `业务错误 ${payload.code}`)
    error.biz = true
    error.code = payload.code
    error.bizCode = payload.bizCode
    error.traceId = payload.traceId
    error.details = payload.details
    throw error
  }
  return payload.data
}

function visibilityParams(context = {}) {
  return {
    visibility: context.visibility || 'OWN',
    moduleCode: context.moduleCode || undefined
  }
}

export const dataExchangeApi = {
  summary(context = {}) {
    return request('/data-exchange/summary', { params: visibilityParams(context) })
  },
  list(params = {}) {
    return request('/data-exchange/jobs', { params })
  },
  getImport(jobId, context = {}) {
    return request(`/data-exchange/imports/${jobId}`, {
      params: visibilityParams(context)
    })
  },
  getImportErrors(jobId, params = {}) {
    return request(`/data-exchange/imports/${jobId}/errors`, {
      params: { ...visibilityParams(params), page: params.page, pageSize: params.pageSize }
    })
  },
  getExport(jobId, context = {}) {
    return request(`/data-exchange/exports/${jobId}`, {
      params: visibilityParams(context)
    })
  },
  confirmImport(jobId, expectedVersion) {
    const idempotencyKey = createIdempotencyKey(jobId, expectedVersion)
    return governedJsonRequest(`/data-exchange/imports/${jobId}/confirm`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: { expectedVersion }
    })
  },
  cancelImport(jobId, expectedVersion, reason) {
    return request(`/data-exchange/imports/${jobId}/cancel`, {
      method: 'POST',
      body: { expectedVersion, reason }
    })
  },
  retryImport(jobId, expectedVersion) {
    return request(`/data-exchange/imports/${jobId}/retry`, {
      method: 'POST',
      body: { expectedVersion }
    })
  },
  validateIdentity(kind, file) {
    return requestUpload(`/data-exchange/imports/identity/${kind}/validate-file`, file)
  },
  async downloadExport(job) {
    const ticket = await request(`/data-exchange/exports/${job.id}/download-ticket`, {
      method: 'POST',
      body: { expectedVersion: job.version }
    })
    const blob = await requestBlob(`/data-exchange/exports/${job.id}/download`, {
      params: { ticket: ticket.ticket }
    })
    const label = job.exportType === 'INITIAL_CREDENTIAL_RECEIPT'
      ? '初始账号凭据_一次性回执.xlsx'
      : job.exportType === 'IMPORT_ERROR_RECEIPT'
        ? '导入错误回执.xlsx'
        : '数据交换导出.xlsx'
    saveBlob(blob, label)
    return ticket
  },
  revokeExport(jobId, expectedVersion, reason) {
    return request(`/data-exchange/exports/${jobId}/revoke`, {
      method: 'POST',
      body: { expectedVersion, reason }
    })
  }
}
