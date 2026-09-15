import test from 'node:test'
import assert from 'node:assert/strict'
import { sandboxBuildEnv, verifySandboxOutput } from '../scripts/build-mp-weixin-sandbox.mjs'

test('sandbox build overrides inherited release target without mutating the parent environment', () => {
  const inherited = { VITE_API_BASE_URL: 'https://example.com', VITE_USE_MOCK: 'true', PATH: 'kept' }
  assert.deepEqual(sandboxBuildEnv(inherited), {
    VITE_API_BASE_URL: 'http://127.0.0.1:8000', VITE_USE_MOCK: 'false', PATH: 'kept'
  })
  assert.equal(inherited.VITE_API_BASE_URL, 'https://example.com')
})

test('sandbox output gate rejects a release endpoint and fake data modes', () => {
  const env = { apiBaseUrl: 'http://127.0.0.1:8000', useMock: false, allowMockFallback: false }
  const source = value => `exports.ENV = ${JSON.stringify(value)}`
  assert.doesNotThrow(() => verifySandboxOutput(source(env)))
  for (const change of [{ apiBaseUrl: 'https://example.com' }, { useMock: true }, { allowMockFallback: true }]) {
    assert.throws(() => verifySandboxOutput(source({ ...env, ...change })), /沙箱构建校验失败/)
  }
})
