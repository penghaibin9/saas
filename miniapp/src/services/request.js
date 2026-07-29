/**
 * 统一请求封装（P10：上线质量收口版）
 * ------------------------------------------------------------
 * - realRequest()：uni.request 调后端，解析统一响应 {code,bizCode,message,data,traceId}。
 * - realUpload()/realDownload()：文件上传下载沿用同一 token 与 401 单飞刷新。
 * - 401 刷新单飞：多接口同时 401 只发一次 /auth/refresh，其余排队等结果。
 * - refresh 失败：清 token 并跳转登录页（不再进入奇怪状态）。
 * - realFirst / realFirstStrict：读接口仅网络失败才回退 mock；
 *   业务错误（403/409/422/404）一律透出，绝不假装成功。
 * - safeToast：同文案 2.5s 内不重复弹，错误不刷屏。
 * - createSubmitLock：写操作提交锁，快速连点不重复提交。
 * - 日志绝不输出 token / 手机号 / 身份证。
 */
import { ENV } from '@/config/env'
import { markMobileViewsDirty } from '@/utils/viewFreshness'

const TOKEN_KEY = 'gx_token_v1'
const REFRESH_KEY = 'gx_refresh_v1'
const INTERNSHIP_BATCH_KEY = 'gx_student_internship_batch_v1'
const GD_TEACHER_BATCH_KEY = 'gx_gd_teacher_batch_v1'
const state = { offlineUntil: 0, warned: false }

export function setToken(token) {
  try { uni.setStorageSync(TOKEN_KEY, token || '') } catch (e) { /* 忽略存储失败 */ }
}

export function getToken() {
  try { return uni.getStorageSync(TOKEN_KEY) || '' } catch (e) { return '' }
}

export function setRefreshToken(token) {
  try { uni.setStorageSync(REFRESH_KEY, token || '') } catch (e) { /* 忽略存储失败 */ }
}

export function getRefreshToken() {
  try { return uni.getStorageSync(REFRESH_KEY) || '' } catch (e) { return '' }
}

/** 教师小程序当前毕业设计批次。对象形状：{ id, name, status }。 */
export function setTeacherGraduationBatch(batch) {
  try {
    const value = batch && batch.id
      ? { id: String(batch.id), name: batch.name || batch.batchName || '', status: batch.status || '' }
      : null
    if (value) uni.setStorageSync(GD_TEACHER_BATCH_KEY, value)
    else uni.removeStorageSync(GD_TEACHER_BATCH_KEY)
  } catch (e) { /* 忽略本地缓存失败 */ }
}

export function getTeacherGraduationBatch() {
  try {
    const value = uni.getStorageSync(GD_TEACHER_BATCH_KEY)
    return value && value.id ? value : null
  } catch (e) { return null }
}


export function clearTokens() {
  setToken('')
  setRefreshToken('')
  setTeacherGraduationBatch(null)
}

export function shouldTryReal() {
  return !ENV.useMock && Date.now() >= state.offlineUntil
}

function markOffline() {
  state.offlineUntil = Date.now() + 15000
  if (!state.warned) {
    state.warned = true
    safeToast(ENV.allowMockFallback
      ? '网络不稳定，开发演示数据可能不是最新'
      : '网络不稳定，请检查网络后重试', 'none')
  }
}

/* ── 错误分类 ── */
export function isBusinessError(e) {
  return !!(e && e.biz)
}

export function isNetworkError(e) {
  return !!(e && (e.code === 'NETWORK' || e.code === 'BAD_RESPONSE'))
}

export function normalizeError(e) {
  const code = e && e.code
  if (isNetworkError(e)) return { kind: 'network', text: '网络异常，请检查网络后重试' }
  if (code === 401001) return { kind: 'auth', text: '登录已失效，请重新登录' }
  if (code === 403001 || code === 403002) return { kind: 'forbidden', text: (e && e.message) || '没有权限执行该操作' }
  if (code === 404001) return { kind: 'notfound', text: (e && e.message) || '数据不存在或已变更' }
  if (code === 409001) return { kind: 'conflict', text: (e && e.message) || '重复提交或状态已变化，请刷新后再试' }
  if (code === 422001 || code === 400001) return { kind: 'invalid', text: (e && e.message) || '填写内容有误，请检查后重试' }
  if (code === 429001) return { kind: 'ratelimit', text: (e && e.message) || '操作过于频繁，请稍后再试' }
  return { kind: 'unknown', text: (e && e.message) || '操作失败，请稍后重试' }
}

