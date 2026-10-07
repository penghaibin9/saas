import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/AttendanceExceptionListView.vue', import.meta.url), 'utf8')).descriptor.script.content
  .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[^\n]*\n/, '').replace('export default', 'return')
function view(api, saveQueue = () => {}) {
  const def = new Function('internshipApi', 'captureWorkContext', 'saveReviewQueue', script)(api, () => {}, saveQueue)
  const vm = { ...def.data(), batchStore: { selectedBatchId: '7' } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  return vm
}
test('exception query scopes to selected batch and clears stale selection', async () => {
  let params
  const vm = view({ getAttendanceExceptions: async p => { params = p; return { code: 0, data: { list: [], total: 0 } } } })
  vm.selected = ['old']; await vm.load()
  assert.equal(params.batchId, '7'); assert.deepEqual(vm.selected, [])
})
test('old exception batch response cannot replace the new batch rows', async () => {
  let resolve; let count = 0
  const vm = view({ getAttendanceExceptions: () => ++count === 1 ? new Promise(done => { resolve = done }) : Promise.resolve({ code: 0, data: { list: [{ id: 'new' }], total: 1 } }) })
  const old = vm.load(); vm.batchStore.selectedBatchId = '8'; await vm.load()
  resolve({ code: 0, data: { list: [{ id: 'old' }], total: 50 } }); await old
  assert.equal(vm.rows[0].id, 'new'); assert.equal(vm.pagination.total, 1)
})


test('exception queue and detail use identical batch and panel context', () => {
  let queue, target
  const vm = view({}, value => { queue = value })
  vm.$route = { path: '/admin/internship/exceptions', query: { panel: 'exceptions', page: '3' } }
  vm.$router = { push: value => { target = value } }; vm.rows = [{ id: '9007199254740999', status: 'PENDING_HANDLE' }]
  vm.goDetail(vm.rows[0])
  assert.deepEqual(queue.listQuery, target.query); assert.equal(target.query.batchId, '7'); assert.equal(target.query.panel, 'exceptions'); assert.equal(target.query.page, '3')
})
