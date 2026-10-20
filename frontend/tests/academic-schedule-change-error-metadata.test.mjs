import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function api(request) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/api/academic-schedule-change.api.js', import.meta.url), 'utf8')
    .replace(/^import .*$/m, '').replaceAll('export const ', 'const ').replace('export default scheduleChangeApi', 'api = scheduleChangeApi')
  const sandbox = { request }
  vm.runInNewContext(source, sandbox)
  return sandbox.api
}

test('formal conflict metadata reaches both list and command consumers without exposing internal errors', async () => {
  const error = Object.assign(new Error('已存在在途申请'), {
    biz: true, code: 409001, bizCode: 'DATA_CONFLICT', traceId: 'test-trace',
    details: { existingChangeId: '1000000000000063602' },
    cause: { private: 'internal-only' }, rawDeveloperDetail: 'internal-only',
  })
  const target = api(async () => { throw error })
  for (const result of await Promise.all([target.list(), target.detail('1'), target.submit({}), target.approve('1', 2)])) {
    assert.equal(result.code, 409001)
    assert.equal(result.bizCode, 'DATA_CONFLICT')
    assert.equal(result.details.existingChangeId, '1000000000000063602')
    assert.equal(result.traceId, 'test-trace')
    assert.equal(result.data, null)
    assert.equal('cause' in result, false)
    assert.equal('rawDeveloperDetail' in result, false)
  }
})

test('write timeout remains unknown and invokes the request only once', async () => {
  let calls = 0
  const target = api(async () => { calls++; throw Object.assign(new Error('请求超时'), { biz: true, code: 503002, bizCode: 'REQUEST_TIMEOUT' }) })
  const result = await target.submit({ originItemId: '1000000000000063602' })
  assert.equal(calls, 1)
  assert.equal(result.code, 503002)
  assert.equal(result.bizCode, 'REQUEST_TIMEOUT')
  assert.equal(result.data, null)
})

test('success and filtered pagination keep their existing contract', async () => {
  const calls = []
  const target = api(async (path, options) => {
    calls.push({ path, options })
    return { items: [{ changeId: 'exact' }], total: 22, page: 3, pageSize: 10 }
  })
  const result = await target.list({ status: 'SUBMITTED,COLLEGE_REVIEW,ACADEMIC_REVIEW', page: 3, pageSize: 10 })
  assert.equal(result.code, 0)
  assert.equal(result.data.total, 22)
  assert.equal(result.data.page, 3)
  assert.equal(result.data.list[0].changeId, 'exact')
  assert.equal(calls[0].options.params.status, 'SUBMITTED,COLLEGE_REVIEW,ACADEMIC_REVIEW')
  assert.equal('details' in result, false)
})
