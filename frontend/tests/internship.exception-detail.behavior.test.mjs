import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/AttendanceExceptionDetailView.vue', import.meta.url), 'utf8')).descriptor.script.content
  .replace(/^import[^\n]*\n/gm, '').replace(/ {2}components: \{[\s\S]*?ActionReceipt \},\r?\n/, '').replace('export default', 'return')
function view(api) {
  const def = new Function('internshipApi', 'emptyConflict', script)(api, () => ({}))
  const vm = { ...def.data(), $route: { params: { id: '1' } } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  vm.loading = false; vm.detail = { id: '1', status: 'PENDING_HANDLE', version: 4 }; vm.comment = '已核对企业现场情况'
  return vm
}
test('exception decision prevents duplicate and conflicted writes', async () => {
  const vm = view({ handleAttendanceException: () => assert.fail('must not submit') })
  vm.submitting = true; await vm.submit(); vm.submitting = false; vm.conflict.active = true; await vm.submit()
})
test('late exception write result cannot advance another student or erase their comment', async () => {
  let resolve
  const vm = view({ handleAttendanceException: () => new Promise(done => { resolve = done }) })
  const pending = vm.submit(); vm.$route.params.id = '2'; vm.detail = { id: '2', status: 'PENDING_HANDLE' }; vm.comment = '另一位学生的核实意见'
  resolve({ code: 0, data: { statusLabel: '已处理' } }); await pending
  assert.equal(vm.lastReceipt, null); assert.equal(vm.comment, '另一位学生的核实意见')
})
