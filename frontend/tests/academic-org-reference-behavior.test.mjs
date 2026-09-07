import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

function panel(api) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/components/AaOrgReferencePanel.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { academicAffairsOrgApi: api } }
  vm.runInNewContext(script, sandbox)
  const definition = sandbox.component
  return Object.assign(definition.data(), definition.methods, { collegeOptions: [], $emit() {} })
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const result = (id = '1') => ({ code: 0, data: { list: [{ targetType: 'CLASS', targetId: id, refs: [] }], total: 40 } })

test('pagination keeps applied filters until the user runs a fresh check', async () => {
  const calls = []
  const state = panel({ listOrgReferenceChecks: async params => { calls.push(params); return result() } })
  state.criteria.keyword = ' 软件 '
  await state.runCheck()
  state.criteria.keyword = '未提交'
  await state.changePage(2)
  assert.equal(calls[1].keyword, '软件')
  assert.equal(calls[1].page, 2)
  await state.runCheck()
  assert.equal(calls[2].keyword, '未提交')
  assert.equal(calls[2].page, 1)
  assert.equal(state.rows[0].key, 'CLASS:1')
})

test('older overview requests cannot replace a newer result or clear its spinner', async () => {
  const first = deferred(), second = deferred()
  let calls = 0
  const state = panel({ listOrgReferenceChecks: () => ++calls === 1 ? first.promise : second.promise })
  const old = state.runCheck(), latest = state.runCheck()
  first.resolve(result('old')); await old
  assert.equal(state.loading, true)
  second.resolve(result('latest')); await latest
  assert.equal(state.rows[0].targetId, 'latest')
  assert.equal(state.loading, false)
})

test('overview errors remain retryable and release loading', async () => {
  const state = panel({ listOrgReferenceChecks: async () => { throw new Error('连接中断') } })
  await state.runCheck()
  assert.equal(state.error, '连接中断')
  assert.equal(state.loading, false)
})

test('closing a detail ignores its late response and retry fetches the same target', async () => {
  const pending = deferred()
  let calls = 0
  const state = panel({ getOrgReferenceCheck: async (kind, id) => {
    assert.equal(kind, 'CLASS'); assert.equal(id, '7')
    return ++calls === 1 ? pending.promise : { code: 0, data: { targetType: kind, targetId: id } }
  } })
  const request = state.openDetail({ targetType: 'CLASS', targetId: '7' })
  state.closeDetail(); pending.resolve({ code: 0, data: { targetId: 'old' } }); await request
  assert.equal(state.detail.report, null)
  await state.retryDetail()
  let emitted
  state.$emit = (name, report) => { emitted = { name, report } }
  state.viewOrganization()
  assert.equal(emitted.name, 'view-organization')
  assert.equal(emitted.report.targetId, '7')
  assert.equal(state.detail.visible, false)
})
