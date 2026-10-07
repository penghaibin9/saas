import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { queuePosition } from '../src/modules/internship/composables/reviewQueue.js'
const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/components/ReviewQueueBar.vue', import.meta.url), 'utf8')).descriptor.script.content.replace(/^import.*\r?\n/gm, '').replace('export default', 'return')
function view(id, query = {}) {
  const messages = [], navigations = []
  const def = new Function('queuePosition', 'toast', script)(queuePosition, { success: text => messages.push(text) })
  const vm = { ...def.data(), currentId: id, $route: { query }, $router: { push: route => navigations.push(route) }, listFallback: '/admin/internship/reports?batchId=2', makePath: id => '/detail/' + id }
  for (const [key, fn] of Object.entries(def.computed)) Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  vm.queue = { ids: ['1', '2'], listPath: '/old-list', listQuery: { batchId: '1' } }
  return { vm, messages, navigations }
}
test('queue with another batch cannot navigate or override fallback return', () => {
  const { vm, navigations } = view('1', { batchId: '2' })
  assert.equal(vm.hasQueue, false); vm.goNext(); vm.backToList()
  assert.deepEqual(navigations, [vm.listFallback])
})
test('unrelated deep-link record cannot use old queue return', () => {
  const { vm, navigations } = view('9', { batchId: '1' }); vm.backToList()
  assert.equal(vm.hasQueue, false); assert.deepEqual(navigations, [vm.listFallback])
})
test('last queue position reports end of list without claiming all work completed', () => {
  const { vm, messages } = view('2', { batchId: '1' })
  assert.equal(vm.advance(), false); assert.match(messages[0], /当前列表末尾/); assert.doesNotMatch(messages[0], /全部处理完/)
})

test('matching queue retains next record and original list return', () => {
  const { vm, navigations } = view('1', { batchId: '1' })
  assert.equal(vm.hasQueue, true); vm.goNext(); vm.backToList()
  assert.deepEqual(navigations, ['/detail/2', { path: '/old-list', query: { batchId: '1' } }])
})
