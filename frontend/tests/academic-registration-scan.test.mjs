import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import { matchPermission } from '../src/config/navPlan.js'
import { academicRouteState } from '../src/modules/academicAffairs/academicFlowContext.js'
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const receipt = (extra = {}) => ({ code: 0, data: { batchId: '101', marked: 2, skipped: 1, notified: 2, ...extra } })
function page(api = {}, file = '../src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue') {
  const source = readFileSync(new URL(file, import.meta.url), 'utf8')
  const writes = [], reads = [], notices = []
  const sandbox = { matchPermission, academicRouteState, toast: { success: value => notices.push(value), error: value => notices.push(value) },
    academicAffairsApi: { scanUnregistered: async id => { writes.push(id); return receipt() }, ...api } }
  for (const name of source.match(/components:\s*{([\s\S]*?)}/)[1].split(',').map(value => value.trim()).filter(Boolean)) sandbox[name] = {}
  vm.runInNewContext(source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?$/gm, '').replace('export default', 'component ='), sandbox)
  const component = sandbox.component
  const state = { ...component.data(), ...component.methods, batchId: '101', tab: 'unregistered',
    batches: [{ batchId: '101', batchName: '原批次', registerType: 'ANNUAL', status: 'OPEN', windowEnd: '2026-09-01' },
      { batchId: '202', batchName: '其他批次', registerType: 'ENROLL', status: 'OPEN', windowEnd: '2026-09-01' }],
    ctx: { currentRole: { roleCode: 'SCHOOL_ADMIN' }, permissionPatterns: ['academicAffairs.registration.unregistered.scan'] },
    $route: { query: {} }, $router: { replace() {} } }
  for (const [key, getter] of Object.entries(component.computed)) Object.defineProperty(state, key, { get: () => getter.call(state) })
  state.loadUnregistered = async () => { reads.push(state.batchId) }
  state.loadCurrentTab = () => {}
  return { state, component, source, writes, reads, notices }
}
const start = state => { state.askScan(); return state.doScan() }

