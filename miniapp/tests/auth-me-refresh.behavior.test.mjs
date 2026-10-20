import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as generation from '../src/services/sessionGeneration.mjs'

function setup(initialToken = '') {
  const sent = []
  const storage = new Map([['gx_token_v1', initialToken], ['gx_refresh_v1', 'test-refresh']])
  const source = readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm, '').replace(/export default[\s\S]*$/, '').replace(/^export /gm, '')
  const uni = {
    getStorageSync: key => storage.get(key) || '',
    setStorageSync: (key, value) => storage.set(key, value),
    request(options) {
      sent.push({ path: new URL(options.url).pathname, token: options.header.Authorization })
      const refresh = options.url.endsWith('/auth/refresh')
      const expired = options.header.Authorization === 'Bearer expired'
      queueMicrotask(() => options.success({ statusCode: expired ? 401 : 200, data: expired
        ? { code: 401001, message: 'expired' }
        : { code: 0, data: refresh ? { accessToken: 'renewed', refreshToken: 'rotated' } : { contexts: ['teacher'] } } }))
    }
  }
  const realRequest = new Function('ENV', 'markMobileViewsDirty', 'uni', ...Object.keys(generation), `${source}\nreturn realRequest`)(
    { apiBaseUrl: 'https://school.test', apiPrefix: '/api/v1', requestTimeout: 1000 }, () => {}, uni, ...Object.values(generation))
  return { realRequest, sent }
}

test('identity page opened after F5 restores the session before requesting role contexts', async () => {
  const { realRequest, sent } = setup()
  assert.deepEqual(await realRequest('/auth/me'), { contexts: ['teacher'] })
  assert.deepEqual(sent.map(x => x.path), ['/api/v1/auth/refresh', '/api/v1/auth/me'])
  assert.equal(sent[1].token, 'Bearer renewed')
})

test('an expired identity request refreshes once and then retries with the rotated session', async () => {
  const { realRequest, sent } = setup('expired')
  await realRequest('/auth/me')
  assert.deepEqual(sent.map(x => x.path), ['/api/v1/auth/me', '/api/v1/auth/refresh', '/api/v1/auth/me'])
  assert.equal(sent[2].token, 'Bearer renewed')
})

test('concurrent identity and business bootstrap share one refresh request', async () => {
  const { realRequest, sent } = setup()
  await Promise.all([realRequest('/auth/me'), realRequest('/mobile/teacher/affairs')])
  assert.equal(sent.filter(x => x.path.endsWith('/auth/refresh')).length, 1)
})
