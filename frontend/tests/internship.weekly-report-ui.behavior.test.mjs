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
