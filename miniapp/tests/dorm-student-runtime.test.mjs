import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/pages/student/affairs/dorm.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function view(api = {}, files = {}) {
  let generation = 1, requestId = 0
  const toasts = []
  const page = new Function('createSubmitLock', 'currentSessionGeneration', 'affairsContractApi', 'studentApi', 'fileSdk', 'normalizeError', 'safeToast', 'createClientRequestId', script)(
    () => ({ run: fn => Promise.resolve().then(fn) }), () => generation, api, { getMyDorm: async () => ({ hasBed: true }) }, files,
    e => ({ text: e?.message || '加载失败' }), text => toasts.push(text), () => `request-${++requestId}`)
  const vm = { ...page.data(), ...page.methods }
  for (const [key, fn] of Object.entries(page.computed)) Object.defineProperty(vm, key, { get: fn.bind(vm) })
  vm.cfg = { hasBed: true }; vm.rectNotes['9'] = '已清理宿舍通道'; vm.rectFiles['9'] = { fileId: '25' }
  return { vm, toasts, switchAccount: () => { generation++ } }
}

test('transfer buildings and rooms request one bounded page per user action', async () => {
  const calls = []
  const { vm } = view({
    getDormTransferOptions: async params => { calls.push(params); return { items: [{ buildingId: String(params.page) }], total: 41, hasMore: true } },
    getDormTransferRooms: async (id, params) => { calls.push({ id, ...params }); return { items: [{ roomId: String(params.page) }], total: 50 } }
  })
  await vm.loadTransferOptions(); assert.equal(calls.length, 1); assert.deepEqual(calls[0], { page: 1, pageSize: 20 })
  await vm.loadTransferOptions(true); assert.equal(vm.buildings.length, 2)
  await vm.pickBuilding({ buildingId: '1' }); assert.deepEqual(calls[2], { id: '1', page: 1, pageSize: 20 })
  await vm.loadTransferRooms(true); assert.equal(vm.rooms.length, 2)
})

test('rectification pagination retains previous records when next page fails', async () => {
  const { vm } = view({ getMyDormRectifications: async params => { assert.deepEqual(params, { page: 2, pageSize: 20 }); throw Error('服务暂不可用') } })
  vm.rectifications = [{ rectificationId: '9' }]; vm.rectTotal = 21
  await vm.loadMoreRectifications()
  assert.equal(vm.rectifications.length, 1); assert.equal(vm.rectPage, 1); assert.equal(vm.rectLoading, false); assert.equal(vm.rectError, '服务暂不可用')
})

for (const mode of ['account', 'unload']) test(`${mode}: late room data is discarded`, async () => {
  const pending = deferred()
  const { vm, switchAccount } = view({ getDormTransferRooms: () => pending.promise })
  vm.sel.building = '1'; const request = vm.loadTransferRooms()
  if (mode === 'account') switchAccount(); else vm.disposed = true
  pending.resolve({ items: [{ roomId: 'old-account-room' }], total: 1 }); await request
  assert.deepEqual(vm.rooms, [])
})

test('rectification double submit issues one command and preserves the displayed version', async () => {
  const pending = deferred(); const calls = []
  const { vm } = view({ submitDormRectification: (id, payload) => { calls.push({ id, payload }); return pending.promise } })
  vm.load = async () => {}
  const first = vm.submitRect({ rectificationId: '9', version: 3 }); const second = vm.submitRect({ rectificationId: '9', version: 3 })
  assert.equal(calls.length, 1); assert.equal(calls[0].payload.expectedVersion, 3)
  pending.resolve({}); await Promise.all([first, second]); assert.equal(vm.submitting, false); assert.equal(vm.rectNotes['9'], undefined)
})

test('failed identical retry keeps idempotency key; changed evidence gets a new key', async () => {
  const ids = []
  const { vm } = view({ submitDormRectification: async (id, data) => { ids.push(data.clientRequestId); throw Error('网络异常') } })
  const row = { rectificationId: '9', version: 3 }
  await vm.submitRect(row); await vm.submitRect(row)
  assert.equal(ids[0], ids[1]); assert.equal(vm.rectNotes['9'], '已清理宿舍通道')
  vm.rectNotes['9'] = '已清理宿舍通道并完成复查'; await vm.submitRect(row)
  assert.notEqual(ids[1], ids[2])
})

test('file picker is single-flight and account switch prevents a subsequent upload', async () => {
  const pending = deferred(); let choices = 0, uploads = 0
  const { vm, switchAccount } = view({}, { choose: () => { choices++; return pending.promise }, upload: async () => { uploads++; return { fileId: '28' } } })
  const first = vm.uploadRectPhoto({ rectificationId: '9' }); await vm.uploadRectPhoto({ rectificationId: '9' })
  assert.equal(choices, 1); switchAccount(); pending.resolve({ name: 'photo.jpg' }); await first
  assert.equal(uploads, 0); assert.equal(vm.rectFiles['9'].fileId, '25')
})

test('account switch ignores old write success without clearing the new form', async () => {
  const pending = deferred(); const { vm, switchAccount, toasts } = view({ submitDormRectification: () => pending.promise })
  let loads = 0; vm.load = async () => { loads++ }
  const request = vm.submitRect({ rectificationId: '9', version: 3 }); switchAccount(); vm.rectNotes['9'] = '新账号填写内容'
  pending.resolve({}); await request
  assert.equal(loads, 0); assert.deepEqual(toasts, []); assert.equal(vm.rectNotes['9'], '新账号填写内容')
})
