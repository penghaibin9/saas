import test from 'node:test'
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
