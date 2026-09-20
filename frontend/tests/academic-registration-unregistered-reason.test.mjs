import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue', import.meta.url), 'utf8')
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
function setup(api) {
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?$/gm, '').replace('export default', 'component =')
  const sandbox = { academicAffairsApi: api }
  for (const name of source.match(/components:\s*{([\s\S]*?)}/)[1].split(',').map(value => value.trim()).filter(Boolean)) sandbox[name] = {}
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const state = { ...component.data(), ...component.methods, ctx: { userId: 'admin' }, batchId: '', tab: 'unregistered' }
  for (const key of ['eligibilityContextKey', 'unregisteredRows']) Object.defineProperty(state, key, { get: () => component.computed[key].call(state) })
  return state
}
const studentId = '1000000000000063603'
const row = (batchId = '4') => ({ studentId, batchId, realName: '测试学生', studentNo: 'TEST-3', kind: 'UNREGISTERED' })
const result = (list, total = list.length) => ({ code: 0, data: { list, total } })

test('one student in two batches has distinct queue identities and page search does not alter server total', () => {
  const page = setup({})
  page.unreg.rows = [row('4'), row('5')]; page.unreg.pagination.total = 120
  assert.equal(new Set(page.unregisteredRows.map(item => item.queueKey)).size, 2)
  page.unreg.keyword = 'missing'
  assert.equal(page.unregisteredRows.length, 0)
  assert.equal(page.unreg.pagination.total, 120)
})

test('reason lookup keeps exact long student and batch IDs; another batch or student cannot supply evidence', async () => {
  const calls = []
  const page = setup({ getRegistrationDeferrals: async query => {
    calls.push(query)
    return result([{ ...row(), deferralId: '9007199254740999', status: 'APPROVED' }, { ...row('5'), deferralId: 'other-batch' }, { ...row(), studentId: '99', deferralId: 'other-student' }])
  } })
  page.unreg.rows = [row()]
  await page.openUnregisteredReason(row())
  assert.equal(calls[0].batchId, '4')
  assert.equal(calls[0].status, undefined)
  assert.equal(page.unregReason.deferrals.length, 1)
  assert.equal(page.unregReason.deferrals[0].deferralId, '9007199254740999')
  assert.equal(page.unregReason.exhausted, true)
})

test('reason response after switching objects cannot fill the newer drawer', async () => {
  const old = deferred()
  const page = setup({ getRegistrationDeferrals: query => query.batchId === '4' ? old.promise : Promise.resolve(result([{ ...row('5'), deferralId: 'new' }])) })
  page.unreg.rows = [row(), row('5')]
  const first = page.openUnregisteredReason(row())
  await page.openUnregisteredReason(row('5'))
  old.resolve(result([{ ...row(), deferralId: 'old' }]))
  await first
  assert.equal(page.unregReason.row.batchId, '5')
  assert.equal(page.unregReason.deferrals[0].deferralId, 'new')
})

test('identity change closes old personal evidence before its request finishes', async () => {
  const pending = deferred()
  const page = setup({ getRegistrationDeferrals: () => pending.promise })
  page.unreg.rows = [row()]
  const read = page.openUnregisteredReason(row())
  page.ctx = { userId: 'different-user' }; page.invalidateEligibilityContext()
  pending.resolve(result([{ ...row(), deferralId: 'private' }]))
  await read
  assert.equal(page.unregReason.visible, false)
  assert.equal(page.unregReason.row, null)
  assert.equal(page.unregReason.deferrals.length, 0)
})

test('403 in either formal code field clears the object and queue without a no-application claim', async () => {
  for (const response of [{ code: 403001 }, { code: 'NO_DATA_SCOPE' }, { code: 500, bizCode: 'NO_PERMISSION' }]) {
    const page = setup({ getRegistrationDeferrals: async () => response })
    page.unreg.rows = [row()]
    await page.openUnregisteredReason(row())
    assert.equal(page.unregReason.row, null)
    assert.equal(page.unreg.rows.length, 0)
    assert.match(page.unreg.error, /无权/)
  }
})

test('bounded lookups do not equate five unmatched pages with absence', async () => {
  let calls = 0
  const page = setup({ getRegistrationDeferrals: async () => { calls++; return result(Array.from({ length: 100 }, (_, index) => ({ batchId: '4', studentId: String(index), deferralId: String(index) })), 600) } })
  page.unreg.rows = [row()]
  await page.openUnregisteredReason(row())
  assert.equal(calls, 5)
  assert.equal(page.unregReason.exhausted, false)
  assert.equal(page.unregReason.deferrals.length, 0)
})

test('transport failure retains an explicit read error and performs no business command', async () => {
  let reads = 0
  const page = setup({ getRegistrationDeferrals: async () => { reads++; throw Error('连接超时') } })
  page.unreg.rows = [row()]
  await page.openUnregisteredReason(row())
  assert.equal(reads, 1)
  assert.match(page.unregReason.error, /连接超时/)
  assert.equal(page.unregReason.exhausted, false)
  assert.equal(page.unregReason.loading, false)
})