/* ── 防刷屏 toast ── */
const _toastState = { last: '', at: 0 }
export function safeToast(title, icon = 'none') {
  try {
    const now = Date.now()
    if (title === _toastState.last && now - _toastState.at < 2500) return
    _toastState.last = title
    _toastState.at = now
    uni.showToast({ title, icon, duration: 2200 })
  } catch (e) { /* 忽略 */ }
}

export function toastError(e) {
  safeToast(normalizeError(e).text, 'none')
}

/* ── 提交锁：同一个写操作短时间不能重复提交 ── */
export function createSubmitLock(cooldownMs = 1200) {
  let busy = false
  let lastAt = 0
  return {
    get busy() { return busy },
    async run(fn) {
      const now = Date.now()
      if (busy || now - lastAt < cooldownMs) {
        return Promise.reject({ code: 'LOCKED', message: '正在提交，请勿重复点击' })
      }
      busy = true
      lastAt = now
      try {
        return await fn()
      } finally {
        busy = false
      }
    }
  }
}

/* ── 未登录/会话失效 → 跳登录 ── */
let _redirecting = false
export function requireAuthOrRedirect(message = '登录已失效，请重新登录') {
  clearTokens()
  if (_redirecting) return
  _redirecting = true
  safeToast(message, 'none')
  setTimeout(() => {
    try { uni.reLaunch({ url: '/pages/login/index' }) } catch (e) { /* 忽略 */ }
    _redirecting = false
  }, 600)
}

/** 模拟一次数据请求。fail=true 时用于演示 error 态。 */
export function mockRequest(payload, { latency = ENV.mockLatency, fail = false } = {}) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (fail) {
        reject({ code: 'MOCK_ERROR', message: '数据加载失败' })
      } else {
        resolve(JSON.parse(JSON.stringify(payload)))
      }
    }, latency)
  })
}

/* ── 401 刷新单飞队列 ── */
let _refreshing = null
function _refreshOnce() {
  if (_refreshing) return _refreshing
  const rt = getRefreshToken()
  if (!rt) {
    return Promise.reject({ code: 401001, biz: true, message: '未登录' })
  }
  _refreshing = realRequest('/auth/refresh', { method: 'POST', auth: false, data: { refreshToken: rt } })
    .then((d) => {
      setToken(d.accessToken)
      setRefreshToken(d.refreshToken || '')
      return d.accessToken
    })
    .catch((e) => {
      requireAuthOrRedirect()
      throw e
    })
    .finally(() => { _refreshing = null })
  return _refreshing
}

function selectedInternshipBatchId(path) {
  if (!String(path || '').startsWith('/mobile/internship')) return ''
  try {
    const value = String(uni.getStorageSync(INTERNSHIP_BATCH_KEY) || '').trim()
    return /^\d+$/.test(value) ? value : ''
  } catch (e) {
    return ''
  }
}

/* ── 教师毕业设计批次上下文与分页 ── */
const GD_TEACHER_PREFIX = '/mobile/teacher/graduation'
const GD_TASKBOOK_PATH = `${GD_TEACHER_PREFIX}/taskbooks`
const GD_TEACHER_PAGED_PATHS = new Set([
  GD_TEACHER_PREFIX,
  `${GD_TEACHER_PREFIX}/my-students`,
  `${GD_TEACHER_PREFIX}/midterm/queue`,
  `${GD_TEACHER_PREFIX}/reviews/my`,
  `${GD_TEACHER_PREFIX}/defense/arrangements`,
  `${GD_TEACHER_PREFIX}/grade/queue`,
  `${GD_TEACHER_PREFIX}/choices/pending`,
  `${GD_TEACHER_PREFIX}/change-requests/pending`,
  GD_TASKBOOK_PATH,
  `${GD_TEACHER_PREFIX}/defense/pending`
])
const GD_MAX_AUTO_PAGES = 20

