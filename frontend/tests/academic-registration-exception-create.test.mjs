import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'
import { academicRouteState } from '../src/modules/academicAffairs/academicFlowContext.js'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue', import.meta.url), 'utf8')
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const record = (extra = {}) => ({ exceptionId: '9007199254740993001', batchId: '101', studentId: '9007199254740993002',
  exceptionType: 'OTHER', description: '材料待补齐', status: 'OPEN', ...extra })
function page(api = {}) {
  const writes = [], reads = [], notices = [], reloads = []
  const sandbox = { academicRouteState, matchPermission, toast: { error() {}, success: value => notices.push(value) },
    academicAffairsApi: {
      createRegistrationException: async (...args) => { writes.push(args); return { code: 0, data: record() } },
      getRegistrationExceptions: async query => { reads.push(query); return { code: 0, data: { list: [record()], total: 1 } } },
      ...api
    } }
  for (const name of source.match(/components:\s*{([\s\S]*?)}/)[1].split(',').map(value => value.trim()).filter(Boolean)) sandbox[name] = {}
  vm.runInNewContext(source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?$/gm, '').replace('export default', 'component ='), sandbox)
  const component = sandbox.component
  const state = { ...component.data(), ...component.methods, batchId: '101', tab: 'exception',
    ctx: { permissionPatterns: ['academicAffairs.registration.exception.create', 'academicAffairs.registration.exception.view'] } }
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(state, name, { get: () => getter.call(state) })
  state.loadCurrentTab = () => {}; state.loadExceptions = () => { reloads.push(state.batchId) }
  state.openExceptionCreate()
  Object.assign(state.excDrawer, { studentId: record().studentId, description: record().description })
  return { state, writes, reads, notices, reloads, component }
}

test('one frozen command reads its exact official ID from the original batch without a status filter', async () => {
  const { state, writes, reads, notices } = page()
  state.exc.status = 'RESOLVED'
  await state.submitExceptionCreate()
  assert.equal(writes.length, 1); assert.equal(writes[0][0], '101')
  assert.equal(writes[0][1].studentId, record().studentId); assert.equal(writes[0][1].description, record().description)
  assert.deepEqual(JSON.parse(JSON.stringify(reads)), [{ batchId: '101', page: 1, pageSize: 100 }])
  assert.equal(state.excCreateReceipt.exceptionId, record().exceptionId); assert.equal(state.excCreateReceipt.status, 'OPEN')
  assert.equal(state.excPendingCreate, null); assert.equal(state.excDrawer.visible, false); assert.equal(notices.length, 0)
})

test('a double submit and close click while writing cannot issue a second command', async () => {
  const reply = deferred(), writes = []
  const { state } = page({ createRegistrationException: (...args) => { writes.push(args); return reply.promise } })
  const pending = state.submitExceptionCreate(); await state.submitExceptionCreate(); state.closeExceptionCreate()
  assert.equal(writes.length, 1); assert.equal(state.excDrawer.visible, true)
  reply.resolve({ code: 0, data: record() }); await pending
  assert.equal(state.excCreating, false); assert.equal(state.excCreateReceipt.exceptionId, record().exceptionId)
})

test('a changed batch or identity before submission cannot reuse an old draft', async () => {
  for (const change of [state => { state.batchId = '202' }, state => { state.ctx.currentRole = 'other-role' }]) {
    const { state, writes } = page(); change(state); await state.submitExceptionCreate()
    assert.equal(writes.length, 0); assert.equal(state.excDrawer.description, record().description)
  }
})

test('a late original-batch reply does not close or reload a different draft', async () => {
  const reply = deferred(), { state, notices, reloads } = page({ createRegistrationException: () => reply.promise })
  const pending = state.submitExceptionCreate()
  state.batchId = '202'; state.onBatchChange()
  const otherDrawer = { visible: true, studentId: 'other', description: '另一份未提交说明', saving: false }
  state.excDrawer = otherDrawer
  reply.resolve({ code: 0, data: record() }); await pending
  assert.equal(state.excDrawer, otherDrawer); assert.equal(otherDrawer.visible, true); assert.equal(otherDrawer.description, '另一份未提交说明')
  assert.equal(notices.length, 0); assert.equal(reloads.length, 0); assert.equal(state.excCreateReceipt.batchId, '101')
})

test('a late identity response cannot fetch or display the previous identity result', async () => {
  const reply = deferred(), { state, reads, notices } = page({ createRegistrationException: () => reply.promise })
  const pending = state.submitExceptionCreate(); state.ctx.currentRole = 'another'; state.invalidateEligibilityContext()
  reply.resolve({ code: 0, data: record() }); await pending
  assert.equal(reads.length, 0); assert.equal(notices.length, 0); assert.equal(state.excCreateReceipt, null)
  assert.ok(state.excPendingCreate); assert.equal(state.canReadExceptionCreate(), false); assert.equal(state.canCreateRegistrationException(), false)
})

test('403 clears original sensitive content and invalidates older queue replies', async () => {
  const { state } = page({ createRegistrationException: async () => ({ code: 403001, message: '无权限' }) })
  state.exc.rows = [record()]; const version = state.queueVersions.exc
  await state.submitExceptionCreate()
  assert.equal(state.exc.rows.length, 0); assert.equal(state.excDrawer.studentId, ''); assert.equal(state.excDrawer.description, '')
  assert.equal(state.excDrawer.visible, false); assert.equal(state.excCreateReceipt, null)
  assert.ok(state.queueVersions.exc > version); assert.equal(state.canCreateRegistrationException(), false)
})

