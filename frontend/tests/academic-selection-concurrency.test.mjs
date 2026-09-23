import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import * as flow from '../src/modules/academicAffairs/academicFlowContext.js'
import { isDeniedResult } from '../src/modules/academicAffairs/components/parallel-a/resultState.js'

const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const batch = id => ({ batchId: id, batchName: `批次${id}`, status: 'DRAFT' })
const ok = data => ({ code: 0, data })

test('switching batches clears previous courses before the new formal header returns', async () => {
  const response = deferred()
  const { state } = mount(undefined, { getBatch: () => response.promise })
  state.current=batch('old');state.courses=[{selectionCourseId:'old-course'}];state.stats={selectedCount:4};state.rounds=[{roundId:'old-round'}]
  const loading=state.select(batch('new'))
  assert.equal(state.courses.length,0);assert.equal(state.rounds.length,0);assert.equal(state.stats,null);assert.equal(state.detailLoading,true)
  response.resolve({code:503,message:'新批次读取失败'});await loading
  assert.equal(state.detailLoading,false);assert.equal(state.courses.length,0)
  assert.equal(state.detailError,'新批次读取失败')
})

test('batch creation requires explicit scope and opens its formal result instead of the old batch', async () => {
  const writes = []
  const { state } = mount(undefined, { createBatch: async body => { writes.push(body); return ok(batch('new')) } })
  state.current = batch('old')
  state.form.batchName = '限定班级选课'; state.form.termId = '52'
  await state.submitCreate()
  assert.equal(writes.length, 0)
  assert.equal(state.formError, '请选择适用班级')
  state.form.classIds = ['9007199254740993']
  await state.submitCreate()
  assert.equal(writes[0].applyScope.classIds[0], '9007199254740993')
  assert.equal(state.current.batchId, 'new')
  assert.equal(state.saving, false)
})

test('explicit school scope does not retain previously selected classes', async () => {
  const writes = []
  const { state } = mount(undefined, { createBatch: async body => { writes.push(body); return ok(batch('new')) } })
  Object.assign(state.form, { batchName: '全校选课', termId: '52', scopeType: 'SCHOOL', classIds: ['1'] })
  await state.submitCreate()
  assert.equal(writes[0].applyScope, undefined)
})

