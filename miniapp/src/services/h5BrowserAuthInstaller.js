/*
 * H5-only browser auth adapter.
 *
 * The mature uni request layer is shared by MP-WEIXIN and H5. Native miniapp keeps the existing
 * JSON refresh-token contract, while H5 must not persist bearer/refresh secrets in web storage.
 * This installer runs before App/session modules are evaluated and only patches the H5 runtime:
 *   - gx_token_v1 becomes memory-only;
 *   - gx_refresh_v1 is never stored/read as a secret (a non-secret sentinel keeps the existing
 *     single-flight refresh flow active after F5);
 *   - /auth/login|refresh|switch-role are transported through the existing per-tab HttpOnly
 *     browser endpoints;
 *   - explicit local token clearing revokes the browser cookie best-effort.
 */

const TOKEN_KEY = 'gx_token_v1'
const REFRESH_KEY = 'gx_refresh_v1'
const CHANNEL_KEY = 'gx_h5_browser_channel_v1'
const SESSION_ID_KEY = 'gx_h5_browser_session_id_v1'
const REFRESH_SENTINEL = '__HTTPONLY_BROWSER_REFRESH__'

const isH5 = typeof window !== 'undefined' && typeof document !== 'undefined' && typeof uni !== 'undefined'

if (isH5) {
  const originalGet = uni.getStorageSync.bind(uni)
  const originalSet = uni.setStorageSync.bind(uni)
  const originalRemove = uni.removeStorageSync?.bind(uni)
  const originalRequest = uni.request.bind(uni)

  let accessToken = ''
  let apiOrigin = ''

  function sessionGet(key) {
    try { return window.sessionStorage.getItem(key) || '' } catch { return '' }
  }
  function sessionSet(key, value) {
    try {
      if (value) window.sessionStorage.setItem(key, String(value))
      else window.sessionStorage.removeItem(key)
    } catch { /* non-secret browser coordination may fall back to memory */ }
  }
  function sessionId() {
    let value = sessionGet(SESSION_ID_KEY)
    if (!value) {
      value = globalThis.crypto?.randomUUID?.() || `h5-${Date.now()}-${Math.random()}`
      sessionSet(SESSION_ID_KEY, value)
    }
    return value
  }
  function channel() { return sessionGet(CHANNEL_KEY) }
  function browserHeaders(extra = {}) {
    const ch = channel()
    return {
      ...extra,
      ...(ch ? { 'X-Browser-Session': ch } : {}),
      'X-Browser-Session-Id': sessionId(),
    }
  }
  function rememberApiOrigin(url) {
    const text = String(url || '')
    const index = text.indexOf('/api/v1/')
    if (index >= 0) apiOrigin = text.slice(0, index)
  }
  function authUrl(path) { return `${apiOrigin}/api/v1${path}` }
  function rewriteAuthUrl(url) {
    const text = String(url || '')
    return text
      .replace(/\/api\/v1\/auth\/login(?=$|\?)/, '/api/v1/auth/browser-login')
      .replace(/\/api\/v1\/auth\/refresh(?=$|\?)/, '/api/v1/auth/browser-refresh')
      .replace(/\/api\/v1\/auth\/switch-role(?=$|\?)/, '/api/v1/auth/browser-switch-role')
  }
  function revokeBrowserSession() {
    const ch = channel()
    if (!ch) return
    const token = accessToken
    const sid = sessionId()
    try {
      originalRequest({
        url: authUrl('/auth/browser-logout'),
        method: 'POST',
        data: {},
        header: {
          'Content-Type': 'application/json',
          'X-Browser-Session': ch,
          'X-Browser-Session-Id': sid,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        withCredentials: true,
        timeout: 5000,
        complete: () => {},
      })
    } catch { /* local logout still proceeds */ }
    sessionSet(CHANNEL_KEY, '')
    sessionSet(SESSION_ID_KEY, '')
  }

  // Purge credentials written by older H5 builds before installing memory-only storage semantics.
  try { originalRemove?.(TOKEN_KEY); originalRemove?.(REFRESH_KEY) } catch { /* ignore */ }
  try { window.localStorage.removeItem(TOKEN_KEY); window.localStorage.removeItem(REFRESH_KEY) } catch { /* ignore */ }
  try { window.sessionStorage.removeItem(TOKEN_KEY); window.sessionStorage.removeItem(REFRESH_KEY) } catch { /* ignore */ }

  uni.getStorageSync = (key) => {
    if (key === TOKEN_KEY) return accessToken
    if (key === REFRESH_KEY) return channel() ? REFRESH_SENTINEL : ''
    return originalGet(key)
  }

  uni.setStorageSync = (key, value) => {
    if (key === TOKEN_KEY) {
      const next = String(value || '')
      if (!next && (accessToken || channel())) revokeBrowserSession()
      accessToken = next
      return
    }
    if (key === REFRESH_KEY) {
      // HttpOnly refresh credentials are intentionally never copied into browser-readable storage.
      return
    }
    return originalSet(key, value)
  }

  if (originalRemove) {
    uni.removeStorageSync = (key) => {
      if (key === TOKEN_KEY) {
        if (accessToken || channel()) revokeBrowserSession()
        accessToken = ''
        return
      }
      if (key === REFRESH_KEY) return
      return originalRemove(key)
    }
  }

  uni.request = (options = {}) => {
    const next = { ...options, header: { ...(options.header || {}) } }
    rememberApiOrigin(next.url)
    const originalUrl = String(next.url || '')
    const isLogin = /\/api\/v1\/auth\/login(?:\?|$)/.test(originalUrl)
    const isCaptcha = /\/api\/v1\/auth\/captcha(?:\?|$)/.test(originalUrl)
    const isRefresh = /\/api\/v1\/auth\/refresh(?:\?|$)/.test(originalUrl)
    const isSwitch = /\/api\/v1\/auth\/switch-role(?:\?|$)/.test(originalUrl)
    if (isCaptcha) {
      const clientType = String(next.data?.clientType || '').toUpperCase()
      const scene = String(next.data?.scene || '').toUpperCase()
      // Password-login CAPTCHA is bound to clientType by the backend. H5 student account login is
      // transported as STUDENT_PC below, so issue that exact challenge contract too. WX_BIND stays
      // STUDENT_MINI because its native binding endpoint is not rewritten to browser-login.
      if (scene === 'PASSWORD_LOGIN' && clientType === 'STUDENT_MINI') {
        next.data = { ...(next.data || {}), clientType: 'STUDENT_PC' }
      }
    }
    if (isLogin) {
      const clientType = String(next.data?.clientType || '').toUpperCase()
      const ch = clientType === 'STUDENT_MINI' || clientType === 'STUDENT_PC' ? 'student' : 'staff'
      sessionSet(CHANNEL_KEY, ch)
      sessionId()
      if (clientType === 'STUDENT_MINI') next.data = { ...(next.data || {}), clientType: 'STUDENT_PC' }
    }
    if (isLogin || isRefresh || isSwitch) {
      next.url = rewriteAuthUrl(originalUrl)
      next.header = browserHeaders(next.header)
      next.withCredentials = true
      if (isRefresh) next.data = {}
    } else {
      // Same-origin production is standard, but keep browser cookies available when an operator
      // intentionally deploys the API on another allowed HTTPS origin.
      next.withCredentials = true
    }
    return originalRequest(next)
  }
}

export const H5_BROWSER_AUTH_INSTALLED = isH5
