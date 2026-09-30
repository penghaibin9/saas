import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as generation from '../src/services/sessionGeneration.mjs'

function runtime() {
  const timers = [], routes = [], storage = new Map()
  const uni = {
    getStorageSync: key => storage.get(key) || '',
    setStorageSync: (key, value) => storage.set(key, value),
    removeStorageSync: key => storage.delete(key),
    showToast() {}, reLaunch: options => routes.push(options.url)
  }
  const source = readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm, '')
    .replace(/export default[\s\S]*$/, '').replace(/^export /gm, '')
  let routedThroughLock = 0
  let blocked = false
  const api = new Function('ENV', 'uni', 'setTimeout', 'relaunch', 'getCurrentPages', ...Object.keys(generation),
    `${source}\nreturn { requireAuthOrRedirect, commitNewSessionTokens, getToken }`)(
    {}, uni, fn => timers.push(fn), url => { if (blocked) return false; routedThroughLock++; routes.push(url); return true },
    () => [{ route: 'pages/teacher/workbench/index' }], ...Object.values(generation))
  return { ...api, timers, routes, block: value => { blocked = value }, throughLock: () => routedThroughLock }
}

test('expired-session timer cannot destroy the teacher home after a new login', () => {
  const api = runtime()
  api.requireAuthOrRedirect()
  api.commitNewSessionTokens('new-test-access', 'new-test-refresh')
  api.timers[0]()
  assert.deepEqual(api.routes, [])
  assert.equal(api.getToken(), 'new-test-access')
})

test('repeated session expiry creates one redirect using the shared navigation lock', () => {
  const api = runtime()
  api.requireAuthOrRedirect(); api.requireAuthOrRedirect()
  assert.equal(api.timers.length, 1)
  api.timers[0]()
  assert.deepEqual(api.routes, ['/pages/login/index'])
  assert.equal(api.throughLock(), 1)
})

test('old redirect callback cannot release or execute a later expired-session redirect', () => {
  const api = runtime()
  api.requireAuthOrRedirect()
  api.commitNewSessionTokens('new-test-access', 'new-test-refresh')
  api.requireAuthOrRedirect()
  assert.equal(api.timers.length, 2)
  api.timers[0]()
  assert.deepEqual(api.routes, [])
  api.timers[1]()
  assert.deepEqual(api.routes, ['/pages/login/index'])
})

test('auth redirect waits for the active route, and cancels that wait if login succeeds', () => {
  for (const loginSucceeds of [false, true]) {
    const api = runtime()
    api.block(true)
    api.requireAuthOrRedirect(); api.timers[0]()
    assert.deepEqual(api.routes, [])
    assert.equal(api.timers.length, 2)
    if (loginSucceeds) api.commitNewSessionTokens('new-test-access', 'new-test-refresh')
    api.block(false); api.timers[1]()
    assert.deepEqual(api.routes, loginSucceeds ? [] : ['/pages/login/index'])
  }
})
