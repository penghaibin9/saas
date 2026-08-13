from pathlib import Path


def read(path):
    return Path(path).read_text(encoding='utf-8')


def write(path, text):
    Path(path).write_text(text, encoding='utf-8')


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 anchor, found {count}')
    return text.replace(old, new, 1)


write('miniapp/src/services/sessionGeneration.mjs', r'''let sessionGeneration = 0

export function currentSessionGeneration() {
  return sessionGeneration
}

export function advanceSessionGeneration() {
  sessionGeneration += 1
  return sessionGeneration
}

export function captureSessionSnapshot(accessToken, refreshToken) {
  return {
    generation: currentSessionGeneration(),
    accessToken: String(accessToken || ''),
    refreshToken: String(refreshToken || '')
  }
}

export function isSessionSnapshotCurrent(snapshot, accessToken, refreshToken) {
  return !!snapshot &&
    snapshot.generation === currentSessionGeneration() &&
    snapshot.accessToken === String(accessToken || '') &&
    snapshot.refreshToken === String(refreshToken || '')
}

export function sessionChangedError() {
  return {
    code: 'SESSION_CHANGED',
    bizCode: 'SESSION_CHANGED',
    biz: true,
    staleSession: true,
    message: '登录状态已变化，请重试'
  }
}

export function assertSessionSnapshot(snapshot, accessToken, refreshToken) {
  if (!isSessionSnapshotCurrent(snapshot, accessToken, refreshToken)) throw sessionChangedError()
  return snapshot
}

export async function guardSessionPromise(promise, {
  snapshot,
  getAccessToken,
  getRefreshToken,
  onSuccess,
  onCurrentError
}) {
  try {
    const value = await promise
    assertSessionSnapshot(snapshot, getAccessToken(), getRefreshToken())
    return onSuccess ? await onSuccess(value) : value
  } catch (error) {
    if (!isSessionSnapshotCurrent(snapshot, getAccessToken(), getRefreshToken())) {
      throw sessionChangedError()
    }
    if (onCurrentError) return onCurrentError(error)
    throw error
  }
}

export function __resetSessionGenerationForTests(value = 0) {
  sessionGeneration = Number(value) || 0
}
''')

