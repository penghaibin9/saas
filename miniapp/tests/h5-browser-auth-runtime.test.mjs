import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

test('H5 adapter rewrites actual requests and never persists access or refresh credentials', () => {
  const stored = new Map([['gx_token_v1', 'old-access'], ['gx_refresh_v1', 'old-refresh']])
  const tab = new Map(), requests = []
  const storage = values => ({ getItem: key => values.get(key),
    setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) })
  const runtime = { getStorageSync: key => stored.get(key),
    setStorageSync: (key, value) => stored.set(key, value),
    removeStorageSync: key => stored.delete(key), request: options => requests.push(options) }
  const context = vm.createContext({ h5Uni: runtime, document: {},
    window: { sessionStorage: storage(tab), localStorage: storage(stored) } })
  const source = readFileSync(new URL('../src/services/h5BrowserAuthInstaller.js', import.meta.url), 'utf8')
    .replace(/^import .*$/m, '').replace('export const H5_BROWSER_AUTH_INSTALLED', 'const H5_BROWSER_AUTH_INSTALLED')
  vm.runInContext(source, context)
  runtime.request({ url: '/api/v1/auth/login', data: { clientType: 'STUDENT_MINI' } })
  assert.equal(requests[0].url, '/api/v1/auth/browser-login')
  assert.equal(requests[0].data.clientType, 'STUDENT_PC')
  assert.equal(requests[0].header['X-Browser-Session'], 'student')
  assert.equal(requests[0].withCredentials, true)
  runtime.setStorageSync('gx_token_v1', 'new-access')
  runtime.setStorageSync('gx_refresh_v1', 'new-refresh')
  assert.equal(runtime.getStorageSync('gx_token_v1'), 'new-access')
  assert.equal(runtime.getStorageSync('gx_refresh_v1'), '__HTTPONLY_BROWSER_REFRESH__')
  assert.equal(stored.has('gx_token_v1'), false)
  assert.equal(stored.has('gx_refresh_v1'), false)
  runtime.request({ url: '/api/v1/auth/refresh', data: { refreshToken: 'must-not-send' } })
  assert.equal(requests[1].url, '/api/v1/auth/browser-refresh')
  assert.deepEqual(Object.keys(requests[1].data), [])
  runtime.removeStorageSync('gx_token_v1')
  assert.equal(requests[2].url, '/api/v1/auth/browser-logout')
  assert.equal(runtime.getStorageSync('gx_token_v1'), '')
  assert.equal(runtime.getStorageSync('gx_refresh_v1'), '')
})
