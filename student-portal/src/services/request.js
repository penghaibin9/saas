/**
 * 学生 PC 门户 · 统一请求层。
 * - SECURITY-P0：accessToken 只驻留内存；refreshToken 仅 HttpOnly+SameSite Cookie。
 * - 学生 PC 固定使用独立 student browser session，不与教师/平台 PC 共用 refresh Cookie。
 * - API base 可配置：VITE_API_BASE_URL（源，勿带 /api），默认开发 localhost:8000 / 生产同源。
 * - 401 单飞 browser-refresh 并重试一次；刷新失败才清当前会话。
 * - 迟到的旧 refresh/401/业务响应不得覆盖、清空或借用已经切换的新会话。
 * - /auth/me 是唯一允许“无内存 token → HttpOnly refresh → 恢复会话”的 auth 读入口。
 * - 绝不调用 /auth/mock-login，绝不免密。
 */
const TOKEN_KEY = 'sp_token_v1'
const REFRESH_KEY = 'sp_refresh_v1'
const INTERNSHIP_BATCH_KEY = 'student_portal_internship_batch_v1'
const GD_TEMP_FILES_KEY = 'sp_gd_temp_files_v1'
const API_PREFIX = '/api/v1'
const BROWSER_SESSION_HEADERS = { 'X-Browser-Session': 'student' }

const API_BASE = (() => {
  const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}
  if (env.VITE_API_BASE_URL) return String(env.VITE_API_BASE_URL).replace(/\/+$/, '')
  if (env.DEV) return 'http://localhost:8000'
  return '' // 生产同源：/api/v1 由 Nginx 反代
})()

let accessToken = ''
let sessionGeneration = 0

for (const key of [TOKEN_KEY, REFRESH_KEY]) {
  try { sessionStorage.removeItem(key); localStorage.removeItem(key) } catch { /* ignore */ }
}

function _sessionGet(key) {
  try { return sessionStorage.getItem(key) || '' } catch { return '' }
}
function _sessionSet(key, value) {
  try {
    if (value) sessionStorage.setItem(key, value)
    else sessionStorage.removeItem(key)
  } catch { /* ignore */ }
}

function _replaceAccessToken(token) {
  accessToken = token || ''
}

function _advanceSession(token) {
  sessionGeneration += 1
  _replaceAccessToken(token)
}

function _invalidateIfCurrent(tokenAtStart) {
  if (accessToken !== tokenAtStart) return false
  sessionGeneration += 1
  _replaceAccessToken('')
  return true
}

function staleSessionError() {
  const e = new Error('登录会话已发生变化，旧请求已停止')
  e.code = 'SESSION_CHANGED'
  e.bizCode = 'SESSION_CHANGED'
  e.biz = true
  e.staleSession = true
  return e
}

export function getToken() {
  return accessToken
}
export function setToken(t) {
  _advanceSession(t || '')
}
export function getRefreshToken() {
  return ''
}
export function setRefreshToken(_t) {}
export function clearSession() {
  _advanceSession('')
  for (const key of [TOKEN_KEY, REFRESH_KEY, INTERNSHIP_BATCH_KEY, GD_TEMP_FILES_KEY]) {
    try { sessionStorage.removeItem(key); localStorage.removeItem(key) } catch { /* ignore */ }
  }
}

function readTempFiles() {
  try { return JSON.parse(_sessionGet(GD_TEMP_FILES_KEY) || '{}') || {} } catch { return {} }
}
function writeTempFiles(value) {
  _sessionSet(GD_TEMP_FILES_KEY, JSON.stringify(value || {}))
}
function rememberTempFile(fileId) {
  if (!fileId) return
  const value = readTempFiles()
  value[String(fileId)] = Date.now()
  writeTempFiles(value)
}
function markTempFilesBound(fileIds) {
  const ids = new Set((fileIds || []).map(String))
  if (!ids.size) return
  const value = readTempFiles()
  ids.forEach((id) => delete value[id])
  writeTempFiles(value)
}

export async function abandonTemporaryGraduationMaterial(fileId) {
  if (!fileId) return null
  const data = await request(`/portal/graduation/materials/${fileId}/abandon`, { method: 'POST' })
  const value = readTempFiles()
  delete value[String(fileId)]
  writeTempFiles(value)
  return data
}

