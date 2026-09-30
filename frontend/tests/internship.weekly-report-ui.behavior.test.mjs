import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
const source = parse(fs.readFileSync(new URL('../src/modules/internship/views/WeeklyReportDetailView.vue', import.meta.url), 'utf8'))
assert.deepEqual(source.errors, [])
const script = source.descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace(/ {2}components: \{[\s\S]*?ActionReceipt \},/, '').replace('export default', 'return')
function view(api) {
  const def = new Function('internshipApi', 'emptyConflict', script)(api, () => ({}))
  const vm = { ...def.data(), loading: false, canReview: true, $route: { params: { id: '1' } } }
  for (const [key, method] of Object.entries(def.methods)) vm[key] = method.bind(vm)
  return vm
}
test('weekly report rejects duplicate and conflicted submissions', async () => {
  const vm = view({ reviewWeeklyReport: () => assert.fail('must not submit') })
  vm.detail = { id: '1', status: 'PENDING_REVIEW', version: 2 }; vm.submitting = true
  await vm.submit('APPROVE'); vm.submitting = false; vm.conflict.active = true; await vm.submit('APPROVE')
})
test('late weekly report approval cannot create receipt or advance a different report', async () => {
  let finish
  const vm = view({ reviewWeeklyReport: () => new Promise(resolve => { finish = resolve }) })
  vm.detail = { id: '1', status: 'PENDING_REVIEW', version: 2 }; const old = vm.submit('APPROVE')
  vm.$route.params.id = '2'; vm.detail = { id: '2', status: 'PENDING_REVIEW', version: 1 }
  finish({ code: 0, data: { id: '1' } }); await old
  assert.equal(vm.lastReceipt, null); assert.equal(vm.detail.id, '2')
})

test('returning to the same weekly report cannot revive the older request', async () => {
  const pending = []
  const vm = view({ getWeeklyReportDetail: () => new Promise(resolve => pending.push(resolve)) })
  const old = vm.load()
  vm.$route.params.id = '2'; const second = vm.load()
  vm.$route.params.id = '1'; const fresh = vm.load()
  pending[2]({ code: 0, data: { id: '1', version: 4 } }); await fresh
  pending[1]({ code: 0, data: { id: '2', version: 1 } }); await second
  pending[0]({ code: 0, data: { id: '1', version: 2 } }); await old
  assert.equal(vm.detail.version, 4); assert.equal(vm.detail.id, '1')
})
