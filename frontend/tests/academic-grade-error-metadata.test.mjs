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

test('复查业务拒绝保留 HTTP 状态与追踪号，不泄露内部错误对象', async () => {
  const target = api(async () => { throw Object.assign(new Error('该学期已归档封存，禁止修改'), {
    biz: true, code: 500001, bizCode: 'TERM_ARCHIVED', httpStatus: 409,
    traceId: 'recheck-test', cause: { internal: 'private' }
  }) })
  for (const result of await Promise.all([target.reviewGradeRecheck('7', {}), target.getGradeRechecks(), target.getGradeRecheck('7')])) {
    assert.equal(result.httpStatus, 409)
    assert.equal(result.bizCode, 'TERM_ARCHIVED')
    assert.equal(result.traceId, 'recheck-test')
    assert.equal('cause' in result, false)
  }
})

test('复查网络超时保持未确定，API 不自动重放', async () => {
  let calls = 0
  const target = api(async () => { calls++; throw Object.assign(new Error('请求超时'), { biz: true, code: 503002, bizCode: 'REQUEST_TIMEOUT' }) })
  const result = await target.reviewGradeRecheck('7', {})
  assert.equal(calls, 1)
  assert.equal(result.bizCode, 'REQUEST_TIMEOUT')
  assert.equal(result.httpStatus, undefined)
})

test('成绩更正按正式分页契约读取空队列与大整数申请编号', async () => {
  for (const items of [[], [{ changeRequestId: '1000000000000000999' }]]) {
    const target = api(async () => ({ items, total: items.length, page: 1, pageSize: 20 }))
    const result = await target.getGradeChanges({ queue: 'PENDING' })
    assert.equal(result.code, 0)
    assert.equal(result.data.list, items)
    assert.equal(result.data.total, items.length)
  }
  const invalid = await api(async () => ({ total: 0 })).getGradeChanges({})
  assert.notEqual(invalid.code, 0, '损坏回执不能伪装成空队列')
})
