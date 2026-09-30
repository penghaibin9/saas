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