function appendQuery(path, key, value) {
  if (new RegExp(`[?&]${key}=`).test(path)) return path
  return `${path}${path.includes('?') ? '&' : '?'}${key}=${encodeURIComponent(value)}`
}
function replaceQuery(path, key, value) {
  const re = new RegExp(`([?&])${key}=[^&]*`)
  if (re.test(path)) return path.replace(re, `$1${key}=${encodeURIComponent(value)}`)
  return appendQuery(path, key, value)
}
function withTeacherGraduationContext(path) {
  if (!path.startsWith(GD_TEACHER_PREFIX) || path.startsWith(`${GD_TEACHER_PREFIX}/batches`)) return path
  const batch = getTeacherGraduationBatch()
  if (!batch || !batch.id) throw { code: 422001, biz: true, message: '请先选择毕业设计批次' }
  let value = appendQuery(path, 'batchId', batch.id)
  const pathname = value.split('?')[0]
  if (GD_TEACHER_PAGED_PATHS.has(pathname)) {
    value = appendQuery(value, 'page', 1)
    value = appendQuery(value, 'pageSize', 100)
  }
  return value
}
function attachPageMeta(items, meta) {
  Object.defineProperty(items, '_pageMeta', { value: meta, enumerable: false, configurable: true })
  return items
}
function normalizeTeacherGraduationData(path, data) {
  const pathname = path.split('?')[0]
  if (pathname === GD_TASKBOOK_PATH && data && Array.isArray(data.items)) {
    return { list: data.items, total: data.total || data.items.length, page: data.page || 1,
      pageSize: data.pageSize || data.items.length, hasMore: !!data.hasMore, truncated: !!data.truncated }
  }
  if (GD_TEACHER_PAGED_PATHS.has(pathname) && pathname !== GD_TEACHER_PREFIX && data && Array.isArray(data.items)) {
    return attachPageMeta(data.items, { total: data.total || data.items.length, page: data.page || 1,
      pageSize: data.pageSize || data.items.length, hasMore: !!data.hasMore, truncated: !!data.truncated })
  }
  return data
}
async function collectTeacherGraduationPages(path, first, options) {
  // 移动列表只返回当前服务端页，禁止请求层静默循环抓取最多 20 页。
  // 需要更多数据的页面必须显式上拉并携带 page/pageSize。
  return normalizeTeacherGraduationData(path, first)
}


function parseUnifiedBody(raw) {
  if (raw && typeof raw === 'object') return raw
  try { return JSON.parse(String(raw || '')) } catch (e) { return null }
}

/* GET 请求单飞：相同身份、路径和查询在并发期间只发送一次。
 * 写操作不共享 Promise；完全相同的并发写请求会被明确拒绝，避免双击重复落库。 */
const _getInflight = new Map()
const _mutationInflight = new Set()

function stablePayload(value) {
  if (!value || typeof value !== 'object') return String(value || '')
  const out = {}
  Object.keys(value).sort().forEach((key) => { out[key] = value[key] })
  try { return JSON.stringify(out) } catch (e) { return '' }
}

function inflightKey(method, effectivePath, data, auth) {
  const identity = auth ? getToken() : 'public'
  return `${method}|${effectivePath}|${stablePayload(data)}|${identity}`
}

function executeRealRequest(path, effectivePath, {
  method, data, auth, _retried, _rawPage
}) {
  return new Promise((resolve, reject) => {
    const header = { 'Content-Type': 'application/json' }
    const token = auth ? getToken() : ''
    if (token) header.Authorization = 'Bearer ' + token
    const internshipBatchId = selectedInternshipBatchId(path)
    if (internshipBatchId) header['X-Internship-Batch-Id'] = internshipBatchId
    uni.request({
      url: ENV.apiBaseUrl + ENV.apiPrefix + effectivePath,
      method,
      data: data || {},
      header,
      timeout: ENV.requestTimeout,
      success: (res) => {
        const body = res.data
        if (!body || typeof body.code !== 'number') {
          markOffline()
          reject({ code: 'BAD_RESPONSE', message: '响应结构异常', httpStatus: res.statusCode })
          return
        }
        if (body.code !== 0) {
          if (body.code === 401001 && auth && !_retried && !path.startsWith('/auth/')) {
            _refreshOnce()
              .then(() => realRequest(path, { method, data, auth, _retried: true, _rawPage }))
              .then(resolve)
              .catch(reject)
            return
          }
          reject({
            code: body.code,
            biz: true,
            message: body.message || '业务错误',
            traceId: body.traceId,
            httpStatus: res.statusCode
          })
          return
        }
        state.warned = false
        if (method !== 'GET') markMobileViewsDirty(path)
        if (_rawPage || method !== 'GET') { resolve(body.data); return }
        collectTeacherGraduationPages(effectivePath, body.data, { method, data, auth, _retried })
          .then(resolve).catch(reject)
      },
      fail: (err) => {
        markOffline()
        reject({ code: 'NETWORK', message: (err && err.errMsg) || '网络异常' })
      }
    })
  })
}

