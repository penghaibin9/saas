import { API_BASE_URL, API_PREFIX } from './config'
import { getToken } from './client'

/**
 * Authenticated multipart POST for business uploads that require extra form fields.
 * Browser owns Content-Type/boundary; never set it manually for FormData.
 * This intentionally mirrors requestUpload's fail-closed write behavior without
 * changing its existing call contract across the application.
 */
export async function requestMultipart(path, { files = {}, fields = {}, timeoutMs = 15000 } = {}) {
  const token = getToken()
  if (!token) {
    const err = new Error('未登录，请先登录')
    err.biz = true
    err.code = 401001
    throw err
  }

  const form = new FormData()
  Object.entries(files || {}).forEach(([name, file]) => {
    if (file != null) form.append(name, file)
  })
  Object.entries(fields || {}).forEach(([name, value]) => {
    if (value !== undefined && value !== null && value !== '') form.append(name, String(value))
  })

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
      signal: controller.signal,
      credentials: 'include'
    })
    const payload = await response.json().catch(() => null)
    if (!payload || typeof payload.code !== 'number') {
      const err = new Error(`响应结构异常（HTTP ${response.status}）`)
      err.biz = true
      err.code = response.status || 500
      throw err
    }
    if (payload.code !== 0) {
      const err = new Error(payload.message || `业务错误 ${payload.code}`)
      err.biz = true
      err.code = payload.code
      err.bizCode = payload.bizCode
      err.details = payload.details
      err.traceId = payload.traceId
      throw err
    }
    return payload.data
  } catch (error) {
    if (!error.biz) {
      error.biz = true
      error.code = 503002
      error.message = '真实接口不可用，写操作禁止 mock 成功'
    }
    throw error
  } finally {
    clearTimeout(timer)
  }
}

export default requestMultipart
