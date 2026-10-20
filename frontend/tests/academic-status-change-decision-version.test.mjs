import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function api(request) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/api/academic-affairs.api.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replaceAll('export const ', 'const ')
    .replace('export default academicAffairsApi', 'api = academicAffairsApi')
  const sandbox = { request }
  vm.runInNewContext(source, sandbox)
  return sandbox.api
}

for (const version of [undefined, null, 0, 7]) {
  test(`status review preserves frozen decision version ${version} in a single request`, async () => {
    const calls = []
    const target = api(async (path, options) => { calls.push({ path, options }); return { decisionVersion: 8 } })
    const result = await target.reviewStatusChange('1000000000000063602', 'APPROVE', '已核对', version)
    assert.equal(calls.length, 1, 'adapter must not fetch a newer version or replay the command')
    assert.equal(calls[0].path, '/academic-affairs/status-changes/1000000000000063602/review')
    assert.equal(calls[0].options.method, 'POST')
    const expected = { action: 'APPROVE', reason: '已核对' }
    if (version != null) expected.expectedDecisionVersion = version
    assert.deepEqual(JSON.parse(JSON.stringify(calls[0].options.body)), expected)
    assert.equal(result.code, 0)
    assert.equal(result.data.decisionVersion, 8)
  })
}

test('status review retains the conflict and never retries using the current decision version', async () => {
  let calls = 0
  const target = api(async () => {
    calls++
    throw Object.assign(new Error('审批版本已变化'), { biz: true, code: 409001, bizCode: 'DATA_CONFLICT', details: { expectedDecisionVersion: 0, currentDecisionVersion: 1 } })
  })
  const result = await target.reviewStatusChange('exact-id', 'RETURN', '保留审批意见', 0)
  assert.equal(calls, 1)
  assert.equal(result.code, 409001)
  assert.equal(result.data, null)
  assert.equal(result.details.currentDecisionVersion, 1)
  assert.equal(result.details.expectedDecisionVersion, 0)
})
