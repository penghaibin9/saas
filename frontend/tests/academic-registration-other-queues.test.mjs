import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue', import.meta.url), 'utf8')
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const result = id => ({ code: 0, data: { list: [{ batchId: id, marker: id }], total: 1 } })
function page(api) {
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?$/gm, '').replace('export default', 'component =')
  const sandbox = { academicAffairsApi: api }
  for (const name of source.match(/components:\s*{([\s\S]*?)}/)[1].split(',').map(x => x.trim()).filter(Boolean)) sandbox[name] = {}
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const state = { ...component.data(), ...component.methods, batchId: '1', ctx: { userId: 'teacher' } }
  Object.defineProperty(state, 'eligibilityContextKey', { get: () => component.computed.eligibilityContextKey.call(state) })
  return { state, component }
}
const queues = [
  ['unreg', 'loadUnregistered', 'getUnregisteredStudents'],
  ['defer', 'loadDeferrals', 'getRegistrationDeferrals'],
  ['exc', 'loadExceptions', 'getRegistrationExceptions'],
  ['archive', 'loadArchive', 'getArchivedRegistrationBatches'],
]
for (const [key, method, endpoint] of queues) {
  test(`${key}: slower old page cannot replace a newer queue or release its loading state`, async () => {
    const old = deferred(), fresh = deferred()
    const api = { [endpoint]: q => q.page === 1 ? old.promise : fresh.promise,
      getRegistrationArchiveDetail: async () => ({ code: 0, data: { stats: { registered: 0, total: 0 } } }) }
    const { state } = page(api)
    const first = state[method](); state[key].pagination.page = 2; const second = state[method]()
    old.resolve(result('old')); await first
    assert.equal(state[key].loading, true)
    assert.equal(state[key].rows.length, 0)
    fresh.resolve(result('new')); await second
    assert.equal(state[key].rows[0].marker, 'new')
    assert.equal(state[key].loading, false)
  })
  test(`${key}: context changes and unmount discard delayed personal data`, async () => {
    for (const change of [(s) => { s.batchId = '2'; s.invalidateEligibilityContext() },
      (s, c) => c.beforeUnmount.call(s)]) {
      const wait = deferred(), { state, component } = page({ [endpoint]: () => wait.promise })
      const pending = state[method](); change(state, component)
      wait.resolve(result('sensitive')); await pending
      assert.equal(state[key].rows.length, 0)
    }
  })
  test(`${key}: denied reads and transport failures clear prior objects`, async () => {
    for (const response of [async () => ({ code: 403001, message: '无权读取' }), async () => { throw new Error('连接断开') }]) {
      const { state } = page({ [endpoint]: response })
      state[key].rows = [{ marker: 'prior' }]; state[key].pagination.total = 1
      await state[method]()
      assert.equal(state[key].rows.length, 0)
      assert.equal(state[key].pagination.total, 0)
      assert.ok(state[key].error)
      assert.equal(state[key].loading, false)
    }
  })
}
test('late archive detail fan-out cannot refill another page', async () => {
  const oldDetail = deferred()
  const { state } = page({ getArchivedRegistrationBatches: async q => result(q.page === 1 ? 'old' : 'new'),
    getRegistrationArchiveDetail: id => id === 'old' ? oldDetail.promise : Promise.resolve({ code: 0, data: { stats: { registered: 2, total: 3 } } }) })
  const first = state.loadArchive(); await Promise.resolve(); await Promise.resolve()
  state.archive.pagination.page = 2; await state.loadArchive()
  oldDetail.resolve({ code: 0, data: { stats: { registered: 999, total: 999 } } }); await first
  assert.equal(state.archive.rows[0].marker, 'new')
  assert.equal(state.archive.rows[0].registered, 2)
})
test('archive statistics unavailable is explicit and not a zero or completed count', async () => {
  const { state } = page({ getArchivedRegistrationBatches: async () => result('archive'),
    getRegistrationArchiveDetail: async () => { throw new Error('timeout') } })
  await state.loadArchive()
  assert.equal(state.archive.rows[0].registered, null)
  assert.match(state.archive.rows[0].detailError, /读取失败/)
  assert.equal(state.archive.loading, false)
})
test('changing scope closes old action and export dialogs before another queue is shown', () => {
  const { state } = page({})
  state.pendingAction = { kind: 'deferralApprove', row: { deferralId: 'old' } }
  state.confirm.visible = true; state.deferRejectDialog.visible = true; state.resolveDialog.visible = true
  state.exportDialog = { visible: true, action: () => { throw new Error('old scope export') } }
  state.invalidateEligibilityContext()
  assert.equal(state.pendingAction, null)
  assert.equal(state.confirm.visible || state.deferRejectDialog.visible || state.resolveDialog.visible || state.exportDialog.visible, false)
  assert.equal(state.exportDialog.action, null)
})
