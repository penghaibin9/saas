import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/LeaveReviewView.vue', import.meta.url), 'utf8')).descriptor.script.content
  .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[\s\S]*?\},\r?\n/, '').replace('export default', 'return')
function view(api, files = {}) {
  const def = new Function('leaveApi', 'guidanceVisitApi', 'emptyConflict', 'REJECT_LEAVE', script)(api, files, () => ({}), [])
  const vm = { ...def.data(), batchStore: { selectedBatchId: '7' } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  return vm
}
test('leave list does not replace newer filter results with a late response', async () => {
  let resolve; let count = 0
  const vm = view({ getLeaves: () => ++count === 1 ? new Promise(done => { resolve = done }) : Promise.resolve({ code: 0, data: { list: [{ id: 'new' }], total: 1 } }) })
  const old = vm.load(); vm.statusFilter = 'APPROVED'; await vm.load()
  resolve({ code: 0, data: { list: [{ id: 'old' }], total: 99 } }); await old
  assert.equal(vm.rows[0].id, 'new'); assert.equal(vm.total, 1)
})
test('downloading previous leave evidence cannot acknowledge a newly selected request', async () => {
  let resolve
  const vm = view({ markEvidenceViewed: () => assert.fail('must not mark new request') }, { downloadAttachment: () => new Promise(done => { resolve = done }) })
  vm.detail.data = { id: '1', attachment: { fileId: '10', fileName: '证明.pdf' } }
  const pending = vm.downloadAtt(); vm.detail.data = { id: '2', evidenceViewed: false }
  resolve(); await pending; assert.equal(vm.detail.data.evidenceViewed, false)
})

test('leave approval blocks duplicate clicks and conflicted snapshots before request', async () => {
  const vm = view({ review: () => assert.fail('must not review') }); vm.canBtn = () => true
  vm.pending = { id: '1', action: 'APPROVE', expectedVersion: 3 }; vm.cd.submitting = true
  await vm.onConfirm({ reason: '' }); vm.cd.submitting = false; vm.conflict.active = true
  await vm.onConfirm({ reason: '' })
})
test('old leave approval response cannot clear or advance a new selection', async () => {
  let resolve
  const vm = view({ review: () => new Promise(done => { resolve = done }) }); vm.canBtn = () => true
  vm.pending = { id: '1', action: 'APPROVE', expectedVersion: 3 }
  const old = vm.onConfirm({ reason: '' }); vm.pending = null; vm.selectedId = '2'
  resolve({ code: 0, data: { id: '1', status: 'APPROVED' } }); await old
  assert.equal(vm.lastReceipt, null); assert.equal(vm.selectedId, '2')
})