test('an old-batch 403 cannot clear a later draft or its queue', async () => {
  const reply = deferred(), { state } = page({ createRegistrationException: () => reply.promise })
  const pending = state.submitExceptionCreate(); state.batchId = '202'; state.onBatchChange()
  const otherDrawer = { visible: true, studentId: 'other', description: '另一份未提交说明', saving: false }
  state.excDrawer = otherDrawer; state.exc.rows = [record({ batchId: '202' })]
  reply.resolve({ code: 403001 }); await pending
  assert.equal(state.excDrawer, otherDrawer); assert.equal(state.exc.rows.length, 1)
  assert.equal(state.excCreateError, '')
})

test('409 preserves the original explanation and does not fabricate a success receipt', async () => {
  const { state, reads } = page({ createRegistrationException: async () => ({ code: 409001, message: '业务条件已变化' }) })
  await state.submitExceptionCreate()
  assert.equal(state.excDrawer.visible, true); assert.equal(state.excDrawer.description, record().description)
  assert.equal(state.excDrawer.formError, '业务条件已变化'); assert.equal(state.excCreateReceipt, null); assert.equal(reads.length, 0)
})

test('timeouts, network failures, absent IDs and mismatched receipts block replay across tabs and batches', async () => {
  for (const response of [() => ({ code: 503001 }), () => { throw new Error('network') },
    () => ({ code: 0, data: {} }), () => ({ code: 0, data: record({ studentId: 'wrong' }) }),
    () => ({ code: 0, data: record({ status: 'UNKNOWN' }) })]) {
    let writes = 0
    const { state, reads } = page({ createRegistrationException: async () => { writes++; return response() } })
    await state.submitExceptionCreate(); state.switchTab('deferral'); state.switchTab('exception')
    state.batchId = '202'; state.onBatchChange(); state.openExceptionCreate(); await state.submitExceptionCreate()
    assert.equal(writes, 1); assert.ok(state.excPendingCreate); assert.equal(state.excCreateReceipt, null)
    assert.equal(state.excPendingCreate.batchId, '101'); assert.equal(reads.length, 0)
  }
})

test('official readback can observe a later resolved state without inventing OPEN', async () => {
  const { state } = page({ getRegistrationExceptions: async () => ({ code: 0, data: { list: [record({ status: 'RESOLVED' })], total: 1 } }) })
  await state.submitExceptionCreate(); assert.equal(state.excCreateReceipt.status, 'RESOLVED')
})

test('readback is limited to five pages and not-found remains locked until a later exact-ID GET', async () => {
  let reads = 0, found = false
  const otherRows = Array.from({ length: 100 }, (_, index) => record({ exceptionId: String(index) }))
  const { state, writes } = page({ getRegistrationExceptions: async () => {
    reads++; return { code: 0, data: { list: found ? [record()] : otherRows, total: 10000 } }
  } })
  await state.submitExceptionCreate()
  assert.equal(reads, 5); assert.equal(state.excCreateReceipt, null); assert.ok(state.excPendingCreate.exceptionId)
  assert.match(state.excPendingCreate.message, /不能判断未创建/)
  await state.submitExceptionCreate(); assert.equal(writes.length, 1)
  found = true; assert.equal(await state.checkExceptionCreateReceipt(), true)
  assert.equal(reads, 6); assert.equal(writes.length, 1); assert.equal(state.excPendingCreate, null)
})

test('read errors, wrong identity evidence and unknown formal statuses do not release the pending write', async () => {
  for (const read of [async () => { throw new Error('timeout') }, async () => ({ code: 503001 }),
    async () => ({ code: 0, data: { list: [record({ batchId: '202' })], total: 1 } }),
    async () => ({ code: 0, data: { list: [record({ status: 'UNKNOWN' })], total: 1 } })]) {
    const { state } = page({ getRegistrationExceptions: read }); await state.submitExceptionCreate()
    assert.ok(state.excPendingCreate); assert.equal(state.excCreateReceipt, null); assert.equal(state.excReceiptChecking, false)
  }
})

test('a readback 403 clears the draft but retains the known ID lock for later authorized verification', async () => {
  let authorized = false
  const { state } = page({ getRegistrationExceptions: async () => authorized
    ? { code: 0, data: { list: [record()], total: 1 } } : { code: 403001 } })
  state.exc.rows = [record()]; await state.submitExceptionCreate()
  assert.equal(state.excDrawer.description, ''); assert.equal(state.exc.rows.length, 0)
  assert.equal(state.excPendingCreate.exceptionId, record().exceptionId); assert.equal(state.excPendingCreate.denied, true)
  assert.equal(state.excCreateReceipt, null); assert.equal(state.canCreateRegistrationException(), false)
  authorized = true; await state.checkExceptionCreateReceipt()
  assert.equal(state.excPendingCreate, null); assert.equal(state.canCreateRegistrationException(), true)
})

test('readback after unmount cannot repopulate an old component', async () => {
  const reply = deferred(), { state, component } = page({ getRegistrationExceptions: () => reply.promise })
  const pending = state.submitExceptionCreate(); await Promise.resolve(); component.beforeUnmount.call(state)
  reply.resolve({ code: 0, data: { list: [record()], total: 1 } }); await pending
  assert.equal(state.excCreateReceipt, null)
})

test('creation and formal readback respect their existing separate permissions', async () => {
  const { state, writes, reads } = page()
  state.ctx.permissionPatterns = ['academicAffairs.registration.exception.view']; await state.submitExceptionCreate()
  assert.equal(writes.length, 0)
  state.ctx.permissionPatterns = ['academicAffairs.registration.exception.create']; state.openExceptionCreate()
  Object.assign(state.excDrawer, { studentId: record().studentId, description: record().description })
  await state.submitExceptionCreate()
  assert.equal(writes.length, 1); assert.equal(reads.length, 0); assert.ok(state.excPendingCreate)
})