/** 真实后端请求：返回统一响应的 data 字段；code!==0 抛业务错（e.biz=true） */
export function realRequest(path, {
  method = 'GET', data, auth = true, _retried = false, _rawPage = false
} = {}) {
  const normalizedMethod = String(method || 'GET').toUpperCase()
  let effectivePath
  try { effectivePath = withTeacherGraduationContext(path) } catch (e) { return Promise.reject(e) }

  // 401 刷新后的重试和内部显式分页必须绕过原单飞槽位，避免等待自身 Promise。
  if (_retried || _rawPage) {
    return executeRealRequest(path, effectivePath, {
      method: normalizedMethod, data, auth, _retried, _rawPage
    })
  }

  const key = inflightKey(normalizedMethod, effectivePath, data, auth)
  if (normalizedMethod === 'GET') {
    if (_getInflight.has(key)) return _getInflight.get(key)
    const pending = executeRealRequest(path, effectivePath, {
      method: normalizedMethod, data, auth, _retried, _rawPage
    }).finally(() => _getInflight.delete(key))
    _getInflight.set(key, pending)
    return pending
  }

  if (_mutationInflight.has(key)) {
    return Promise.reject({ code: 'LOCKED', biz: true, message: '正在提交，请勿重复点击' })
  }
  _mutationInflight.add(key)
  return executeRealRequest(path, effectivePath, {
    method: normalizedMethod, data, auth, _retried, _rawPage
  }).finally(() => _mutationInflight.delete(key))
}


/** 文件上传：使用真实 /files 两步式合同，401 后单飞刷新并仅重试一次。 */
export function realUpload(path, filePath, {
  name = 'file', formData = {}, auth = true, _retried = false
} = {}) {
  return new Promise((resolve, reject) => {
    if (!filePath) {
      reject({ code: 422001, biz: true, message: '请选择要上传的文件' })
      return
    }
    const header = {}
    const token = auth ? getToken() : ''
    if (token) header.Authorization = 'Bearer ' + token
    uni.uploadFile({
      url: ENV.apiBaseUrl + ENV.apiPrefix + path,
      filePath,
      name,
      formData,
      header,
      timeout: Math.max(ENV.requestTimeout || 10000, 30000),
      success: (res) => {
        const body = parseUnifiedBody(res.data)
        if (!body || typeof body.code !== 'number') {
          reject({ code: 'BAD_RESPONSE', message: '上传响应结构异常' })
          return
        }
        if (body.code !== 0) {
          if (body.code === 401001 && auth && !_retried) {
            _refreshOnce()
              .then(() => realUpload(path, filePath, { name, formData, auth, _retried: true }))
              .then(resolve)
              .catch(reject)
            return
          }
          reject({ code: body.code, biz: true, message: body.message || '上传失败', traceId: body.traceId })
          return
        }
        resolve(body.data)
      },
      fail: (err) => {
        markOffline()
        reject({ code: 'NETWORK', message: (err && err.errMsg) || '上传失败' })
      }
    })
  })
}

/** 文件下载：返回临时文件路径；401 后单飞刷新并仅重试一次。 */
export function realDownload(path, { auth = true, _retried = false } = {}) {
  return new Promise((resolve, reject) => {
    const header = {}
    const token = auth ? getToken() : ''
    if (token) header.Authorization = 'Bearer ' + token
    uni.downloadFile({
      url: ENV.apiBaseUrl + ENV.apiPrefix + path,
      header,
      timeout: Math.max(ENV.requestTimeout || 10000, 30000),
      success: (res) => {
        if (res.statusCode === 200 && res.tempFilePath) {
          resolve({ tempFilePath: res.tempFilePath })
          return
        }
        if (res.statusCode === 401 && auth && !_retried) {
          _refreshOnce()
            .then(() => realDownload(path, { auth, _retried: true }))
            .then(resolve)
            .catch(reject)
          return
        }
        reject({ code: res.statusCode === 403 ? 403001 : 404001, biz: true, message: '文件不存在或无权下载' })
      },
      fail: (err) => {
        markOffline()
        reject({ code: 'NETWORK', message: (err && err.errMsg) || '下载失败' })
      }
    })
  })
}

export function realFirst(label, realFn, mockFn) {
  if (!shouldTryReal()) {
    if (ENV.allowMockFallback && mockFn) return mockFn()
    return Promise.reject({ code: 'NETWORK', message: '真实接口不可用，生产环境已禁用 mock fallback' })
  }
  return realFn().catch((e) => {
    if (e && e.biz) throw e
    if (ENV.allowMockFallback && mockFn) return mockFn()
    throw e
  })
}

export function realFirstStrict(label, realFn, mockFn) {
  return realFirst(label, realFn, mockFn)
}

export function request(options) {
  return realRequest(options.url, { method: options.method, data: options.data })
}

export default {
  mockRequest, realRequest, realUpload, realDownload, realFirst, realFirstStrict, request,
  setToken, getToken, clearTokens, safeToast, toastError, normalizeError,
  createSubmitLock, requireAuthOrRedirect, isBusinessError, isNetworkError
}
