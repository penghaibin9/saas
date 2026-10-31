let csrfToken = ''
export function setCsrfToken(value) { csrfToken = value || '' }
export async function request(path, { method = 'GET', body, params, timeoutMs = 30000, blob = false } = {}) {
  const url = new URL(`/api${path}`, window.location.origin)
  Object.entries(params || {}).forEach(([key, value]) => url.searchParams.set(key, value))
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const headers = { Accept: blob ? '*/*' : 'application/json' }
    if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json'
    if (method !== 'GET') headers['X-Website-CSRF'] = csrfToken
    const response = await fetch(url, { method, headers, credentials: 'same-origin', signal: controller.signal,
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined })
    if (blob && response.ok) return response.blob()
    const payload = await response.json().catch(() => ({}))
    if (!response.ok || payload.code !== 0) {
      if (response.status === 401) window.dispatchEvent(new Event('website-session-expired'))
      throw new Error(payload.message || '网站服务暂不可用，请稍后重试。')
    }
    return payload.data
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('请求超时，请刷新核对结果后再操作。')
    if (error.name === 'TypeError' || error.name === 'NetworkError') throw new Error('暂时无法连接官网服务，请检查网络后重新读取。')
    throw error
  } finally { clearTimeout(timeout) }
}
export const requestUpload = (path, file, field, options) => {
  const body = new FormData(); body.append(field, file)
  return request(path, { ...options, method: 'POST', body })
}
export const requestBlob = path => request(path, { blob: true })