p = 'miniapp/src/services/request.js'
t = read(p)
t = replace_once(
    t,
    "import { markMobileViewsDirty } from '@/utils/viewFreshness'\n",
    "import { markMobileViewsDirty } from '@/utils/viewFreshness'\nimport {\n  advanceSessionGeneration, assertSessionSnapshot, captureSessionSnapshot,\n  currentSessionGeneration, guardSessionPromise, isSessionSnapshotCurrent, sessionChangedError\n} from './sessionGeneration.mjs'\n",
    'request generation import'
)
t = replace_once(
    t,
    "export function getRefreshToken() {\n  try { return uni.getStorageSync(REFRESH_KEY) || '' } catch (e) { return '' }\n}\n",
    "export function getRefreshToken() {\n  try { return uni.getStorageSync(REFRESH_KEY) || '' } catch (e) { return '' }\n}\n\nexport function commitNewSessionTokens(accessToken, refreshToken) {\n  advanceSessionGeneration()\n  setToken(accessToken || '')\n  setRefreshToken(refreshToken || '')\n  return currentSessionGeneration()\n}\n",
    'commit session tokens'
)
t = replace_once(
    t,
    "export function clearTokens() {\n  setToken('')\n  setRefreshToken('')\n  setTeacherGraduationBatch(null)\n}\n",
    "export function clearTokens() {\n  advanceSessionGeneration()\n  setToken('')\n  setRefreshToken('')\n  setTeacherGraduationBatch(null)\n}\n",
    'clear advances generation'
)
old_refresh = '''let _refreshing = null
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
'''
new_refresh = '''let _refreshing = null
function _refreshOnce(expectedGeneration = currentSessionGeneration()) {
  if (_refreshing && _refreshing.generation === expectedGeneration) return _refreshing.promise
  if (currentSessionGeneration() !== expectedGeneration) return Promise.reject(sessionChangedError())
  const snapshot = captureSessionSnapshot(getToken(), getRefreshToken())
  if (!snapshot.refreshToken) {
    return Promise.reject({ code: 401001, biz: true, message: '未登录' })
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
'''
t = replace_once(t, old_refresh, new_refresh, 'refresh once')
t = replace_once(
    t,
    "function inflightKey(method, effectivePath, data, auth) {\n  const identity = auth ? getToken() : 'public'\n  return `${method}|${effectivePath}|${stablePayload(data)}|${identity}`\n}\n",
    "function inflightKey(method, effectivePath, data, auth) {\n  const identity = auth ? `${currentSessionGeneration()}|${getToken()}` : 'public'\n  return `${method}|${effectivePath}|${stablePayload(data)}|${identity}`\n}\n",
    'inflight generation key'
)
t = replace_once(
    t,
    "function executeRealRequest(path, effectivePath, {\n  method, data, auth, _retried, _rawPage\n}) {\n  return new Promise((resolve, reject) => {\n    const header = { 'Content-Type': 'application/json' }\n    const token = auth ? getToken() : ''\n",
    "function executeRealRequest(path, effectivePath, {\n  method, data, auth, _retried, _rawPage, _expectedGeneration\n}) {\n  if (auth && _expectedGeneration != null && currentSessionGeneration() !== _expectedGeneration) {\n    return Promise.reject(sessionChangedError())\n  }\n  const requestSnapshot = auth ? captureSessionSnapshot(getToken(), getRefreshToken()) : null\n  return new Promise((resolve, reject) => {\n    const header = { 'Content-Type': 'application/json' }\n    const token = requestSnapshot ? requestSnapshot.accessToken : ''\n",
    'execute request snapshot'
)
t = replace_once(
    t,
    "      success: (res) => {\n        const body = res.data\n",
    "      success: (res) => {\n        if (requestSnapshot && !isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {\n          reject(sessionChangedError())\n          return\n        }\n        const body = res.data\n",
    'request success stale guard'
)
t = replace_once(
    t,
    "            _refreshOnce()\n              .then(() => realRequest(path, { method, data, auth, _retried: true, _rawPage }))\n",
    "            _refreshOnce(requestSnapshot.generation)\n              .then(() => realRequest(path, {\n                method, data, auth, _retried: true, _rawPage,\n                _expectedGeneration: requestSnapshot.generation\n              }))\n",
    'request 401 replay guard'
)
t = replace_once(
    t,
    "      fail: (err) => {\n        markOffline()\n        reject({ code: 'NETWORK', message: (err && err.errMsg) || '网络异常' })\n      }\n",
    "      fail: (err) => {\n        if (requestSnapshot && !isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {\n          reject(sessionChangedError())\n          return\n        }\n        markOffline()\n        reject({ code: 'NETWORK', message: (err && err.errMsg) || '网络异常' })\n      }\n",
    'request fail stale guard'
)
t = replace_once(
    t,
    "export function realRequest(path, {\n  method = 'GET', data, auth = true, _retried = false, _rawPage = false\n} = {}) {\n",
    "export function realRequest(path, {\n  method = 'GET', data, auth = true, _retried = false, _rawPage = false, _expectedGeneration = null\n} = {}) {\n",
    'realRequest signature'
)
t = t.replace(
    "method: normalizedMethod, data, auth, _retried, _rawPage\n",
    "method: normalizedMethod, data, auth, _retried, _rawPage, _expectedGeneration\n"
)
# realUpload: capture logical session and bind retry to the same generation.
t = replace_once(
    t,
    "export function realUpload(path, filePath, {\n  name = 'file', formData = {}, auth = true, _retried = false\n} = {}) {\n  return new Promise((resolve, reject) => {\n",
    "export function realUpload(path, filePath, {\n  name = 'file', formData = {}, auth = true, _retried = false, _expectedGeneration = null\n} = {}) {\n  if (auth && _expectedGeneration != null && currentSessionGeneration() !== _expectedGeneration) {\n    return Promise.reject(sessionChangedError())\n  }\n  const requestSnapshot = auth ? captureSessionSnapshot(getToken(), getRefreshToken()) : null\n  return new Promise((resolve, reject) => {\n",
    'upload snapshot'
)
t = replace_once(t, "    const token = auth ? getToken() : ''\n    if (token) header.Authorization = 'Bearer ' + token\n    uni.uploadFile({\n", "    const token = requestSnapshot ? requestSnapshot.accessToken : ''\n    if (token) header.Authorization = 'Bearer ' + token\n    uni.uploadFile({\n", 'upload token snapshot')
t = replace_once(
    t,
    "      success: (res) => {\n        const body = parseUnifiedBody(res.data)\n",
    "      success: (res) => {\n        if (requestSnapshot && !isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {\n          reject(sessionChangedError())\n          return\n        }\n        const body = parseUnifiedBody(res.data)\n",
    'upload success guard'
)
t = replace_once(
    t,
    "            _refreshOnce()\n              .then(() => realUpload(path, filePath, { name, formData, auth, _retried: true }))\n",
    "            _refreshOnce(requestSnapshot.generation)\n              .then(() => realUpload(path, filePath, {\n                name, formData, auth, _retried: true, _expectedGeneration: requestSnapshot.generation\n              }))\n",
    'upload retry guard'
)
t = replace_once(
    t,
    "      fail: (err) => {\n        markOffline()\n        reject({ code: 'NETWORK', message: (err && err.errMsg) || '上传失败' })\n      }\n",
    "      fail: (err) => {\n        if (requestSnapshot && !isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {\n          reject(sessionChangedError())\n          return\n        }\n        markOffline()\n        reject({ code: 'NETWORK', message: (err && err.errMsg) || '上传失败' })\n      }\n",
    'upload fail guard'
)
# realDownload: same logical-session protection.
t = replace_once(
    t,
    "export function realDownload(path, { auth = true, _retried = false } = {}) {\n  return new Promise((resolve, reject) => {\n    const header = {}\n    const token = auth ? getToken() : ''\n",
    "export function realDownload(path, { auth = true, _retried = false, _expectedGeneration = null } = {}) {\n  if (auth && _expectedGeneration != null && currentSessionGeneration() !== _expectedGeneration) {\n    return Promise.reject(sessionChangedError())\n  }\n  const requestSnapshot = auth ? captureSessionSnapshot(getToken(), getRefreshToken()) : null\n  return new Promise((resolve, reject) => {\n    const header = {}\n    const token = requestSnapshot ? requestSnapshot.accessToken : ''\n",
    'download snapshot'
)
t = replace_once(
    t,
    "      success: (res) => {\n        if (res.statusCode === 200 && res.tempFilePath) {\n",
    "      success: (res) => {\n        if (requestSnapshot && !isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {\n          reject(sessionChangedError())\n          return\n        }\n        if (res.statusCode === 200 && res.tempFilePath) {\n",
    'download success guard'
)
t = replace_once(
    t,
    "          _refreshOnce()\n            .then(() => realDownload(path, { auth, _retried: true }))\n",
    "          _refreshOnce(requestSnapshot.generation)\n            .then(() => realDownload(path, {\n              auth, _retried: true, _expectedGeneration: requestSnapshot.generation\n            }))\n",
    'download retry guard'
)
t = replace_once(
    t,
    "      fail: (err) => {\n        markOffline()\n        reject({ code: 'NETWORK', message: (err && err.errMsg) || '下载失败' })\n      }\n",
    "      fail: (err) => {\n        if (requestSnapshot && !isSessionSnapshotCurrent(requestSnapshot, getToken(), getRefreshToken())) {\n          reject(sessionChangedError())\n          return\n        }\n        markOffline()\n        reject({ code: 'NETWORK', message: (err && err.errMsg) || '下载失败' })\n      }\n",
    'download fail guard'
)
t = replace_once(
    t,
    "  setToken, getToken, clearTokens, safeToast, toastError, normalizeError,\n",
    "  setToken, getToken, clearTokens, commitNewSessionTokens, safeToast, toastError, normalizeError,\n",
    'request default export'
)
write(p, t)

