/** 家长门户独立请求层：不得覆盖学生 PC 门户 sp_token_v1。 */
const TOKEN_KEY = 'sp_guardian_v1'
const API_PREFIX = '/api/v1'

const API_BASE = (() => {
  const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}
  if (env.VITE_API_BASE_URL) return String(env.VITE_API_BASE_URL).replace(/\/+$/, '')
  if (env.DEV) return 'http://localhost:8000'
  return ''
})()

// 令牌存 sessionStorage 而非 localStorage：家长可能在公用电脑或孩子的电脑上登录，
// localStorage 关掉浏览器还在，等于把家长会话留在别人机器上。
// 迁移期兼容一次旧 localStorage 值，搬进 sessionStorage 后立刻删除旧值。
export function getGuardianToken() {
  try {
    const current = sessionStorage.getItem(TOKEN_KEY)
    if (current) return current
    const legacy = localStorage.getItem(TOKEN_KEY)
    if (legacy) {
      sessionStorage.setItem(TOKEN_KEY, legacy)
      localStorage.removeItem(TOKEN_KEY)
      return legacy
    }
  } catch { /* storage unavailable */ }
  return ''
}

export function setGuardianToken(token) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(TOKEN_KEY)   // 旧值不得残留在磁盘上
  } catch { /* storage unavailable */ }
}

export function clearGuardianSession() { setGuardianToken('') }

async function guardianRequest(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getGuardianToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`
  let response
  try {
    response = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
      method,
      headers,
      body: body == null ? undefined : JSON.stringify(body)
    })
  } catch {
    const error = new Error('网络不可达，请检查网络后重试')
    error.network = true
    throw error
  }
  let payload = null
  try { payload = await response.json() } catch { payload = null }
  if (response.status === 401) {
    clearGuardianSession()
    const error = new Error('家长登录已失效，请重新获取验证码')
    error.status = 401
    throw error
  }
  if (!payload || typeof payload.code !== 'number') {
    const error = new Error(`响应结构异常（HTTP ${response.status}）`)
    error.status = response.status
    throw error
  }
  if (payload.code !== 0) {
    const error = new Error(payload.message || `业务错误 ${payload.code}`)
    error.code = payload.code
    error.biz = true
    error.traceId = payload.traceId
    throw error
  }
  return payload.data
}

export const guardianApi = {
  getToken: getGuardianToken,
  clearSession: clearGuardianSession,
  requestOtp(phone) {
    return guardianRequest('/portal/guardian/otp', {
      method: 'POST', auth: false, body: { phone }
    })
  },
  async login(phone, code) {
    const data = await guardianRequest('/portal/guardian/login', {
      method: 'POST', auth: false, body: { phone, code }
    })
    const token = data?.accessToken || data?.token || ''
    if (!token) throw new Error('家长登录响应缺少访问令牌')
    setGuardianToken(token)
    return data
  },
  students() {
    return guardianRequest('/portal/guardian/students')
  },
  studentOverview(linkId) {
    return guardianRequest(`/portal/guardian/students/${encodeURIComponent(linkId)}/overview`)
  },
  consents() {
    return guardianRequest('/portal/guardian/internship/consents')
  },
  consentDetail(consentId, linkToken) {
    return guardianRequest(
      `/portal/guardian/internship/consents/${encodeURIComponent(consentId)}?token=${encodeURIComponent(linkToken)}`
    )
  },
  confirmConsent(consentId, body) {
    return guardianRequest(`/portal/guardian/internship/consents/${encodeURIComponent(consentId)}/confirm`, {
      method: 'POST', body
    })
  }
}

export default guardianApi