test('uncertain create result preserves the form and releases submitting', async () => {
  const { state } = mount(undefined, { createBatch: async () => { throw Error('连接中断，请核对批次') } })
  Object.assign(state.form, { batchName: '保留输入', termId: '52', classIds: ['1'] })
  await state.submitCreate()
  assert.equal(state.form.batchName, '保留输入')
  assert.equal(state.saving, false)
  assert.match(state.formError, /核对批次/)
})
function mount(file = 'AaSelectionConsoleView', overrides = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${file}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import (.*?) from .*$/gm,
    (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies`).replace('export default', 'component =')
  const api = { listBatches: async () => ok({ list: [], total: 0 }), listCourses: async id => ok({ list: [{ id }] }),
    batchStats: async id => ok({ batchId: id }), listRounds: async id => ok({ items: [{ id }] }),
    getBatch: async id => ok(batch(id)), batchPreflight: async () => ok({ allowed: true }), ...overrides }
  const context = { dependencies: { ...flow, academicAffairsApi: api, academicAffairsSelectionApi: api,
    isDeniedResult, currentUserFromToken: () => ({}), toast: { success() {}, error() {} } } }
  vm.runInNewContext(script, context)
  const component = context.component
  const state = Object.assign(component.data(), component.methods, { ctx: {}, $route: { fullPath: '/selection', query: {} },
    activeTab: 'batch', academicFlow: { identity: () => 'tenant:user:role', restorePosition() {} } })
  for (const key of ['listGate', 'detailGate', 'rosterGate']) state[key] = flow.createAcademicRequestGate(() => key === 'listGate' ? state.pageContext() : state.commandContext())
  return { state, component, api }
}

test('time tick prevents duplicate commands and reports deferred and blocked batches', async () => {
  const response = deferred(); let writes = 0
  const { state } = mount(undefined, { timeTick: () => { writes++; return response.promise } })
  state.load = async () => {}
  const first = state.runTimeTick(); await state.runTimeTick()
  assert.equal(writes, 1)
  response.resolve(ok({ opened: 2, closed: 1, blocked: [{ batchId: '11', message: '学期已归档' }], deferred: [{ batchId: '12', message: '其他命令处理中' }] }))
  await first
  assert.equal(state.tickReceipt.partial, true)
  assert.match(state.tickReceipt.message, /已开选 2 个，已截止 1 个/)
  assert.match(state.tickReceipt.message, /批次 11：学期已归档/)
  assert.match(state.tickReceipt.message, /批次 12：其他命令处理中/)
  assert.equal(state.tickBusy, false)
  assert.equal(state.batchStatusLabel({ status: 'OPEN', windowState: 'ENDED' }), '窗口已截止，待收口')
})

test('time tick receipt from a previous identity is discarded', async () => {
  const response = deferred()
  const { state } = mount(undefined, { timeTick: () => response.promise })
  const action = state.runTimeTick()
  state.academicFlow.identity = () => 'another-school'
  response.resolve(ok({ opened: 5, closed: 8 }))
  await action
  assert.equal(state.tickReceipt, null)
})

test('selection A arriving after B cannot replace B courses, statistics or rounds', async () => {
  const slow = deferred()
  const { state } = mount(undefined, { listCourses: id => id === 'A' ? slow.promise : Promise.resolve(ok({ list: [{ id }] })) })
  const a = state.select(batch('A')); await state.select(batch('B'))
  slow.resolve(ok({ list: [{ id: 'A' }] })); await a
  assert.equal(state.current.batchId, 'B'); assert.equal(state.courses[0].id, 'B')
  assert.equal(state.stats.batchId, 'B'); assert.equal(state.rounds[0].id, 'B'); assert.equal(state.detailLoading, false)
})

test('newer refresh of same batch wins and old errors cannot replace its success', async () => {
  const old = deferred(); let calls = 0
  const { state } = mount(undefined, { listCourses: () => ++calls === 1 ? old.promise : Promise.resolve(ok({ list: [{ id: 'new' }] })) })
  state.current = batch('A'); const first = state.refreshDetail(); await state.refreshDetail()
  old.resolve({ code: 403, message: 'old forbidden' }); await first
  assert.equal(state.courses[0].id, 'new'); assert.equal(state.detailError, '')
})

test('latest detail failure stays visible and clears old statistics', async () => {
  const { state } = mount(undefined, { batchStats: async () => ({ code: 403, message: '无权限' }) })
  await state.select(batch('A')); assert.equal(state.detailError, '无权限'); assert.equal(state.stats, null)
})

test('A confirmation switched to B closes and sends no command', async () => {
  const writes = []; const { state } = mount(undefined, { publishBatch: async id => { writes.push(id); return ok(batch(id)) } })
  await state.select(batch('A')); await state.lifecycle('publishBatch', '发布'); assert.equal(state.confirmVisible, true)
  await state.select(batch('B')); await state.onConfirm()
  assert.equal(state.confirmVisible, false); assert.deepEqual(writes, [])
})

test('preflight from A cannot open a confirmation for B or a later visit to A', async () => {
  const check = deferred(); const { state, api } = mount()
  await state.select(batch('A')); api.batchPreflight = () => check.promise
  const pending = state.lifecycle('publishBatch', '发布')
  state.invalidateSelection(); state.current = batch('B'); state.invalidateSelection(); state.current = batch('A')
  check.resolve(ok({ allowed: true })); await pending
  assert.equal(state.confirmVisible, false)
})

test('double confirmation sends one captured command and stale write result cannot replace B', async () => {
  const result = deferred(); const writes = []
  const { state } = mount(undefined, { publishBatch: id => { writes.push(id); return result.promise } })
  await state.select(batch('A')); await state.lifecycle('publishBatch', '发布')
  const first = state.onConfirm(); await state.onConfirm(); await state.select(batch('B'))
  result.resolve(ok({ ...batch('A'), status: 'PUBLISHED' })); await first
  assert.deepEqual(writes, ['A']); assert.equal(state.current.batchId, 'B'); assert.equal(state.saving, false)
})

test('successful lifecycle releases submitting even though the status changed', async () => {
  const { state } = mount(undefined, { publishBatch: async id => ok({ ...batch(id), status: 'PUBLISHED' }) })
  await state.select(batch('A')); await state.lifecycle('publishBatch', '发布'); await state.onConfirm()
  assert.equal(state.current.status, 'PUBLISHED'); assert.equal(state.saving, false)
})

test('roster A arriving after roster B cannot contaminate the open drawer', async () => {
  const slow = deferred(); const { state } = mount(undefined, { courseRoster: id => id === 'A' ? slow.promise : Promise.resolve(ok({ list: [{ id }] })) })
  state.current = batch('batch'); const a = state.openRoster({ selectionCourseId: 'A' })
  await state.openRoster({ selectionCourseId: 'B' }); slow.resolve(ok({ list: [{ id: 'A' }] })); await a
  assert.equal(state.rosterRows[0].id, 'B')
})

test('unmount invalidates a pending detail response', async () => {
  const slow = deferred(); const { state, component } = mount(undefined, { listCourses: () => slow.promise })
  const load = state.select(batch('A')); component.beforeUnmount.call(state)
  slow.resolve(ok({ list: [{ id: 'A' }] })); await load
  assert.equal(state.courses.length, 0); assert.equal(state.stats, null)
})

test('role identity changes invalidate responses even before context watcher runs', async () => {
  const slow = deferred(); const { state } = mount(undefined, { listCourses: () => slow.promise })
  const load = state.select(batch('A')); state.academicFlow.identity = () => 'tenant:user:other-role'
  slow.resolve(ok({ list: [{ id: 'A' }] })); await load; assert.equal(state.courses.length, 0)
})

test('direct batchId deep link selects the requested batch instead of the default batch', async () => {
  const { state } = mount(undefined, {
    listBatches: async () => ok({ list: [batch('A'), batch('B')], total: 2 })
  })
  state.$route = { fullPath: '/selection?tab=rule&batchId=B', query: { tab: 'rule', batchId: 'B' } }
  state.activeTab = 'rule'
  await state.load()
  assert.equal(state.current.batchId, 'B')
})

test('scheduling workbench uses latest batch response while previous batch is loading', async () => {
  const slow = deferred(); const { state, component } = mount('AaSchedulingConsoleView', { getScheduleSummary: id => id === 'A' ? slow.promise : Promise.resolve(ok({ batchId: id })) })
  state.$route = { fullPath: '/scheduling?batchId=A', query: { batchId: 'A' } }; state.workbenchBatchId = 'A'
  state.workbenchGate = flow.createAcademicRequestGate(() => JSON.stringify([state.routeContextKey(), state.workbenchBatchId]))
  state.routeGate = flow.createAcademicRequestGate(() => state.routeContextKey()); state.ruleGate = flow.createAcademicRequestGate(() => state.routeContextKey())
  const a = state.loadWorkbench(); state.$route = { fullPath: '/scheduling?batchId=B', query: { batchId: 'B' } }
  state.workbenchBatchId = 'B'; await state.loadWorkbench(); slow.resolve(ok({ batchId: 'A' })); await a
  assert.equal(state.workbench.batchId, 'B'); component.beforeUnmount.call(state)
})
