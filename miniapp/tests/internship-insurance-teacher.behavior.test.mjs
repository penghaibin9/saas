import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const script = fs.readFileSync(new URL('../src/pages/teacher-internship/insurance-verify/index.vue', import.meta.url), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
const item = { id: '9007199254740999', studentName: '虚构学生', version: 3, fileId: '9', hasFile: true }
function view({ open = async () => ({ fileId: '9', readyForBusiness: true, canPreview: true }), write = async () => {}, read = async () => ({ list: [] }) } = {}) {
  const context = { restore() {}, load: async () => {}, selectedBatchId: '1', batches: [{ id: '1' }] }
  const def = new Function('useInternshipContextStore', 'teacherInternshipInsurancePending', 'teacherInternshipInsuranceVerify', 'fileSdk', script)(() => context, read, write, { openInline: open })
  const vm = { ...def.data(), state: 'ready', batchId: '1', list: [item] }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  return vm
}

test('approval requires the current original file to open safely', async () => {
  const vm = view(); vm.verify(item, 'APPROVE'); assert.equal(vm.review, null)
  await vm.openEvidence(item); vm.verify(item, 'APPROVE'); assert.equal(vm.review.version, 3)
  assert.equal(vm.evidenceReady({ ...item, version: 4 }), false)
})

test('unsafe or mismatched file metadata never enables approval', async () => {
  for (const meta of [{ fileId: 'other', readyForBusiness: true, canPreview: true }, { fileId: '9', readyForBusiness: false, canPreview: true }]) {
    const vm = view({ open: async () => meta }); await vm.openEvidence(item)
    assert.equal(vm.evidenceReady(item), false); assert.ok(vm.evidenceErrors[item.id])
  }
})

test('reject validation and conflict preserve the teachers original text and version', async () => {
  let writes = 0; const vm = view({ write: async () => { writes++; throw { code: 409001 } } })
  vm.verify(item, 'REJECT'); vm.review.comment = '短'; await vm.submitReview(); assert.equal(writes, 0)
  vm.review.comment = '请补充覆盖完整实习期的保单'; await vm.submitReview(); await vm.submitReview()
  assert.equal(writes, 1); assert.equal(vm.review.version, 3); assert.equal(vm.conflict, true)
  vm.closeReview(); vm.verify(item, 'REJECT'); assert.match(vm.review.comment, /完整实习期/)
})

test('double submission sends once and reloads the actual queue on success', async () => {
  let resolve, writes = 0, reads = 0
  const vm = view({ write: async (id, body) => { writes++; assert.equal(id, item.id); assert.equal(body.expectedVersion, 3); return new Promise(done => { resolve = done }) }, read: async () => { reads++; return { list: [] } } })
  vm.verify(item, 'REJECT'); vm.review.comment = '保单期限不足，请补充完整'
  const pending = vm.submitReview(); await vm.submitReview(); resolve({}); await pending
  assert.equal(writes, 1); assert.equal(reads, 1); assert.deepEqual(vm.list, []); assert.match(vm.receipt, /等待学生补正/)
})

test('late evidence and review results cannot leak into another batch', async () => {
  let resolve
  const vm = view({ open: () => new Promise(done => { resolve = done }) })
  const pending = vm.openEvidence(item); vm.loadSeq++; vm.batchId = '2'
  resolve({ fileId: '9', readyForBusiness: true, canPreview: true }); await pending
  assert.equal(vm.evidenceReady(item), false)
})

test('freshly reloaded queue requires opening the new evidence again', async () => {
  const vm = view(); await vm.openEvidence(item); assert.equal(vm.evidenceReady(item), true)
  await vm.load(); assert.equal(vm.evidenceReady(item), false)
})
