/**
 * 统一请求封装（P10：上线质量收口版）
 * ------------------------------------------------------------
 * - realRequest()：uni.request 调后端，解析统一响应 {code,bizCode,message,data,traceId,decisionTrace}。
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
import {
  advanceSessionGeneration, assertSessionSnapshot, captureSessionSnapshot,
  currentSessionGeneration, guardSessionPromise, isSessionSnapshotCurrent, sessionChangedError
} from './sessionGeneration.mjs'

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

export function commitNewSessionTokens(accessToken, refreshToken) {
  advanceSessionGeneration()
  setToken(accessToken || '')
  setRefreshToken(refreshToken || '')
  return currentSessionGeneration()
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
  advanceSessionGeneration()
  setToken('')
  setRefreshToken('')
  setTeacherGraduationBatch(null)
}

export function shouldTryReal() {
  // 仅演示回退使用冷却期；真实环境的重试必须重新访问服务端。
  return !ENV.useMock && (!ENV.allowMockFallback || Date.now() >= state.offlineUntil)
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

// 后端 message 仅能作为“可读业务提示”的候选值，绝不能把网关、堆栈、SQL、路径或令牌
// 原样塞进 toast / 空状态。业务详情页中的退回原因是独立字段，不走这里。
const UNSAFE_ERROR_TEXT = /(?:\r|\n|https?:\/\/|file:\/\/|[A-Za-z]:\\|\/(?:api|app|var|usr|home)\/|traceback|stack\s*trace|sql(?:alchemy|ite)?|mysql|postgres|exception|error\s*:|failed\s+to|econn|etimedout|<[^>]+>|token|authorization|bearer|password|secret)/i
const CJK_TEXT = /[\u3400-\u9fff]/
// 后端偶有把内部 reasonCode 与中文说明拼在同一 message；即使含中文，也不能让
// EVIDENCE_INVALIDATED 这类实现编号出现在学生页面。
const INTERNAL_ERROR_CODE_PREFIX = /(?:^|[\s（(])[A-Z][A-Z0-9_]{2,}\s*[:：]/

function safeBusinessMessage(message, fallback) {
  const text = String(message || '').trim().replace(/\s+/g, ' ')
  if (!text || text.length > 120 || !CJK_TEXT.test(text) || UNSAFE_ERROR_TEXT.test(text) || INTERNAL_ERROR_CODE_PREFIX.test(text)) return fallback
  return text
}

function safeMessageForCode(e, fallback) {
  // 只有明确的业务拒绝才允许保留经过筛选的中文说明；网络和未知异常一律走固定文案。
  return e?.biz ? safeBusinessMessage(e.message, fallback) : fallback
}

function requestErrorMessage(code, bizCode, message) {
  const error = { code, bizCode, biz: true, message }
  if (Number(code) === 400001 || Number(code) === 422001) return safeMessageForCode(error, '填写内容有误，请检查后重试')
  if (Number(code) === 409001) return safeMessageForCode(error, '当前记录已被处理或状态已变化，请刷新后核对')
  if (Number(code) === 404001) return '数据不存在或已变更'
  if (Number(code) === 429001) return '操作过于频繁，请稍后再试'
  if (Number(code) === 401001) return '登录已失效，请重新登录'
  if (Number(code) === 403001 || Number(code) === 403002) return '暂无访问权限，请联系学校管理员'
  return '服务暂时不可用，请稍后重试'
}

export function normalizeError(e) {
  const code = Number(e && e.code)
  const statuses = [e?.httpStatus, e?.status, e?.statusCode, e?.response?.status, code]
    .map(Number).filter(Number.isFinite).map(value => value >= 100000 ? Math.trunc(value / 1000) : value)
  if (statuses.some(value => value >= 500 && value < 600)) return { kind: 'unknown', pageState: 'error', text: '服务暂时不可用，请稍后重试' }
  if (isNetworkError(e)) return { kind: 'network', pageState: 'offline', text: '网络异常，请检查网络后重试' }
  if (statuses.includes(401) || statuses.includes(419)) return { kind: 'auth', pageState: 'unauthorized', text: '登录已失效，请重新登录' }
  if (statuses.includes(403) || ['NO_PERMISSION', 'NO_DATA_SCOPE', 'FORBIDDEN'].includes(e?.bizCode || e?.code)) {
    const noLicense = e?.bizCode === 'MODULE_NOT_AUTHORIZED' || e?.bizCode === 'MODULE_EXPIRED_READONLY' || /^模块未购买或未授权[：:]/.test(String(e?.message || ''))
    return { kind: 'forbidden', pageState: noLicense ? 'noLicense' : 'forbidden', text: noLicense ? '本校未开通该模块，请联系学校管理员' : '暂无访问权限，请联系学校管理员' }
  }
  if (code === 404001) return { kind: 'notfound', text: '数据不存在或已变更' }
  if (code === 409001) return { kind: 'conflict', text: safeMessageForCode(e, '重复提交或状态已变化，请刷新后再试') }
  if (code === 422001 || code === 400001) return { kind: 'invalid', text: safeMessageForCode(e, '填写内容有误，请检查后重试') }
  if (code === 429001) return { kind: 'ratelimit', text: '操作过于频繁，请稍后再试' }
  return { kind: 'unknown', pageState: 'error', text: '操作失败，请稍后重试' }
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

/* ── 未登录/会话失效 → 跳登录 ──
 * 只清 token 会残留 gx_session_v1 里的上一账号身份快照（姓名/学号/班级等），冷启动会先用
 * 旧身份渲染一瞬，业务草稿等会话态也不会被清理。stores/session.js 已导入本模块，若这里再
 * 反向导入 useSessionStore 会形成模块循环引用；改为登录态初始化时由 session store 反向
 * 注册一个"完整登出"回调，request.js 不感知 pinia store 的存在。 */