let cleanupStarted = false
function cleanupStaleGraduationTemps() {
  if (cleanupStarted) return
  cleanupStarted = true
  const now = Date.now()
  const cutoff = 24 * 60 * 60 * 1000
  const value = readTempFiles()
  Object.entries(value).forEach(([fileId, at]) => {
    if (now - Number(at || 0) < cutoff) return
    abandonTemporaryGraduationMaterial(fileId).catch(() => { /* 已绑定文件会 409 */ })
  })
}

function selectedInternshipBatch(path) {
  if (!String(path || '').startsWith('/portal/internship')) return ''
  try {
    const value = String(_sessionGet(INTERNSHIP_BATCH_KEY) || '').trim()
    return /^\d+$/.test(value) ? value : ''
  } catch { return '' }
}

function addInternshipBatchHeader(headers, path) {
  const batchId = selectedInternshipBatch(path)
  if (batchId) headers['X-Internship-Batch-Id'] = batchId
}

function addBrowserSessionHeader(headers, path) {
  if (String(path || '').startsWith('/auth/browser-')) {
    headers['X-Browser-Session'] = BROWSER_SESSION_HEADERS['X-Browser-Session']
  }
}

function withQuery(path, params) {
  const entries = Object.entries(params || {}).filter(([, value]) => value !== undefined && value !== null && value !== '')
  if (!entries.length) return path
  const query = new URLSearchParams()
  for (const [key, value] of entries) {
    if (Array.isArray(value)) value.forEach((item) => query.append(key, String(item)))
    else query.append(key, String(value))
  }
  return `${path}${path.includes('?') ? '&' : '?'}${query.toString()}`
}

function authError(message = '登录已失效，请重新登录', payload = null, status = 401) {
  const e = new Error(message)
  e.status = status
  e.code = 401001
  e.biz = true
  if (payload && typeof payload === 'object') {
    e.bizCode = payload.bizCode
    e.details = payload.details
    e.traceId = payload.traceId
    e.decisionTrace = payload.decisionTrace
  }
  return e
}

async function responseJson(res) {
  try { return await res.json() } catch { return null }
}

