import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/pages/teacher/dorm-review/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function view({ api = {}, teacher = {}, request = async () => ({}), files = {} } = {}) {
  let generation = 1, id = 0
  const messages = []
  const page = new Function('teacherApi', 'affairsContractApi', 'realRequest', 'fileSdk', 'normalizeError', 'toast', 'currentSessionGeneration', 'createClientRequestId', script)(teacher, api, request, files, e => ({ text: e.message }), text => messages.push(text), () => generation, () => `request-${++id}`)
  const vm = { ...page.data(), ...page.methods }
  vm.sessionGeneration = 1
  Object.defineProperty(vm, 'inspectionAbnormal', { get: page.computed.inspectionAbnormal.bind(vm) })
  return { vm, messages, switchAccount: () => { generation++ } }
}

test('transfer queue does not depend on inspection or rectification permissions', async () => {
  let calls = 0
  const { vm } = view({ teacher: { getAffairsDormPending: async () => { calls++; return { transfers: [{ transferId: '1' }], exceptions: [] } } }, api: new Proxy({}, { get() { throw Error('unrelated request') } }) })
  await vm.load(); assert.equal(vm.state, 'ready'); assert.equal(calls, 1); assert.equal(vm.transfers[0].transferId, '1')
})

test('inspection page requests only a bounded task page', async () => {
  const calls = []
  const { vm } = view({ api: { getDormInspectionTasks: async (...args) => { calls.push(args); return { items: [{ taskId: '25' }], total: 45 } } } })
  vm.tab = 'inspection'; vm.taskPage = 2; await vm.load()
  assert.equal(vm.state, 'ready'); assert.deepEqual(calls, [['RUNNING', { page: 2, pageSize: 20 }]]); assert.equal(vm.taskTotal, 45)
})

test('pending page uses server totals and sends the requested page', async () => {
  const calls = []
  const { vm } = view({ teacher: { getAffairsDormPending: async params => { calls.push(params); return { transfers: [{ transferId: '21' }], exceptions: [], transferTotal: 42, exceptionTotal: 0 } } } })
  vm.pendingPage = 2; await vm.load()
  assert.deepEqual(calls, [{ page: 2, pageSize: 20 }]); assert.equal(vm.transferTotal, 42)
})

test('a confirmation dialog cannot submit after switching accounts', async () => {
  let writes = 0
  const { vm, switchAccount } = view({ api: { reviewDormTransfer: async () => { writes++ } } })
  vm.reviewTransfer({ transferId: '9', version: 4, allowedActions: ['APPROVE'] }, 'APPROVE')
  switchAccount(); await vm.submitActionDlg(); assert.equal(writes, 0)
})

test('recheck double submit sends the old page version once', async () => {
  const pending = deferred(), calls = []
  const { vm } = view({ api: { recheckDormRectification: (id, data) => { calls.push(data); return pending.promise } } })
  vm.recheckNotes['9'] = '已按照片逐项确认'; vm.load = async () => {}
  const row = { rectificationId: '9', version: 4, severity: 'LOW', allowedActions: ['PASS'] }
  const first = vm.submitRecheck(row, 'PASS'); await vm.submitRecheck(row, 'PASS')
  assert.equal(calls.length, 1); assert.equal(calls[0].expectedVersion, 4)
  pending.resolve({}); await first; assert.equal(vm.acting, false)
})

test('inspection floor is filtered on server, with explicit room pagination', async () => {
  const calls = []
  const { vm } = view({ api: { getDormInspectionRooms: async (...args) => { calls.push(args); return { items: [{ roomId: '15' }], total: 25 } } } })
  await vm.selectTask({ taskId: '7', buildingId: '5', floorScope: [3, 4] })
  assert.deepEqual(calls[0], ['5', { floor: 3, page: 1, pageSize: 20 }]); assert.equal(calls.length, 1)
  vm.roomPage = 2; await vm.loadInspectionRooms(); assert.equal(calls[1][1].page, 2)
})