let _forceLogoutHandler = null
export function registerForceLogoutHandler(fn) { _forceLogoutHandler = fn }

let _redirecting = false
export function requireAuthOrRedirect(message = '登录已失效，请重新登录') {
  if (_forceLogoutHandler) {
    try { _forceLogoutHandler() } catch (e) { clearTokens() }
  } else {
    clearTokens()
  }
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
function _refreshOnce(expectedGeneration = currentSessionGeneration()) {
  if (_refreshing && _refreshing.generation === expectedGeneration) return _refreshing.promise
  if (currentSessionGeneration() !== expectedGeneration) return Promise.reject(sessionChangedError())
  const snapshot = captureSessionSnapshot(getToken(), getRefreshToken())
  if (!snapshot.refreshToken) {
    // A restored H5 tab can retain its page route while its per-tab browser
    // session (or refresh cookie) no longer exists. Do not leave that tab on a
    // generic “加载失败” view: clear the stale identity and return to the app
    // login surface just as a failed refresh would.
    const error = { code: 401001, biz: true, message: '登录已失效，请重新登录' }
    requireAuthOrRedirect(error.message)
    return Promise.reject(error)
  }
  const pending = guardSessionPromise(
    realRequest('/auth/refresh', {
      method: 'POST', auth: false, data: { refreshToken: snapshot.refreshToken }
    }),
    {
      snapshot,
      getAccessToken: getToken,
      getRefreshToken,
      onSuccess: (d) => {
        setToken(d.accessToken)
        setRefreshToken(d.refreshToken || '')
        return d.accessToken
      },
      onCurrentError: (e) => {
        requireAuthOrRedirect()
        throw e
      }
    }
  )
  const slot = { generation: expectedGeneration, promise: null }
  slot.promise = pending.finally(() => {
    if (_refreshing === slot) _refreshing = null
  })
  _refreshing = slot
  return slot.promise
}

function refreshOrReuseCurrentSession(requestSnapshot) {
  if (!requestSnapshot || currentSessionGeneration() !== requestSnapshot.generation) {
    return Promise.reject(sessionChangedError())
  }
  // 同一逻辑 generation 内，别的 401 可能已经完成 token 轮换。此时旧 token 的迟到 401
  // 不能被当作“换号登录”，也不需要再发第二次 refresh；直接让它使用当前 token 重试一次。
  if (!isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {
    return Promise.resolve(getToken())
  }
  return _refreshOnce(requestSnapshot.generation)
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
    // 移动端队列始终由页面显式续页；请求层不能把默认 100 条伪装成完整列表。
    value = appendQuery(value, 'pageSize', 20)
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

// uni.request 的 H5 适配层会把 GET data 中的 `undefined` 序列化成
// `?key=`。对于 FastAPI 的可选整数参数，这不等于“未传”，而是一个非法
// 空字符串（例如课表首次读取会变成 `?week=`）。只在查询参数层去掉
// undefined/null；空字符串仍按调用方原意传给服务端校验，写请求 body 也
// 不在这里改写。
function omitAbsentGetParams(data, method) {
  if (String(method || 'GET').toUpperCase() !== 'GET'
    || !data || typeof data !== 'object' || Array.isArray(data)) return data
  const normalized = {}
  Object.entries(data).forEach(([key, value]) => {
    if (value !== undefined && value !== null) normalized[key] = value
  })
  return normalized
}

function inflightKey(method, effectivePath, data, auth) {
  const identity = auth ? `${currentSessionGeneration()}|${getToken()}` : 'public'
  return `${method}|${effectivePath}|${stablePayload(data)}|${identity}`
}

function normalizeJsonResponseBody(value) {
  if (typeof value !== 'string') return value
  const text = value.trim()
  if (!text || (text[0] !== '{' && text[0] !== '[')) return value
  try { return JSON.parse(text) } catch { return value }
}

function executeRealRequest(path, effectivePath, {
  method, data, auth, _retried, _rawPage, _expectedGeneration, headers = {}
}) {
  if (auth && _expectedGeneration != null && currentSessionGeneration() !== _expectedGeneration) {
    return Promise.reject(sessionChangedError())
  }
  const requestSnapshot = auth ? captureSessionSnapshot(getToken(), getRefreshToken()) : null
  return new Promise((resolve, reject) => {
    const header = { 'Content-Type': 'application/json', ...headers }
    const token = requestSnapshot ? requestSnapshot.accessToken : ''
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
        // Some H5 adapters expose an application/json response as text while
        // native miniapp runtimes expose the parsed object. Normalize only
        // syntactically valid JSON; malformed/non-JSON bodies still fail closed.
        const body = normalizeJsonResponseBody(res.data)
        if (body && body.code === 401001 && auth && !_retried && path.split('?')[0] !== '/auth/refresh') {
          refreshOrReuseCurrentSession(requestSnapshot)
            .then(() => realRequest(path, {
              method, data, auth, _retried: true, _rawPage, headers,
              _expectedGeneration: requestSnapshot.generation
            }))
            .then(resolve)
            .catch(reject)
          return
        }
        if (requestSnapshot && !isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {
          reject(sessionChangedError())
          return
        }
        if (!body || typeof body.code !== 'number') {
          markOffline()
          reject({ code: 'BAD_RESPONSE', message: '响应结构异常', httpStatus: res.statusCode })
          return
        }
        if (body.code !== 0) {
          reject({
            code: body.code,
            biz: true,
            message: requestErrorMessage(body.code, body.bizCode, body.message),
            serverMessage: body.message || '',
            traceId: body.traceId,
            bizCode: body.bizCode,
            details: body.details,
            decisionTrace: body.decisionTrace,
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
        if (requestSnapshot && !isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {
          reject(sessionChangedError())
          return
        }
        markOffline()
        reject({ code: 'NETWORK', message: '网络异常，请检查网络后重试' })
      }
    })
  })
}

/** 真实后端请求：返回统一响应的 data 字段；code!==0 抛业务错（e.biz=true） */
export function realRequest(path, {
  method = 'GET', data, auth = true, _retried = false, _rawPage = false, _expectedGeneration = null, headers = {}
} = {}) {
  const normalizedMethod = String(method || 'GET').toUpperCase()
  const normalizedData = omitAbsentGetParams(data, normalizedMethod)
  // H5 access tokens intentionally live in memory only. After F5 the per-tab HttpOnly
  // refresh cookie is still valid, but there is no bearer token to attach to the first
  // business request. Restore the access token before that request instead of relying on
  // every runtime to surface a non-2xx response through uni.request's success callback.
  // /auth/me and role switching also need the restored identity after a direct F5.
  if (auth && !_retried && String(path || '').split('?')[0] !== '/auth/refresh' && !getToken() && getRefreshToken()) {
    const expectedGeneration = currentSessionGeneration()
    return _refreshOnce(expectedGeneration).then(() => realRequest(path, {
      method: normalizedMethod, data: normalizedData, auth, _retried: true, _rawPage, headers,
      _expectedGeneration: expectedGeneration
    }))
  }
  let effectivePath
  try { effectivePath = withTeacherGraduationContext(path) } catch (e) { return Promise.reject(e) }

  // 401 刷新后的重试和内部显式分页必须绕过原单飞槽位，避免等待自身 Promise。
  if (_retried || _rawPage) {
    return executeRealRequest(path, effectivePath, {
      method: normalizedMethod, data: normalizedData, auth, _retried, _rawPage, _expectedGeneration, headers
    })
  }

  const key = inflightKey(normalizedMethod, effectivePath, normalizedData, auth)
  if (normalizedMethod === 'GET') {
    if (_getInflight.has(key)) return _getInflight.get(key)
    const pending = executeRealRequest(path, effectivePath, {
      method: normalizedMethod, data: normalizedData, auth, _retried, _rawPage, _expectedGeneration, headers
    }).finally(() => _getInflight.delete(key))
    _getInflight.set(key, pending)
    return pending
  }

  if (_mutationInflight.has(key)) {
    return Promise.reject({ code: 'LOCKED', biz: true, message: '正在提交，请勿重复点击' })
  }
  _mutationInflight.add(key)
  return executeRealRequest(path, effectivePath, {
    method: normalizedMethod, data: normalizedData, auth, _retried, _rawPage, _expectedGeneration, headers
  }).finally(() => _mutationInflight.delete(key))
}


/** 文件上传：使用真实 /files 两步式合同，401 后单飞刷新并仅重试一次。 */
export function realUpload(path, filePath, {
  name = 'file', formData = {}, auth = true, _retried = false, _expectedGeneration = null
} = {}) {
  if (auth && _expectedGeneration != null && currentSessionGeneration() !== _expectedGeneration) {
    return Promise.reject(sessionChangedError())
  }
  const requestSnapshot = auth ? captureSessionSnapshot(getToken(), getRefreshToken()) : null
  return new Promise((resolve, reject) => {
    if (!filePath) {
      reject({ code: 422001, biz: true, message: '请选择要上传的文件' })
      return
    }
    const header = {}
    const token = requestSnapshot ? requestSnapshot.accessToken : ''
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
        if (body && body.code === 401001 && auth && !_retried) {
          refreshOrReuseCurrentSession(requestSnapshot)
            .then(() => realUpload(path, filePath, {
              name, formData, auth, _retried: true, _expectedGeneration: requestSnapshot.generation
            }))
            .then(resolve)
            .catch(reject)
          return
        }
        if (requestSnapshot && !isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {
          reject(sessionChangedError())
          return
        }
        if (!body || typeof body.code !== 'number') {
          reject({ code: 'BAD_RESPONSE', message: '上传响应结构异常' })
          return
        }
        if (body.code !== 0) {
          reject({
            code: body.code,
            biz: true,
            message: requestErrorMessage(body.code, body.bizCode, body.message),
            serverMessage: body.message || '',
            traceId: body.traceId,
            bizCode: body.bizCode
          })
          return
        }
        resolve(body.data)
      },
      fail: (err) => {
        if (requestSnapshot && !isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {
          reject(sessionChangedError())
          return
        }
        markOffline()
        reject({ code: 'NETWORK', message: '网络异常，附件上传未完成，请检查网络后重试' })
      }
    })
  })
}

/** 文件下载：返回临时文件路径；401 后单飞刷新并仅重试一次。 */
export function realDownload(path, { auth = true, _retried = false, _expectedGeneration = null } = {}) {
  if (auth && _expectedGeneration != null && currentSessionGeneration() !== _expectedGeneration) {
    return Promise.reject(sessionChangedError())
  }
  const requestSnapshot = auth ? captureSessionSnapshot(getToken(), getRefreshToken()) : null
  return new Promise((resolve, reject) => {
    const header = {}
    const token = requestSnapshot ? requestSnapshot.accessToken : ''
    if (token) header.Authorization = 'Bearer ' + token
    uni.downloadFile({
      url: ENV.apiBaseUrl + ENV.apiPrefix + path,
      header,
      timeout: Math.max(ENV.requestTimeout || 10000, 30000),
      success: (res) => {
        if (res.statusCode === 401 && auth && !_retried) {
          refreshOrReuseCurrentSession(requestSnapshot)
            .then(() => realDownload(path, {
              auth, _retried: true, _expectedGeneration: requestSnapshot.generation
            }))
            .then(resolve)
            .catch(reject)
          return
        }
        if (requestSnapshot && !isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {
          reject(sessionChangedError())
          return
        }
        if (res.statusCode === 200 && res.tempFilePath) {
          resolve({ tempFilePath: res.tempFilePath })
          return
        }
        reject({ code: res.statusCode === 403 ? 403001 : 404001, biz: true, message: '文件不存在或无权下载' })
      },
      fail: (err) => {
        if (requestSnapshot && !isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {
          reject(sessionChangedError())
          return
        }
        markOffline()
        // errMsg 可能包含系统路径、域名或网关细节；用户只需要可执行的恢复指引。
        reject({
          code: 'NETWORK',
          message: '附件下载失败，请检查网络后重试',
          serverMessage: err && err.errMsg ? String(err.errMsg) : ''
        })
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
  setToken, getToken, clearTokens, commitNewSessionTokens, safeToast, toastError, normalizeError,
  createSubmitLock, requireAuthOrRedirect, registerForceLogoutHandler, isBusinessError, isNetworkError
}
