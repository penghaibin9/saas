const API_BASE = (() => {
  const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}
  if (env.VITE_API_BASE_URL) return String(env.VITE_API_BASE_URL).replace(/\/+$/, '')
  if (env.DEV) return 'http://localhost:8000'
  return ''
})()
const API_PREFIX = '/api/v1'
let accessToken = ''

export function setAccessToken(token){ accessToken = String(token || '') }
export function clearAccessToken(){ accessToken = '' }

export async function request(path,{method='GET',body,params,auth=true}={}){
  const query = new URLSearchParams()
  Object.entries(params || {}).forEach(([key,value]) => {
    if (value === undefined || value === null || value === '') return
    if (Array.isArray(value)) value.forEach(item => query.append(key,String(item)))
    else query.set(key,String(value))
  })
  const suffix = query.size ? `${path.includes('?') ? '&' : '?'}${query.toString()}` : ''
  const headers = {'Content-Type':'application/json','X-Browser-Session':'enterprise'}
  if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`
  let response
  try {
    response = await fetch(`${API_BASE}${API_PREFIX}${path}${suffix}`, {
      method, headers, credentials:'include', body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    const error = new Error('网络不可达，请检查企业协同后端服务')
    error.network = true
    throw error
  }
  let payload = null
  try { payload = await response.json() } catch { /* fail below */ }
  if (!payload || typeof payload.code !== 'number') {
    const error = new Error(`响应结构异常（HTTP ${response.status}）`)
    error.status = response.status
    throw error
  }
  if (response.status === 401 || payload.code === 401001) {
    clearAccessToken()
    const error = new Error(payload.message || '企业登录已失效，请重新登录')
    error.status = 401
    throw error
  }
  if (payload.code !== 0) {
    const error = new Error(payload.message || `业务错误 ${payload.code}`)
    error.status = response.status
    error.code = payload.code
    error.bizCode = payload.bizCode
    error.details = payload.details
    throw error
  }
  return payload.data
}
