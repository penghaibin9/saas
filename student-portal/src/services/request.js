/**
 * 学生 PC 门户 · 统一请求层。
 * - token 独立 key：sp_token_v1（不碰 miniapp / frontend 管理端的 token）。
 * - API base 可配置：VITE_API_BASE_URL（源，勿带 /api），默认开发 localhost:8000 / 生产同源。
 * - 绝不调用 /auth/mock-login，绝不免密。
 */
import {
  clearGraduationSection,
  failGraduationSection,
  graduationSectionForPath
} from '@/stores/graduationHealth'

const TOKEN_KEY = 'sp_token_v1'
const REFRESH_KEY = 'sp_refresh_v1'
const GD_TEMP_FILES_KEY = 'sp_gd_temp_files_v1'
const API_PREFIX = '/api/v1'

const API_BASE = (() => {
  const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}
  if (env.VITE_API_BASE_URL) return String(env.VITE_API_BASE_URL).replace(/\/+$/, '')
  if (env.DEV) return 'http://localhost:8000'
  return ''
})()

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) || '' } catch { return '' }
}
export function setToken(t) {
  try { localStorage.setItem(TOKEN_KEY, t || '') } catch { /* ignore */ }
}
export function setRefreshToken(t) {
  try { localStorage.setItem(REFRESH_KEY, t || '') } catch { /* ignore */ }
}
export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(GD_TEMP_FILES_KEY)
  } catch { /* ignore */ }
}

function readTempFiles() {
  try { return JSON.parse(localStorage.getItem(GD_TEMP_FILES_KEY) || '{}') || {} } catch { return {} }
}
function writeTempFiles(value) {
  try { localStorage.setItem(GD_TEMP_FILES_KEY, JSON.stringify(value || {})) } catch { /* ignore */ }
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
    abandonTemporaryGraduationMaterial(fileId).catch(() => { /* 已绑定文件会 409，保留登记供后续核对 */ })
  })
}

export async function request(path, { method = 'GET', body, auth = true } = {}) {
  cleanupStaleGraduationTemps()
  const section = method === 'GET' ? graduationSectionForPath(path) : ''
  if (section) clearGraduationSection(section)
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`
  let res
  try {
    res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
      method, headers, body: body ? JSON.stringify(body) : undefined
    })
  } catch (netErr) {
    const e = new Error('网络不可达，请检查后端服务'); e.network = true
    if (section) failGraduationSection(section, e.message)
    throw e
  }
  let payload = null
  try { payload = await res.json() } catch { payload = null }
  if (res.status === 401) {
    clearSession()
    const e = new Error('登录已失效，请重新登录'); e.status = 401
    if (section) failGraduationSection(section, e.message)
    throw e
  }
  if (!payload || typeof payload.code !== 'number') {
    const e = new Error(`响应结构异常（HTTP ${res.status}）`); e.status = res.status
    if (section) failGraduationSection(section, e.message)
    throw e
  }
  if (payload.code !== 0) {
    const e = new Error(payload.message || `业务错误 ${payload.code}`); e.code = payload.code; e.biz = true
    if (section) failGraduationSection(section, e.message)
    throw e
  }
  const cleanPath = String(path || '').split('?')[0]
  if (method === 'POST' && ['/portal/graduation/proposal', '/portal/graduation/final'].includes(cleanPath)) {
    markTempFilesBound(body && body.attachments)
  }
  return payload.data
}

/**
 * 学生门户的文件上传：仅用于先上传、再把 fileId 交给具体业务接口的两步流程。
 * 不给调用方暴露后台接口，也不把文件内容混入普通 JSON 请求。
 */
export async function uploadFile(path, file, { auth = true } = {}) {
  cleanupStaleGraduationTemps()
  const headers = {}
  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`
  const form = new FormData()
  form.append('file', file)
  let res
  try {
    res = await fetch(`${API_BASE}${API_PREFIX}${path}`, { method: 'POST', headers, body: form })
  } catch (netErr) {
    const e = new Error('网络不可达，请检查后端服务'); e.network = true; throw e
  }
  let payload = null
  try { payload = await res.json() } catch { payload = null }
  if (res.status === 401) { clearSession(); const e = new Error('登录已失效，请重新登录'); e.status = 401; throw e }
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

/** 下载受业务关系保护的文件；以 Bearer token 取回 blob，避免把令牌拼进 URL。 */
export async function downloadFile(path, fallbackName = '毕业设计材料') {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let res
  try {
    res = await fetch(`${API_BASE}${API_PREFIX}${path}`, { headers })
  } catch (netErr) {
    const e = new Error('网络不可达，请检查后端服务'); e.network = true; throw e
  }
  if (res.status === 401) { clearSession(); const e = new Error('登录已失效，请重新登录'); e.status = 401; throw e }
  if (!res.ok) {
    const e = new Error('材料下载失败或你已无权访问'); e.status = res.status; throw e
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fallbackName
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
