import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaRegistrationBatchListView.vue', import.meta.url), 'utf8')
const batchId = '9007199254740993001'
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const batch = (extra = {}) => ({ batchId, batchName: '原注册批次', registerType: 'ANNUAL', status: 'OPEN', ...extra })
const list = (rows, total = rows.length) => ({ code: 0, data: { list: rows, total } })
function page(api = {}) {
  const writes = [], reads = [], notices = [], destinations = []
  let official = batch()
  const sandbox = { dependencies: { matchPermission, toast: { success: value => notices.push(value), error: value => notices.push(value) },
    academicAffairsApi: {
      closeRegistrationBatch: async id => { writes.push(['close', id]); official = batch({ status: 'CLOSED' }); return { code: 0, data: official } },
      archiveRegistrationBatch: async id => { writes.push(['archive', id]); official = batch({ status: 'ARCHIVED' }); return { code: 0, data: official } },
      getRegistrationBatches: async query => { reads.push(query); return list([official]) },
      ...api
    } } }
  vm.runInNewContext(source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component ='), sandbox)
  const component = sandbox.component
  const state = { ...component.data(), ...component.methods, rows: [batch()], loading: false,
    ctx: { role: 'SCHOOL_ADMIN', permissionPatterns: ['academicAffairs.registration.archive.manage', 'academicAffairs.registration.view'] },
    $route: { query: { type: 'ANNUAL', page: '3' } }, $router: { replace: value => destinations.push(value), push: value => destinations.push(value) } }
  for (const [key, value] of Object.entries(component.computed)) Object.defineProperty(state, key, { get: () => (typeof value === 'function' ? value : value.get).call(state) })
  return { state, component, writes, reads, notices, destinations }
}
function ask(state, kind = 'close') {
  if (kind === 'archive') { state.rows[0].status = 'CLOSED'; state.askArchive(state.rows[0]) }
  else state.askClose(state.rows[0])
}
async function dispatch(state, kind = 'close') { ask(state, kind); await state.onConfirm() }

test('close and archive require their exact returned batch ID and terminal status', async () => {
  for (const kind of ['close', 'archive']) {
    for (const data of [{ batchId: 'different', status: kind === 'close' ? 'CLOSED' : 'ARCHIVED' },
      batch({ status: 'OPEN' }), undefined]) {
      const { state, notices } = page({ [kind === 'close' ? 'closeRegistrationBatch' : 'archiveRegistrationBatch']: async () => ({ code: 0, data }) })
      await dispatch(state, kind)
      assert.equal(state.batchWrite.pending.row.batchId, batchId); assert.equal(state.batchWrite.receipt, null)
      assert.match(state.batchWrite.error, /结果未知/); assert.deepEqual(notices, [])
    }
  }
})
test('valid close and archive receipts retain exact IDs and formal states without a global stale toast', async () => {
  for (const kind of ['close', 'archive']) {
    const { state, writes, notices } = page(); await dispatch(state, kind)
    assert.deepEqual(writes, [[kind, batchId]]); assert.equal(state.batchWrite.pending, null)
    assert.equal(state.batchWrite.receipt.batchId, batchId)
    assert.equal(state.batchWrite.receipt.status, kind === 'close' ? 'CLOSED' : 'ARCHIVED'); assert.deepEqual(notices, [])
  }
})
test('a frozen close object dispatches only once even when the row and confirmation are clicked again', async () => {
  const reply = deferred(), writes = []
  const { state } = page({ closeRegistrationBatch: id => { writes.push(id); return reply.promise } })
  ask(state); state.rows[0].batchId = 'changed'
  const pending = state.onConfirm(); await state.onConfirm(); state.askClose(state.rows[0]); await state.onConfirm()
  assert.deepEqual(writes, [batchId]); reply.resolve({ code: 0, data: batch({ status: 'CLOSED' }) }); await pending
})
test('view-only and registration.manage identities cannot close or archive, including after opening a confirmation', async () => {
  for (const permissions of [['academicAffairs.registration.view'], ['academicAffairs.registration.manage']]) {
    const { state, writes } = page(); ask(state); state.ctx.permissionPatterns = permissions
    await state.onConfirm(); await dispatch(state); await dispatch(state, 'archive'); assert.deepEqual(writes, [])
  }
})
test('a different identity, context epoch or type cannot dispatch an old confirmation', async () => {
  for (const mutate of [s => { s.ctx.actor = 'other' }, s => { s.scopeVersion++ }, s => { s.$route.query.type = 'ENROLL' }]) {
    const { state, writes } = page(); ask(state); mutate(state); await state.onConfirm(); assert.deepEqual(writes, [])
  }
})
test('403 clears the old batch data and confirmation and prevents redispatch for the denied identity', async () => {
  let writes = 0
  const { state } = page({ closeRegistrationBatch: async () => { writes++; return { code: 403001, message: '批次权限已撤回' } } })
  state.pagination.total = 1; state.showCreate = true
  const row = state.rows[0]; await dispatch(state)
  assert.equal(state.rows.length, 0); assert.equal(state.pagination.total, 0); assert.equal(state.loading, false)
  assert.equal(state.pendingAction, null); assert.equal(state.confirm.visible, false); assert.equal(state.showCreate, false)
  assert.equal(state.batchWrite.pending, null); assert.equal(state.batchWrite.receipt, null)
  assert.equal(state.error, '批次权限已撤回'); state.askClose(row); await state.onConfirm(); assert.equal(writes, 1)
})
test('403 invalidates an in-flight old list read so it cannot restore rejected batch data', async () => {
  const read = deferred()
  const { state } = page({ getRegistrationBatches: () => read.promise, closeRegistrationBatch: async () => ({ code: 403001 }) })
  const row = state.rows[0]; const pending = state.load(); state.askClose(row); await state.onConfirm()
  read.resolve(list([batch()])); await pending
  assert.equal(state.rows.length, 0); assert.equal(state.pagination.total, 0)
})
test('late old-identity success or denial cannot change new-identity rows or display an old receipt', async () => {
  for (const response of [{ code: 0, data: batch({ status: 'CLOSED' }) }, { code: 403001 }]) {
    const reply = deferred(); const { state } = page({ closeRegistrationBatch: () => reply.promise })
    ask(state); const pending = state.onConfirm(); state.ctx.actor = 'other'; state.scopeVersion++
    state.rows = [batch({ batchId: 'new' })]; reply.resolve(response); await pending
    assert.equal(state.rows[0].batchId, 'new'); assert.equal(state.batchWrite.receipt, null); assert.equal(state.batchWriteVisible, false)
  }
})
test('503, network exception and missing receipts hold the unknown lock across explicit retry attempts', async () => {
  for (const response of [async () => ({ code: 503001 }), async () => { throw new Error('network') }, async () => undefined]) {
    let writes = 0
    const { state } = page({ closeRegistrationBatch: () => { writes++; return response() } })
    await dispatch(state); const row = state.rows[0]; state.askClose(row); await state.onConfirm()
    assert.equal(writes, 1); assert.equal(state.batchWrite.pending.row.batchId, batchId); assert.equal(state.busyId, '')
  }
})
test('unknown writes stay locked across route type or identity changes, including late unknown responses', async () => {
  const reply = deferred(); const { state } = page({ closeRegistrationBatch: () => reply.promise })
  ask(state); const pending = state.onConfirm(); state.ctx.actor = 'other'; state.scopeVersion++
  reply.resolve({ code: 503001 }); await pending
  state.$route.query.type = 'ENROLL'; assert.equal(state.batchActionsBlocked, true); assert.equal(state.batchWriteVisible, false)
  delete state.ctx.actor; state.$route.query.type = 'ANNUAL'
  assert.equal(state.batchWrite.pending.row.batchId, batchId); assert.equal(state.batchActionsBlocked, true)
})
test('409 preserves its real rejection and refreshes the current batch list without automatically retrying', async () => {
  let writes = 0
  const { state, reads } = page({ closeRegistrationBatch: async () => { writes++; return { code: 409001, message: '仅开放中批次可关闭，当前状态 CLOSED' } } })
  await dispatch(state); assert.equal(writes, 1); assert.equal(reads.length, 1); assert.equal(state.batchWrite.pending, null)
  assert.equal(state.batchWrite.error, '仅开放中批次可关闭，当前状态 CLOSED'); assert.equal(state.pendingAction, null)
})
test('formal list read finds the exact original ID outside current filters and keeps unknown even at the expected state', async () => {
  const reads = []
  const { state, destinations, notices } = page({ closeRegistrationBatch: async () => ({ code: 503001 }),
    getRegistrationBatches: async query => { reads.push(query); return query.page === 1 ? list([batch({ batchId: 'other' })], 101) : list([batch({ status: 'CLOSED' })], 101) } })
  state.pagination.page = 3; await dispatch(state); await state.readBatchOutcome()
  assert.deepEqual(JSON.parse(JSON.stringify(reads)), [{ page: 1, pageSize: 100 }, { page: 2, pageSize: 100 }])
  assert.equal(state.batchWrite.readRow.batchId, batchId); assert.equal(state.batchWrite.readRow.status, 'CLOSED')
  assert.equal(state.batchWrite.pending.row.batchId, batchId); assert.equal(state.batchWrite.receipt, null); assert.equal(state.batchActionsBlocked, true)
  assert.equal(state.pagination.page, 3); assert.equal(state.$route.query.type, 'ANNUAL'); assert.deepEqual(destinations, []); assert.deepEqual(notices, [])
})
test('formal reads require the existing view permission and original identity without inferring access from archive.manage', async () => {
  const { state, reads } = page({ closeRegistrationBatch: async () => ({ code: 503001 }) }); await dispatch(state)
  state.ctx.permissionPatterns = ['academicAffairs.registration.archive.manage']; await state.readBatchOutcome()
  state.ctx.permissionPatterns = ['academicAffairs.registration.archive.manage', 'academicAffairs.registration.view']; state.ctx.actor = 'other'
  await state.readBatchOutcome(); assert.equal(reads.length, 0)
})
test('formal lookup is capped at five pages and absence cannot prove a command was not executed', async () => {
  let reads = 0
  const { state } = page({ closeRegistrationBatch: async () => ({ code: 503001 }), getRegistrationBatches: async () => { reads++; return list([batch({ batchId: 'other' })], 1000000) } })
  await dispatch(state); await state.readBatchOutcome()
  assert.equal(reads, 5); assert.match(state.batchWrite.readError, /不能据此认定操作未执行/); assert.equal(state.batchWrite.pending.row.batchId, batchId)
})
test('denied, malformed or failed formal reads clear any old read result while keeping the original write unknown', async () => {
  for (const response of [async () => ({ code: 403001, message: '只读范围已变' }), async () => ({ code: 0, data: {} }),
    async () => list([batch({ status: 'unexpected' })]), async () => { throw new Error('网络中断') }]) {
    const { state } = page({ closeRegistrationBatch: async () => ({ code: 503001 }), getRegistrationBatches: response })
    await dispatch(state); state.batchWrite.readRow = batch({ status: 'CLOSED' }); await state.readBatchOutcome()
    assert.equal(state.batchWrite.readRow, null); assert.equal(state.batchWrite.pending.row.batchId, batchId)
    assert.ok(state.batchWrite.readError); assert.equal(state.batchWrite.checking, false)
  }
})
test('a late formal read cannot publish another identity or scope result', async () => {
  const reply = deferred(); const { state } = page({ closeRegistrationBatch: async () => ({ code: 503001 }), getRegistrationBatches: () => reply.promise })
  await dispatch(state); const pending = state.readBatchOutcome(); state.ctx.actor = 'other'; state.scopeVersion++
  reply.resolve(list([batch({ status: 'CLOSED' })])); await pending
  assert.equal(state.batchWrite.readRow, null); assert.equal(state.batchWrite.pending.row.batchId, batchId)
})