test('late room and occupant results cannot overwrite a newer selection', async () => {
  const oldRooms = deferred(), oldPeople = deferred()
  const { vm } = view({ api: {
    getDormInspectionRooms: id => id === '1' ? oldRooms.promise : Promise.resolve({ items: [{ roomId: '22' }], total: 1 }),
    getDormInspectionBeds: id => id === '21' ? oldPeople.promise : Promise.resolve({ items: [{ studentId: 'new', studentName: '当前学生' }] })
  } })
  const first = vm.selectTask({ buildingId: '1' }); await vm.selectTask({ buildingId: '2' })
  oldRooms.resolve({ items: [{ roomId: 'old' }], total: 1 }); await first
  assert.equal(vm.rooms[0].roomId, '22')
  const people = vm.selectRoom({ roomId: '21' }); await vm.selectRoom({ roomId: '22' })
  oldPeople.resolve({ items: [{ studentId: 'old' }] }); await people
  assert.equal(vm.occupants[0].studentId, 'new')
})

test('account switch discards a late teacher queue', async () => {
  const pending = deferred(); const { vm, switchAccount } = view({ teacher: { getAffairsDormPending: () => pending.promise } })
  const request = vm.load(); switchAccount(); pending.resolve({ transfers: [{ transferId: 'old' }], exceptions: [] }); await request
  assert.deepEqual(vm.transfers, [])
})

test('inspection submit is single-flight and late account success is ignored', async () => {
  const pending = deferred(); let writes = 0
  const { vm, switchAccount, messages } = view({ api: { submitDormInspectionRecord: () => { writes++; return pending.promise } } })
  vm.inspection = { task: { taskId: '7' }, roomId: '22', items: [], detail: '', studentId: '', file: null }
  const first = vm.submitInspection(); await vm.submitInspection(); assert.equal(writes, 1)
  switchAccount(); pending.resolve({}); await first; assert.deepEqual(messages, [])
})

test('uncertain inspection retries retain the request key and reject silently changed payloads', async () => {
  const ids = []; const { vm, messages } = view({ api: { submitDormInspectionRecord: async (id, data) => { ids.push(data.clientRequestId); throw Error('网络异常') } } })
  vm.inspection = { task: { taskId: '7' }, roomId: '22', items: [], detail: '', studentId: '', file: null }
  await vm.submitInspection(); await vm.submitInspection(); assert.equal(ids[0], ids[1])
  vm.inspection.studentId = '31'; await vm.submitInspection(); assert.equal(ids.length, 2); assert.match(messages.at(-1), /先刷新任务确认/)
})

test('recheck upload locks before opening picker and stops on account switch', async () => {
  const pending = deferred(); let choose = 0, upload = 0
  const { vm, switchAccount } = view({ files: { choose: () => { choose++; return pending.promise }, upload: async () => { upload++ } } })
  const first = vm.uploadRecheckPhoto({ rectificationId: '9' }); await vm.uploadRecheckPhoto({ rectificationId: '9' })
  assert.equal(choose, 1); switchAccount(); pending.resolve({ name: 'pic.jpg' }); await first; assert.equal(upload, 0)
})

test('dorm API pagination uses one HTTP request and preserves large identifiers', async () => {
  const calls = []
  const apiSource = readFileSync(new URL('../src/services/affairsContractApi.js', import.meta.url), 'utf8').replace(/^import .*$/gm, '').replace('export default affairsContractApi', '').replace('export const affairsContractApi =', 'return')
  const api = new Function('realRequest', apiSource)((...args) => { calls.push(args); return Promise.resolve({ items: [], total: 2000 }) })
  await api.getDormTransferOptions(); await api.getDormTransferRooms('9007199254740993', { page: 2 }); await api.getDormInspectionRooms('9007199254740993', { floor: 3, page: 2 })
  assert.equal(calls.length, 3); assert.equal(calls[0][1].data.pageSize, 20)
  assert.match(calls[1][0], /9007199254740993/); assert.deepEqual(calls[2][1].data, { floor: 3, page: 2, pageSize: 20 })
})
