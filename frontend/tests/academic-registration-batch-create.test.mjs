import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaRegistrationBatchListView.vue', import.meta.url), 'utf8')
const batchId = '9007199254740993001'
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const draft = (extra = {}) => ({ batchName: '本学年正式注册批次', registerType: 'ANNUAL', windowStart: '2026-09-01', windowEnd: '2026-09-20', open: false, ...extra })
const receipt = (body = draft(), extra = {}) => ({ code: 0, data: { batchId, batchName: body.batchName, registerType: body.registerType, status: body.open ? 'OPEN' : 'DRAFT', ...extra } })
function page(api = {}) {
  const writes = [], reads = [], notices = []
  const sandbox = { dependencies: { matchPermission, toast: { success: value => notices.push(value), error: value => notices.push(value) },
    academicAffairsApi: { createRegistrationBatch: async body => { writes.push(body); return receipt(body) },
      getRegistrationBatches: async query => { reads.push(query); return { code: 0, data: { list: [], total: 0 } } }, ...api } } }
  vm.runInNewContext(source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component ='), sandbox)
  const component = sandbox.component
  const state = { ...component.data(), ...component.methods, loading: false,
    ctx: { role: 'SCHOOL_ADMIN', permissionPatterns: ['academicAffairs.registration.manage', 'academicAffairs.registration.view'] },
    $route: { query: { type: 'ANNUAL', page: '3' } } }
  for (const [key, value] of Object.entries(component.computed)) {
    const get = typeof value === 'function' ? value : value.get
    Object.defineProperty(state, key, { get: () => get.call(state), ...(value.set ? { set: next => value.set.call(state, next) } : {}) })
  }
  return { state, component, writes, reads, notices }
}
function open(state, extra = {}) { state.toggleCreate(); state.draft = draft(extra) }

test('creation freezes all formal input fields and accepts the exact canonical DTO for DRAFT and OPEN', async () => {
  for (const isOpen of [false, true]) {
    const { state, writes, notices } = page(); open(state, { open: isOpen }); await state.createBatch()
    assert.equal(writes.length, 1); assert.deepEqual(JSON.parse(JSON.stringify(writes[0])), draft({ open: isOpen })); assert.equal(Object.isFrozen(writes[0]), true)
    assert.equal(state.createWrite.receipt.batchId, batchId); assert.equal(state.createWrite.receipt.status, isOpen ? 'OPEN' : 'DRAFT')
    assert.equal(state.createWrite.pending, null); assert.equal(state.showCreate, false); assert.equal(state.draft.batchName, '')
    assert.deepEqual(notices, [])
  }
})
test('a leaf route fixes the captured registration type even if a stale draft has a different type', async () => {
  const { state, writes } = page(); open(state, { registerType: 'ENROLL' }); await state.createBatch()
  assert.equal(writes[0].registerType, 'ANNUAL'); assert.equal(state.createWrite.receipt.registerType, 'ANNUAL')
})
test('view and archive.manage do not permit creation, including after a form was opened', async () => {
  for (const permissions of [['academicAffairs.registration.view'], ['academicAffairs.registration.archive.manage']]) {
    const { state, writes } = page(); open(state); state.ctx.permissionPatterns = permissions; await state.createBatch()
    assert.equal(writes.length, 0); assert.equal(state.createBlocked, true)
  }
})
test('a closed or old-context form cannot dispatch a creation command', async () => {
  for (const mutate of [s => { s.toggleCreate() }, s => { s.ctx.actor = 'other' }, s => { s.scopeVersion++ }, s => { s.$route.query.type = 'ENROLL' }]) {
    const { state, writes } = page(); open(state); mutate(state); await state.createBatch(); assert.equal(writes.length, 0)
  }
})
test('single submit guard blocks double clicks, closing the form and late date-picker input while creating', async () => {
  const reply = deferred(), writes = []
  const { state } = page({ createRegistrationBatch: body => { writes.push(body); return reply.promise } }); open(state)
  const pending = state.createBatch(); await state.createBatch(); state.toggleCreate(); state.windowRange = { start: '2099-01-01', end: '2099-01-02' }
  assert.equal(writes.length, 1); assert.equal(state.showCreate, true); assert.equal(state.draft.windowStart, '2026-09-01')
  reply.resolve(receipt()); await pending; assert.equal(state.creating, false)
})
test('a late successful creation cannot clear edited fields or a replacement form in the same context', async () => {
  for (const mutate of [s => { s.draft.batchName = '新的输入' }, s => { s.draft = draft({ batchName: '新的输入' }); s.createForm = { identity: s.batchActionIdentity(), context: s.contextKey } }]) {
    const reply = deferred(); const { state, reads, notices } = page({ createRegistrationBatch: () => reply.promise }); open(state)
    const pending = state.createBatch(); mutate(state); reply.resolve(receipt()); await pending
    assert.equal(state.draft.batchName, '新的输入'); assert.equal(state.showCreate, true); assert.equal(state.createWrite.receipt, null)
    assert.equal(state.createWrite.pending, null); assert.equal(reads.length, 0); assert.deepEqual(notices, [])
  }
})
test('late success from another identity, scope epoch, type or unmounted page cannot publish an old receipt or clear the new draft', async () => {
  for (const mutate of [s => { s.ctx.actor = 'other' }, s => { s.scopeVersion++ }, s => { s.$route.query.type = 'ENROLL' }, s => { s.disposed = true }]) {
    const reply = deferred(); const { state, reads } = page({ createRegistrationBatch: () => reply.promise }); open(state)
    const pending = state.createBatch(); mutate(state); state.draft = draft({ batchName: '新上下文输入' }); reply.resolve(receipt()); await pending
    assert.equal(state.draft.batchName, '新上下文输入'); assert.equal(state.createWrite.receipt, null); assert.equal(reads.length, 0)
  }
})
test('missing, nondecimal or numeric IDs and wrong name, type or status are unknown despite code zero', async () => {
  for (const extra of [{ batchId: undefined }, { batchId: '' }, { batchId: 123 }, { batchId: '0' }, { batchId: 'not-an-id' },
    { batchName: '另一批次' }, { registerType: 'ENROLL' }, { status: 'OPEN' }, { status: 'ARCHIVED' }]) {
    const { state, notices } = page({ createRegistrationBatch: async () => receipt(draft(), extra) }); open(state); await state.createBatch()
    assert.ok(state.createWrite.pending); assert.equal(state.createWrite.receipt, null); assert.equal(state.createBlocked, true)
    assert.equal(state.draft.batchName, draft().batchName); assert.match(state.createWrite.error, /结果未知/); assert.deepEqual(notices, [])
  }
})
test('503, network exceptions and missing envelopes preserve an unknown lock and never query a similar batch name', async () => {
  for (const response of [async () => ({ code: 503001 }), async () => { throw new Error('网络中断') }, async () => undefined]) {
    let writes = 0
    const { state, reads } = page({ createRegistrationBatch: () => { writes++; return response() } }); open(state)
    await state.createBatch(); await state.createBatch(); state.toggleCreate(); await state.createBatch()
    assert.equal(writes, 1); assert.equal(reads.length, 0); assert.ok(state.createWrite.pending); assert.equal(state.creating, false)
    assert.deepEqual(JSON.parse(JSON.stringify(state.draft)), draft())
  }
})
test('unknown creation remains locked after type and identity watchers run', async () => {
  const { state, component } = page({ createRegistrationBatch: async () => ({ code: 503001 }) }); open(state); await state.createBatch()
  state.$route.query.type = 'ENROLL'; component.watch['$route.query.type'].call(state)
  state.ctx.actor = 'other'; component.watch.ctx.handler.call(state)
  assert.ok(state.createWrite.pending); assert.equal(state.createBlocked, true); assert.equal(state.createWriteVisible, false)
})
test('a late unknown reply after changing identity still protects the pending creation without revealing the old draft', async () => {
  const reply = deferred(); const { state, component } = page({ createRegistrationBatch: () => reply.promise }); open(state)
  const pending = state.createBatch(); state.ctx.actor = 'other'; component.watch.ctx.handler.call(state)
  reply.resolve({ code: 503001 }); await pending
  assert.ok(state.createWrite.pending); assert.equal(state.createBlocked, true); assert.equal(state.createWriteVisible, false); assert.equal(state.draft.batchName, '')
})
test('403 clears only the corresponding private form and blocks further creation for the rejected identity', async () => {
  let writes = 0
  const { state } = page({ createRegistrationBatch: async () => { writes++; return { code: 403001, message: '无新建权限' } } })
  open(state); await state.createBatch()
  assert.equal(state.showCreate, false); assert.equal(state.createForm, null); assert.equal(state.draft.batchName, ''); assert.equal(state.draft.windowStart, '')
  assert.equal(state.createWrite.pending, null); assert.equal(state.createWrite.receipt, null); assert.equal(state.createWrite.target.body, undefined)
  assert.equal(state.createWrite.error, '无新建权限'); state.toggleCreate(); await state.createBatch(); assert.equal(writes, 1)
})
test('a late 403 from an old form cannot clear a new identity form', async () => {
  const reply = deferred(); const { state } = page({ createRegistrationBatch: () => reply.promise }); open(state)
  const pending = state.createBatch(); state.ctx.actor = 'other'; state.draft = draft({ batchName: '新身份草稿' })
  state.createForm = { identity: state.batchActionIdentity(), context: state.contextKey }; state.showCreate = true
  reply.resolve({ code: 403001 }); await pending
  assert.equal(state.draft.batchName, '新身份草稿'); assert.equal(state.showCreate, true); assert.equal(state.createWrite.pending, null)
})
test('409 preserves every entered field and displays its real rejection without automatically creating or searching', async () => {
  let writes = 0
  const { state, reads } = page({ createRegistrationBatch: async () => { writes++; return { code: 409001, message: '学期已归档' } } }); open(state)
  await state.createBatch(); assert.equal(writes, 1); assert.equal(reads.length, 0)
  assert.deepEqual(JSON.parse(JSON.stringify(state.draft)), draft()); assert.equal(state.showCreate, true); assert.equal(state.createWrite.pending, null)
  assert.equal(state.createWrite.error, '学期已归档')
})
test('success claims only returned canonical fields and explicitly leaves unreturned dates unverified', () => {
  assert.match(source, /注册窗口起止未在正式回执中返回/)
  assert.match(source, /不能根据同名或相似名称认定已经创建或未创建/)
})
