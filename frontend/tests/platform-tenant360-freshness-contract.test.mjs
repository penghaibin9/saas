import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/modules/platform/views/control/PlatformControlTenantDetail.vue', import.meta.url), 'utf8')

test('tenant360 clears stale tenant payload before every reload', () => {
  assert.match(source, /clearTenantPayload\(\)/)
  assert.match(source, /this\.tenant = null/)
  assert.match(source, /this\.tenant360 = \{\}/)
  assert.match(source, /this\.oneTimeSecret = ''/)
})

test('tenant360 isolates route reuse and late responses with epochs', () => {
  assert.match(source, /requestEpoch/)
  assert.match(source, /tabRequestEpoch/)
  assert.match(source, /watch:\s*\{[\s\S]*tid\(newTenantId, oldTenantId\)/)
  assert.match(source, /epoch !== this\.requestEpoch/)
  assert.match(source, /tenantId !== String\(this\.tid \|\| ''\)/)
  assert.match(source, /const stillCurrent = \(\) => epoch === this\.tabRequestEpoch/)
})

test('legacy commercial and workflow surfaces are read-only in tenant360', () => {
  assert.match(source, /商业授权（只读对账）/)
  assert.match(source, /WorkflowDefinition 是唯一运行真值/)
  assert.doesNotMatch(source, /@click="saveFeatures"/)
  assert.doesNotMatch(source, /@change="saveWorkflow/)
})

test('rules and brand writes send optimistic-lock metadata through hardening api', () => {
  assert.match(source, /platformControlHardeningApi\.putRules\(this\.tid, this\.rules, this\.rulesVersion, reason\.trim\(\)\)/)
  assert.match(source, /platformControlHardeningApi\.putBrand\(this\.tid, \{ \.\.\.this\.brand \}, this\.brandVersion, reason\.trim\(\)\)/)
})