test('scan: exact command permission is required; view, registration.manage and archive.manage cannot dispatch', async () => {
  for (const permission of ['view', 'manage', 'archive.manage', 'unregistered.view']) {
    const { state, writes } = page(); state.ctx.permissionPatterns = ['academicAffairs.registration.' + permission]
    await start(state); assert.equal(writes.length, 0)
  }
})
test('scan: closed batch, unknown type, missing batch and wrong tab cannot dispatch', async () => {
  for (const mutate of [s => { s.batches[0].status = 'CLOSED' }, s => { s.batches[0].registerType = 'UNKNOWN' },
    s => { s.batchId = 'missing' }, s => { s.tab = 'archive' }]) {
    const { state, writes } = page(); mutate(state); await start(state); assert.equal(writes.length, 0)
  }
})
test('scan: confirmation explicitly describes the whole batch and different main-ledger effects', () => {
  for (const type of ['ENROLL', 'ANNUAL', 'SEMESTER']) {
    const { state } = page(); state.batches[0].registerType = type; state.askScan()
    assert.match(state.scanConfirm.message, /101.*全校.*本页外/)
    assert.match(state.scanConfirm.message, type === 'ENROLL' ? /正式入口标记学籍主档/ : /不倒退学籍主档/)
  }
})
test('scan: batch, identity and scope-epoch changes invalidate a waiting confirmation', async () => {
  for (const mutate of [s => { s.batchId = '202'; s.onBatchChange() }, s => { s.ctx.actor = 'other'; s.invalidateEligibilityContext() },
    s => { s.eligScopeVersion++ }]) {
    const { state, writes } = page(); state.askScan(); mutate(state); await state.doScan(); assert.equal(writes.length, 0)
  }
})
test('scan: command freezes the original exact batch and rejects double clicks', async () => {
  const reply = deferred(), writes = []
  const { state } = page({ scanUnregistered: id => { writes.push(id); return reply.promise } })
  const pending = start(state); await state.doScan(); state.askScan(); await state.doScan()
  assert.deepEqual(writes, ['101']); assert.equal(state.scanning, true)
  reply.resolve(receipt()); await pending
  assert.equal(state.scanOperation.receipt.batchId, '101'); assert.equal(state.scanning, false)
})
test('scan: late success after new batch, identity, scope epoch or unmount cannot publish old results or reload new queue', async () => {
  for (const mutate of [s => { s.batchId = '202'; s.onBatchChange() }, s => { s.ctx.actor = 'other'; s.invalidateEligibilityContext() },
    s => { s.eligScopeVersion++ }, s => { s.eligDisposed = true }]) {
    const reply = deferred(); const { state, reads, notices } = page({ scanUnregistered: () => reply.promise })
    const pending = start(state); mutate(state); reply.resolve(receipt()); await pending
    assert.equal(state.scanOperation.receipt, null); assert.deepEqual(reads, []); assert.deepEqual(notices, [])
  }
})
test('scan: 503, network exception and malformed receipts stay unknown and cannot automatically rescan', async () => {
  const replies = [async () => ({ code: 503001 }), async () => { throw new Error('network') },
    async () => receipt({ batchId: 'wrong' }), async () => receipt({ marked: -1 }), async () => receipt({ notified: 3 }),
    async () => receipt({ skipped: '1' }), async () => ({ code: 0, data: {} }), async () => undefined]
  for (const response of replies) {
    let writes = 0; const { state } = page({ scanUnregistered: () => { writes++; return response() } })
    await start(state); assert.equal(state.scanOperation.pending.batchId, '101'); assert.equal(state.scanOperation.receipt, null)
    await state.loadUnregistered(); await start(state); assert.equal(writes, 1); assert.equal(state.scanning, false)
  }
})
test('scan: unknown result survives batch and tab changes and old-identity return', async () => {
  const { state } = page({ scanUnregistered: async () => ({ code: 503001 }) }); await start(state)
  state.batchId = '202'; state.onBatchChange(); state.switchTab('archive'); state.switchTab('unregistered')
  state.batchId = '101'; state.onBatchChange()
  assert.equal(state.scanOperation.pending.batchId, '101'); assert.equal(state.canScanUnregistered, false)
  assert.equal(state.scanTargetCurrent(state.scanOperation.target), false)
})
test('scan: a late uncertain response remains locked after leaving its original context', async () => {
  const reply = deferred(); const { state } = page({ scanUnregistered: () => reply.promise })
  const pending = start(state); state.batchId = '202'; state.onBatchChange(); reply.resolve({ code: 503001 }); await pending
  assert.equal(state.scanOperation.pending.batchId, '101'); assert.equal(state.canScanUnregistered, false)
  assert.equal(state.scanOperation.error, '')
})
test('scan: 403 clears the current sensitive queue, invalidates reads and blocks the denied identity', async () => {
  const { state } = page({ scanUnregistered: async () => ({ code: 403001, message: '无数据范围' }) })
  state.unreg.rows = [{ studentId: 'secret' }]; state.unreg.pagination.total = 1
  await start(state); assert.deepEqual(Array.from(state.unreg.rows), []); assert.equal(state.unreg.pagination.total, 0)
  assert.equal(state.queueVersions.unreg, 1); assert.equal(state.scanOperation.pending, null)
  assert.equal(state.canScanUnregistered, false); assert.equal(state.unreg.error, '无数据范围')
})
test('scan: a late old-identity 403 does not clear new-identity data', async () => {
  const reply = deferred(); const { state } = page({ scanUnregistered: () => reply.promise })
  const pending = start(state); state.ctx.actor = 'other'; state.invalidateEligibilityContext(); state.unreg.rows = [{ studentId: 'new' }]
  reply.resolve({ code: 403001 }); await pending
  assert.equal(state.unreg.rows[0].studentId, 'new'); assert.equal(state.scanOperation.error, '')
})
test('scan: 409 preserves the exact rejection, refreshes only the original queue and does not auto-retry', async () => {
  const { state, reads, notices } = page({ scanUnregistered: async () => ({ code: 409001, message: '批次已关闭' }) })
  await start(state); assert.equal(state.scanOperation.error, '批次已关闭'); assert.equal(state.scanOperation.pending, null)
  assert.deepEqual(reads, ['101']); assert.deepEqual(notices, []); assert.equal(state.scanConfirm.target, null)
})
test('scan: valid receipt preserves marked, deferral-skipped and created-todo counts without inventing delivery', async () => {
  const { state, source, notices } = page(); await start(state)
  assert.deepEqual(JSON.parse(JSON.stringify(state.scanOperation.receipt)), receipt().data)
  assert.match(source, /标记未注册记录.*receipt.marked/); assert.match(source, /新增辅导员待办.*receipt.notified/)
  assert.doesNotMatch(source, /通知辅导员 \$\{res.data.notified\} 人/); assert.deepEqual(notices, [])
})
