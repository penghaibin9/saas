import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/pages/teacher/campus-service/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
function mount(api) {
  let generation = 1
  const notices = []
  const component = new Function('teacherApi', 'currentSessionGeneration', 'normalizeError', 'safeToast', 'toastError', 'go', script)(
    api, () => generation, e => ({ text: e.message, pageState: e.pageState || 'error' }), x => notices.push(x), e => notices.push(e.message), () => {})
  const vm = { ...component.data(), ...component.methods }
  return { vm, component, notices, switchAccount: () => { generation++ } }
}

test('search supersedes a pending next page and duplicate load-more is suppressed', async () => {
  const slow = deferred(); let calls = 0
  const { vm } = mount({ getCampusWorkOrders: ({ page }) => { calls++; return page === 2 ? slow.promise : Promise.resolve({ list: [{ id: 'new' }], total: 1 }) } })
  vm.workList = [{ id: 'old' }]; vm.workPage = 1
  const more = vm.loadMoreWorkOrders()
  await vm.loadMoreWorkOrders()
  await vm.searchWorkOrders()
  slow.resolve({ list: [{ id: 'stale' }], total: 50 }); await more
  assert.equal(calls, 2); assert.deepEqual(vm.workList, [{ id: 'new' }]); assert.equal(vm.workPage, 1)
})

test('closed page and switched account cannot receive old work order data', async () => {
  for (const mode of ['unload', 'account']) {
    const slow = deferred()
    const { vm, component, switchAccount } = mount({ getCampusWorkOrders: () => slow.promise })
    const request = vm.loadWorkOrders()
    if (mode === 'unload') component.onUnload.call(vm); else switchAccount()
    slow.resolve({ list: [{ id: 'student-a' }], total: 1 }); await request
    assert.deepEqual(vm.workList, [])
  }
})

test('double tap issues one mutation and account switch prevents follow-up reads', async () => {
  const slow = deferred(); let writes = 0; let reads = 0
  const { vm, switchAccount, notices } = mount({ handleCampusWorkOrder: async (_id, body) => { writes++; assert.equal(body.version, 4); return slow.promise }, getCampusWorkOrderDetail: () => { reads++ } })
  vm.selected = { order: { id: '12', version: 4, allowedActions: ['handle', 'complete'] } }; vm.actionNote = '已核实并完成办理'
  const submit = vm.submitWorkOrder(true); await vm.submitWorkOrder(true)
  switchAccount(); slow.resolve({}); await submit
  assert.equal(writes, 1); assert.equal(reads, 0); assert.deepEqual(notices, [])
})

test('failed or conflicted mutation preserves note and does not fetch a new version for replay', async () => {
  let reads = 0
  const { vm } = mount({ handleCampusWorkOrder: async () => { throw Error('记录版本已变化') }, getCampusWorkOrderDetail: () => { reads++ } })
  vm.selected = { order: { id: '12', version: 4, allowedActions: ['handle', 'complete'] } }; vm.actionNote = '本次填写的办理意见'
  await vm.submitWorkOrder(true)
  assert.equal(reads, 0); assert.equal(vm.actionNote, '本次填写的办理意见'); assert.equal(vm.submitting, false)
})

test('server read-only action contract prevents accidental processing', async () => {
  let writes = 0
  const { vm } = mount({ handleCampusWorkOrder: () => { writes++ } })
  vm.selected = { order: { id: '12', version: 4, allowedActions: [] } }; vm.actionNote = '本次填写的办理意见'
  await vm.submitWorkOrder(true); assert.equal(writes, 0)
})

test('an invalid list response stays error rather than showing no applications', async () => {
  const { vm } = mount({ getCampusWorkOrders: async () => ({}) })
  await vm.loadWorkOrders(); assert.equal(vm.workState, 'error'); assert.ok(vm.workError)
})

test('work orders load independently when the leave queue fails', async () => {
  const { vm } = mount({ getCampusServicePending: async () => { throw Error('请假暂时不可用') }, getCampusWorkOrders: async () => ({ list: [{ id: '12' }], total: 1 }) })
  await vm.load(); assert.equal(vm.state, 'error')
  await vm.switchWorkOrders()
  assert.equal(vm.activeTab, 'workorder'); assert.equal(vm.workState, 'ready'); assert.equal(vm.workList[0].id, '12')
})

test('authorization and network failures retain their explicit page states', async () => {
  for (const pageState of ['unauthorized', 'forbidden', 'noLicense', 'offline']) {
    const { vm } = mount({ getCampusWorkOrders: async () => { throw Object.assign(Error('当前无法加载'), { pageState }) } })
    await vm.loadWorkOrders(); assert.equal(vm.workState, pageState)
  }
})

test('a saved mutation followed by a failed read cannot reuse the old actionable detail', async () => {
  let writes = 0; let lists = 0
  const { vm } = mount({
    handleCampusWorkOrder: async () => { writes++ },
    getCampusWorkOrderDetail: async () => { throw Error('网络异常，请重新打开查看') },
    getCampusWorkOrders: async () => { lists++; return { list: [{ id: '12', status: 'COMPLETED' }], total: 1 } }
  })
  vm.selected = { order: { id: '12', version: 4, allowedActions: ['handle', 'complete'] } }; vm.actionNote = '已核实并完成办理'
  await vm.submitWorkOrder(true)
  assert.equal(vm.selected, null); assert.equal(vm.detailLoading, false); assert.equal(vm.submitting, false)
  vm.actionNote = '再次点击旧的办理按钮'; await vm.submitWorkOrder(true)
  assert.equal(writes, 1); assert.equal(lists, 1); assert.equal(vm.workList[0].status, 'COMPLETED')
})
