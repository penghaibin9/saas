import test from 'node:test'
import assert from 'node:assert/strict'
import { sandboxBuildEnv, verifySandboxOutput, configureSandboxProject } from '../scripts/build-mp-weixin-sandbox.mjs'
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { defaultWeixinBuildArgs } from '../scripts/build-mp-weixin.mjs'

test('daily Weixin build uses the sandbox while release keeps its dedicated finalizer', () => {
  const { scripts } = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'))
  assert.equal(scripts['build:mp-weixin'], 'node scripts/build-mp-weixin.mjs')
  for (const env of [{}, { CI: 'false' }]) {
    const args = defaultWeixinBuildArgs(env)
    assert.equal(args.length, 1)
    assert.match(args[0], /build-mp-weixin-sandbox\.mjs$/)
  }
  const ciArgs = defaultWeixinBuildArgs({ CI: 'true' })
  assert.match(ciArgs[0], /uni\.js$/)
  assert.deepEqual(ciArgs.slice(1), ['build', '-p', 'mp-weixin'])
  assert.equal(scripts['build:mp-weixin:release'], 'uni build -p mp-weixin && node scripts/optimize-mp-weixin.mjs && node scripts/finalize-mp-weixin-release.mjs')
})

test('sandbox enables localhost debugging only in its private output config and preserves developer settings', () => {
  const dir = mkdtempSync(join(tmpdir(), 'weixin-sandbox-'))
  try {
    configureSandboxProject(dir)
    const path = join(dir, 'project.private.config.json')
    assert.equal(JSON.parse(readFileSync(path, 'utf8')).setting.urlCheck, false)
    writeFileSync(path, JSON.stringify({ libVersion: '3.17.2', setting: { urlCheck: true, es6: true }, condition: { miniprogram: {} } }))
    configureSandboxProject(dir)
    assert.deepEqual(JSON.parse(readFileSync(path, 'utf8')), {
      libVersion: '3.17.2', setting: { urlCheck: false, es6: true }, condition: { miniprogram: {} }
    })
  } finally { rmSync(dir, { recursive: true, force: true }) }
})

test('sandbox build preserves the default target and forces real data without mutating the parent environment', () => {
  const inherited = { VITE_USE_MOCK: 'true', PATH: 'kept' }
  assert.deepEqual(sandboxBuildEnv(inherited), {
    VITE_API_BASE_URL: 'http://127.0.0.1:8000', VITE_USE_MOCK: 'false', PATH: 'kept'
  })
  assert.deepEqual(inherited, { VITE_USE_MOCK: 'true', PATH: 'kept' })
})

test('sandbox build accepts an explicit loopback candidate port and preserves it through the real app environment', () => {
  const inherited = { VITE_API_BASE_URL: 'http://127.0.0.1:8001/', VITE_USE_MOCK: 'true', PATH: 'kept' }
  const buildEnv = sandboxBuildEnv(inherited)
  assert.deepEqual(buildEnv, { VITE_API_BASE_URL: 'http://127.0.0.1:8001', VITE_USE_MOCK: 'false', PATH: 'kept' })
  assert.equal(inherited.VITE_API_BASE_URL, 'http://127.0.0.1:8001/')
  const source = readFileSync(new URL('../src/config/env.js', import.meta.url), 'utf8')
    .replaceAll('import.meta.env.', 'build.')
    .replace('export const ENV', 'const ENV')
    .replace('export default ENV', 'return ENV')
  const env = new Function('build', source)({ ...buildEnv, DEV: false, PROD: true })
  assert.equal(env.apiBaseUrl, 'http://127.0.0.1:8001')
  assert.equal(env.useMock, false)
  assert.equal(env.allowMockFallback, false)
  assert.doesNotThrow(() => verifySandboxOutput(`exports.ENV = ${JSON.stringify(env)}`, buildEnv.VITE_API_BASE_URL))
})

test('sandbox target rejects external origins, credentials, paths and invalid ports before building', () => {
  for (const value of [
    'https://example.com', 'http://localhost:8001', 'http://127.0.0.2:8001',
    'http://127.0.0.1:0', 'http://127.0.0.1:65536', 'http://127.0.0.1:8001.5',
    'http://127.0.0.1', 'http://127.0.0.1:8001/api/v1', 'http://127.0.0.1:8001?x=1',
    'http://127.0.0.1:8001#x', 'http://user:pass@127.0.0.1:8001'
  ]) {
    assert.throws(() => sandboxBuildEnv({ VITE_API_BASE_URL: value }), /微信沙箱接口地址必须/)
  }
  for (const port of [1, 65535]) {
    const value = `http://127.0.0.1:${port}`
    assert.equal(sandboxBuildEnv({ VITE_API_BASE_URL: value }).VITE_API_BASE_URL, value)
  }
})

test('sandbox output gate rejects a release endpoint and fake data modes', () => {
  const env = { apiBaseUrl: 'http://127.0.0.1:8000', useMock: false, allowMockFallback: false }
  const source = value => `exports.ENV = ${JSON.stringify(value)}`
  assert.doesNotThrow(() => verifySandboxOutput(source(env)))
  for (const change of [{ apiBaseUrl: 'https://example.com' }, { useMock: true }, { allowMockFallback: true }]) {
    assert.throws(() => verifySandboxOutput(source({ ...env, ...change })), /沙箱构建校验失败/)
  }
})

test('sandbox output must match the selected candidate and cannot silently fall back to the default port', () => {
  const source = value => `exports.ENV = ${JSON.stringify(value)}`
  const expected = sandboxBuildEnv({ VITE_API_BASE_URL: 'http://127.0.0.1:8001' }).VITE_API_BASE_URL
  const env = { apiBaseUrl: expected, useMock: false, allowMockFallback: false }
  for (const change of [
    { apiBaseUrl: 'http://127.0.0.1:8000' }, { useMock: true }, { allowMockFallback: true },
    { useMock: 'false' }, { allowMockFallback: undefined }
  ]) {
    assert.throws(() => verifySandboxOutput(source({ ...env, ...change }), expected), /沙箱构建校验失败/)
  }
})