let refreshing = null
async function refreshOnce() {
  if (refreshing) return refreshing
  const generationAtStart = sessionGeneration
  const accessTokenAtStart = accessToken
  refreshing = (async () => {
    let res
    try {
      res = await fetch(`${API_BASE}${API_PREFIX}/auth/browser-refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...BROWSER_SESSION_HEADERS },
        credentials: 'same-origin'
      })
    } catch {
      const e = new Error('网络不可达，请检查后端服务')
      e.network = true
      throw e
    }
    const payload = await responseJson(res)
    if (!payload || typeof payload.code !== 'number' || res.status === 401 || payload.code !== 0) {
      throw authError((payload && payload.message) || '登录已失效，请重新登录')
    }
    const data = payload.data || {}
    if (!data.accessToken) throw authError()
    if (sessionGeneration !== generationAtStart || accessToken !== accessTokenAtStart) {
      throw staleSessionError()
    }
    _replaceAccessToken(data.accessToken)
    return data.accessToken
  })()
    .catch((e) => {
      if (!e.staleSession && sessionGeneration === generationAtStart && accessToken === accessTokenAtStart) {
        _invalidateIfCurrent(accessTokenAtStart)
      }
      throw e
    })
    .finally(() => { refreshing = null })
  return refreshing
}

function isUnauthorized(res, payload) {
  return res.status === 401 || (payload && payload.code === 401001)
}

function browserAuthPath(path) {
  return path === '/auth/login' ? '/auth/browser-login' : path
}

function browserAuthBody(path, body) {
  const studentPcAuthPaths = new Set([
    '/auth/login',
    '/auth/captcha',
    '/auth/password-reset/request',
    '/auth/password-reset/verify'
  ])
  if (!studentPcAuthPaths.has(path)) return body
  return { ...(body || {}), clientType: 'STUDENT_PC' }
}

export async function request(path, {
  method = 'GET', body, auth = true, params, query, _retried = false
} = {}) {
  // F5 后 accessToken 为空；只允许 /auth/me 先走一次 HttpOnly cookie refresh。
  // 登录、验证码、找回密码等其它 auth 端点永远不触发隐式 refresh。
  if (auth && !_retried && path === '/auth/me' && !getToken()) {
    await refreshOnce()
    return request(path, { method, body, auth, params, query, _retried: true })
  }

  cleanupStaleGraduationTemps()
  const generationAtStart = sessionGeneration
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`
  addInternshipBatchHeader(headers, path)
  addBrowserSessionHeader(headers, path)
  const requestPath = withQuery(browserAuthPath(path), params || query)
  const requestBody = browserAuthBody(path, body)
  let res
  try {
    res = await fetch(`${API_BASE}${API_PREFIX}${requestPath}`, {
      method,
      headers,
      body: requestBody ? JSON.stringify(requestBody) : undefined,
      credentials: 'same-origin'
    })
  } catch {
    const e = new Error('网络不可达，请检查后端服务'); e.network = true; throw e
  }
  const payload = await responseJson(res)
  if (auth && sessionGeneration !== generationAtStart) throw staleSessionError()
  if (isUnauthorized(res, payload)) {
    if (auth && !_retried && !path.startsWith('/auth/')) {
      // 同一逻辑学生会话内的并发请求可能已经完成 refresh；允许同身份 token 重试。
      if (accessToken && accessToken !== token) {
        return request(path, { method, body, auth, params, query, _retried: true })
      }
      await refreshOnce()
      if (sessionGeneration !== generationAtStart) throw staleSessionError()
      return request(path, { method, body, auth, params, query, _retried: true })
    }
    if (auth) _invalidateIfCurrent(token)
    throw authError((payload && payload.message) || undefined, payload, res.status)
  }
  if (!payload || typeof payload.code !== 'number') {
    const e = new Error(`响应结构异常（HTTP ${res.status}）`); e.status = res.status; throw e
  }
  if (payload.code !== 0) {
    const e = new Error(payload.message || `业务错误 ${payload.code}`)
    e.code = payload.code
    e.biz = true
    e.bizCode = payload.bizCode
    e.details = payload.details
    e.traceId = payload.traceId
    e.decisionTrace = payload.decisionTrace
    throw e
  }
  const cleanPath = String(path || '').split('?')[0]
  if (method === 'POST' && ['/portal/graduation/proposal', '/portal/graduation/final'].includes(cleanPath)) {
    markTempFilesBound(body && body.attachments)
  }
  return payload.data
}

export async function uploadFile(path, file, { auth = true, _retried = false } = {}) {
  cleanupStaleGraduationTemps()
  const generationAtStart = sessionGeneration
  const headers = {}
  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`
  addInternshipBatchHeader(headers, path)
  const form = new FormData()
  form.append('file', file)
  let res
  try {
    res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
      method: 'POST', headers, body: form, credentials: 'same-origin'
    })
  } catch {
    const e = new Error('网络不可达，请检查后端服务'); e.network = true; throw e
  }
  const payload = await responseJson(res)
  if (auth && sessionGeneration !== generationAtStart) throw staleSessionError()
  if (isUnauthorized(res, payload)) {
    if (auth && !_retried) {
      if (accessToken && accessToken !== token) {
        return uploadFile(path, file, { auth, _retried: true })
      }
      await refreshOnce()
      if (sessionGeneration !== generationAtStart) throw staleSessionError()
      return uploadFile(path, file, { auth, _retried: true })
    }
    if (auth) _invalidateIfCurrent(token)
    throw authError((payload && payload.message) || undefined)
  }
  if (!payload || typeof payload.code !== 'number') {
    const e = new Error(`响应结构异常（HTTP ${res.status}）`); e.status = res.status; throw e
  }
  if (payload.code !== 0) {
    const e = new Error(payload.message || `业务错误 ${payload.code}`); e.code = payload.code; e.biz = true; throw e
  }
  if (String(path).includes('bizType=GRADUATION_MATERIAL') && payload.data?.fileId) {
    rememberTempFile(payload.data.fileId)
  }
  return payload.data
}

export async function downloadFile(path, fallbackName = '毕业设计材料', _retried = false) {
  const generationAtStart = sessionGeneration
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  addInternshipBatchHeader(headers, path)
  let res
  try {
    res = await fetch(`${API_BASE}${API_PREFIX}${path}`, { headers, credentials: 'same-origin' })
  } catch {
    const e = new Error('网络不可达，请检查后端服务'); e.network = true; throw e
  }
  if (sessionGeneration !== generationAtStart) throw staleSessionError()
  if (res.status === 401) {
    if (!_retried) {
      if (accessToken && accessToken !== token) return downloadFile(path, fallbackName, true)
      await refreshOnce()
      if (sessionGeneration !== generationAtStart) throw staleSessionError()
      return downloadFile(path, fallbackName, true)
    }
    _invalidateIfCurrent(token)
    throw authError()
  }
  if (!res.ok) {
    const e = new Error('材料下载失败或你已无权访问'); e.status = res.status; throw e
  }
  const blob = await res.blob()
  if (sessionGeneration !== generationAtStart) throw staleSessionError()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fallbackName
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
