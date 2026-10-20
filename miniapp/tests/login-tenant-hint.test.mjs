import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { normalizeLoginTenantHint } from '../src/utils/loginTenantHint.mjs'
import { buildHandoff } from '../scripts/generate-v3-handoff.mjs'
test('school link hints accept codes, never URLs, objects or unbounded input', () => {
  assert.equal(normalizeLoginTenantHint(' sandbox-school '), 'sandbox-school')
  assert.equal(normalizeLoginTenantHint('school_0002'), 'school_0002')
  for (const value of [undefined, null, [], {}, 'https://example.com', '../other', 'a&role=admin', 'x'.repeat(101)]) assert.equal(normalizeLoginTenantHint(value), '')
})
for (const side of ['student', 'teacher']) test(`${side} entry forwards the exact URL school hint to the login component`, () => {
  const source = readFileSync(new URL(`../src/pages/login/${side}/index.vue`, import.meta.url), 'utf8')
  assert.match(source, /:tenant-code-hint="tenantCodeHint"/)
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'module.exports =')
  const scope = { module: { exports: {} }, normalizeLoginTenantHint, MiniLoginAuthPanel: {} }
  vm.runInNewContext(script, scope)
  const component = scope.module.exports, state = component.data()
  component.onLoad.call(state, { tenant: 'sandbox-school', dormRectificationId: '123' })
  assert.equal(state.tenantCodeHint, 'sandbox-school')
  assert.equal(state.dormRectificationId, '123')
  component.onLoad.call(state, { tenantCode: 'school_0002' })
  assert.equal(state.tenantCodeHint, 'school_0002')
})
test('handoff fingerprints actual source and distinguishes uncommitted candidates', () => {
  const current = buildHandoff()
  assert.match(current.sourceFingerprint, /^[a-f0-9]{64}$/)
  assert.ok(['WORKING_TREE_CANDIDATE', 'COMMITTED'].includes(current.implementationState))
  assert.equal(buildHandoff().sourceFingerprint, current.sourceFingerprint)
})
