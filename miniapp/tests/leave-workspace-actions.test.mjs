import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

const source = fs.readFileSync(new URL('../src/pages/teacher/affairs-leave/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
test('student detail hides the fixed new-application bar so it cannot intercept follow-up actions', () => {
  const page = fs.readFileSync(new URL('../src/pages/student/affairs/leave.vue', import.meta.url), 'utf8')
  assert.match(page, /<MobileSafeAreaBar v-if="!detailVisible">/)
  assert.match(page, /@click="editReturned\(x\)"/)
  assert.match(page, /@click="openExtend\(x\)"/)
})
function make() {
  const calls = []
  const api = { getAffairsLeavePending: async () => ({ list: [], total: 0 }) }
  const component = new Function('teacherApi', 'MobileLeaveDetail', 'normalizeError', 'toast', script)(api, {}, e => ({ kind: e.code === 409 ? 'conflict' : 'network' }), text => calls.push(text))
  const vm = { ...component.data(), ...component.methods }
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: () => getter.call(vm) })
  vm.detailId = '7'
  vm.openDetail = async id => calls.push(`detail:${id}`)
  vm._err = e => ({ kind: e.code === 409 ? 'conflict' : 'network' })
  return { vm, calls, api }
}
test('successful command followed by failed reload never retries a committed approval', async () => {
  const { vm, calls } = make()
  let writes = 0, retries = 0
  vm.load = async () => { throw new Error('network') }
  await vm.run(async () => { writes++ }, '已通过', '审批', () => { retries++ })
  assert.equal(writes, 1)
  assert.equal(retries, 0)
  assert.equal(vm.acting, false)
  assert.match(vm.detailError, /操作已成功/)
  assert.equal(calls.includes('detail:7'), false)
})
test('a conflict stops continuous processing and refreshes the same record without resubmission', async () => {
  const { vm, calls } = make()
  vm.sequentialMode = true
  vm.pending = [{ id: '7', version: 2, allowedActions: ['APPROVE'] }]
  vm.load = async () => calls.push('reload')
  await vm.run(async () => { throw { code: 409 } }, '已通过', '审批')
  assert.equal(vm.sequentialMode, false)
  assert.equal(vm.sequentialConflict, true)
  assert.deepEqual(calls, ['reload', 'detail:7'])
})
test('continuous approval only advances after reloading truth', async () => {
  const { vm, calls } = make()
  vm.sequentialMode = true
  vm.pending = [{ id: '7', version: 2, allowedActions: ['APPROVE'] }]
  vm.load = async () => { calls.push('reload'); vm.pending = [{ id: '8', version: 1, allowedActions: ['APPROVE'] }] }
  await vm.run(async () => calls.push('write:7'), '已通过', '审批', null, '7')
  assert.deepEqual(calls, ['write:7', '已通过', 'reload', 'detail:8'])
})
test('network failure keeps the existing draft retry; duplicate clicks do not write twice', async () => {
  const { vm } = make()
  let retry = 0, write = 0
  vm.acting = true
  await vm.run(async () => { write++ }, '', '')
  assert.equal(write, 0)
  vm.acting = false
  await vm.run(async () => { throw new Error('offline') }, '', '', () => { retry++ })
  await new Promise(resolve => setTimeout(resolve, 5))
  assert.equal(retry, 1)
  assert.equal(vm.acting, false)
})
test('finishing the last item on the last page returns to an existing page', async () => {
  const { vm, api } = make()
  const pages = []
  vm.page = 3
  api.getAffairsLeavePending = async params => {
    pages.push(params.page)
    return { total: 40, list: params.page === 3 ? [] : [{ id: '40', version: 1, allowedActions: ['APPROVE'] }] }
  }
  await vm.load()
  assert.deepEqual(pages, [3, 2])
  assert.equal(vm.visibleItems[0].id, '40')
  assert.equal(vm.state, 'ready')
})