p = 'miniapp/src/services/realApi.js'
t = read(p)
t = replace_once(t, "import { realRequest, setRefreshToken, setToken } from './request'\n", "import { commitNewSessionTokens, realRequest } from './request'\n", 'realApi import')
t = replace_once(t, "function _holdLogin(data) {\n  setToken(data.accessToken)\n  setRefreshToken(data.refreshToken || '')\n  return data\n}\n", "function _holdLogin(data) {\n  commitNewSessionTokens(data.accessToken, data.refreshToken || '')\n  return data\n}\n", 'role switch commit')
write(p, t)

p = 'miniapp/src/components/login/MiniLoginAuthPanel.vue'
t = read(p)
t = replace_once(t, "import { clearTokens, realRequest, setRefreshToken, setToken } from '@/services/request'\n", "import { clearTokens, commitNewSessionTokens, realRequest } from '@/services/request'\n", 'login import')
t = replace_once(t, "      setToken(data.accessToken)\n      setRefreshToken(data.refreshToken || '')\n", "      commitNewSessionTokens(data.accessToken, data.refreshToken || '')\n", 'login token commit')
write(p, t)

write('miniapp/tests/auth-session-generation.test.mjs', r'''import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import {
  __resetSessionGenerationForTests,
  advanceSessionGeneration,
  captureSessionSnapshot,
  currentSessionGeneration,
  guardSessionPromise,
  isSessionSnapshotCurrent,
  sessionChangedError
} from '../src/services/sessionGeneration.mjs'

function deferred() {
  let resolve, reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

function harness(access = 'a1', refresh = 'r1') {
  let a = access
  let r = refresh
  return {
    getAccess: () => a,
    getRefresh: () => r,
    setAccess: (v) => { a = v },
    setRefresh: (v) => { r = v }
  }
}

test.beforeEach(() => __resetSessionGenerationForTests())

test('generation advances only when logical session changes', () => {
  assert.equal(currentSessionGeneration(), 0)
  assert.equal(advanceSessionGeneration(), 1)
  assert.equal(advanceSessionGeneration(), 2)
})

test('snapshot captures generation and both credentials', () => {
  const snapshot = captureSessionSnapshot('a1', 'r1')
  assert.deepEqual(snapshot, { generation: 0, accessToken: 'a1', refreshToken: 'r1' })
  assert.equal(isSessionSnapshotCurrent(snapshot, 'a1', 'r1'), true)
})

test('late old-session success cannot apply after new login', async () => {
  const h = harness()
  const d = deferred()
  let applied = false
  const snapshot = captureSessionSnapshot(h.getAccess(), h.getRefresh())
  const guarded = guardSessionPromise(d.promise, {
    snapshot, getAccessToken: h.getAccess, getRefreshToken: h.getRefresh,
    onSuccess: () => { applied = true }
  })
  advanceSessionGeneration(); h.setAccess('a2'); h.setRefresh('r2'); d.resolve({ ok: true })
  await assert.rejects(guarded, (e) => e.code === 'SESSION_CHANGED' && e.staleSession === true)
  assert.equal(applied, false)
})

test('late old-session failure cannot logout the newer account', async () => {
  const h = harness()
  const d = deferred()
  let currentErrorHandled = false
  const snapshot = captureSessionSnapshot(h.getAccess(), h.getRefresh())
  const guarded = guardSessionPromise(d.promise, {
    snapshot, getAccessToken: h.getAccess, getRefreshToken: h.getRefresh,
    onCurrentError: () => { currentErrorHandled = true }
  })
  advanceSessionGeneration(); h.setAccess('a2'); h.setRefresh('r2'); d.reject(new Error('old refresh failed'))
  await assert.rejects(guarded, (e) => e.code === 'SESSION_CHANGED' && e.staleSession === true)
  assert.equal(currentErrorHandled, false)
})

test('current-session success may commit refreshed credentials', async () => {
  const h = harness()
  const d = deferred()
  const snapshot = captureSessionSnapshot(h.getAccess(), h.getRefresh())
  const guarded = guardSessionPromise(d.promise, {
    snapshot, getAccessToken: h.getAccess, getRefreshToken: h.getRefresh,
    onSuccess: (value) => value.access
  })
  d.resolve({ access: 'a2' })
  assert.equal(await guarded, 'a2')
})

test('current-session failure remains a real auth failure', async () => {
  const h = harness()
  const d = deferred()
  let handled = false
  const snapshot = captureSessionSnapshot(h.getAccess(), h.getRefresh())
  const guarded = guardSessionPromise(d.promise, {
    snapshot, getAccessToken: h.getAccess, getRefreshToken: h.getRefresh,
    onCurrentError: (error) => { handled = true; throw error }
  })
  d.reject(Object.assign(new Error('refresh failed'), { code: 401001 }))
  await assert.rejects(guarded, (e) => e.code === 401001)
  assert.equal(handled, true)
})

test('access token replacement invalidates an in-flight snapshot even without generation change', () => {
  const snapshot = captureSessionSnapshot('a1', 'r1')
  assert.equal(isSessionSnapshotCurrent(snapshot, 'a2', 'r1'), false)
})

test('refresh token replacement invalidates an in-flight snapshot even without generation change', () => {
  const snapshot = captureSessionSnapshot('a1', 'r1')
  assert.equal(isSessionSnapshotCurrent(snapshot, 'a1', 'r2'), false)
})

test('stale error is a fail-closed business error with explicit stale marker', () => {
  assert.deepEqual(sessionChangedError(), {
    code: 'SESSION_CHANGED', bizCode: 'SESSION_CHANGED', biz: true, staleSession: true,
    message: '登录状态已变化，请重试'
  })
})

test('request, upload, download and GET singleflight are wired to logical generation', async () => {
  const source = await readFile(new URL('../src/services/request.js', import.meta.url), 'utf8')
  assert.match(source, /currentSessionGeneration\(\).*?\|\$\{getToken\(\)\}/s)
  assert.match(source, /_refreshOnce\(requestSnapshot\.generation\)/)
  assert.match(source, /realUpload[\s\S]*?captureSessionSnapshot/)
  assert.match(source, /realDownload[\s\S]*?captureSessionSnapshot/)
  assert.match(source, /_expectedGeneration: requestSnapshot\.generation/g)
  assert.match(source, /reject\(sessionChangedError\(\)\)/g)
})
''')

# Fail fast if another miniapp path still stores a login/switch-role token pair directly.
for path in ('miniapp/src/services/realApi.js', 'miniapp/src/components/login/MiniLoginAuthPanel.vue'):
    source = read(path)
    if 'setRefreshToken(' in source or 'setToken(data.accessToken)' in source:
        raise SystemExit(f'{path}: direct logical-session token commit remains')
