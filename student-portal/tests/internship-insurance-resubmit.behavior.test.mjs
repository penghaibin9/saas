import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { computed, reactive } from 'vue'

const source = fs.readFileSync(new URL('../src/views/internship/InternshipView.vue', import.meta.url), 'utf8')
const actions = source.slice(source.indexOf('async function uploadInsurancePolicy('), source.indexOf('async function ackPlan('))
const readonlySource = source.split('\n').find(line => line.startsWith('const insuranceReadOnly ='))
function view(api = {}) {
  const state = reactive({ busy: { value: false }, my: { value: {} }, insuranceMeta: { value: { id: '9007199254740999', version: 4, status: 'REJECTED' } }, insuranceError: { value: '' }, insuranceConflict: { value: false }, insForm: { policyNo: 'FIXTURE-01', fileId: 'old-file' } })
  const reads = [], notices = []
  const methods = new Function(...Object.keys(state), 'internshipCoreApi', 'currentInternshipContext', 'loadTab', 'ui', 'computed', `${readonlySource}; let insuranceEpoch = 0; ${actions}; return { saveInsurance, uploadInsurancePolicy, changeContext() { insuranceEpoch++ } }`)(...Object.values(state), api, () => ({ batchId: '1', internshipId: '2' }), async (...args) => reads.push(args), { notify: value => notices.push(value) }, computed)
  return { ...state, ...methods, reads, notices }
}

test('returned insurance submits the reviewed version and placement then reloads the result', async () => {
  const writes = []; const vm = view({ saveInsurance: async body => writes.push(body) })
  await vm.saveInsurance()
  assert.deepEqual(writes, [{ policyNo: 'FIXTURE-01', fileId: 'old-file', batchId: '1', internshipId: '2', expectedVersion: 4 }])
  assert.deepEqual(vm.reads, [['insurance', true]])
})

test('conflict retains edits and blocks blind resubmission', async () => {
  let writes = 0; const vm = view({ saveInsurance: async () => { writes++; throw { code: 409001 } } })
  await vm.saveInsurance(); await vm.saveInsurance()
  assert.equal(writes, 1); assert.equal(vm.insForm.fileId, 'old-file')
  assert.equal(vm.insuranceConflict.value, true); assert.match(vm.insuranceError.value, /填写内容已保留/)
})

test('duplicate, read-only and missing-version submissions never reach the server', async () => {
  const vm = view({ saveInsurance: async () => assert.fail('unexpected write') })
  vm.busy.value = true; await vm.saveInsurance(); vm.busy.value = false
  vm.my.value.historyMode = true; await vm.saveInsurance(); vm.my.value.historyMode = false
  vm.insuranceMeta.value.status = 'VERIFIED'; await vm.saveInsurance()
  vm.insuranceMeta.value.status = 'REJECTED'; vm.insuranceMeta.value.version = null; await vm.saveInsurance()
  assert.match(vm.insuranceError.value, /版本缺失/)
})

test('failed or malformed replacement upload preserves the existing policy file', async () => {
  for (const uploadInsurancePolicy of [async () => { throw new Error('上传失败') }, async () => ({})]) {
    const vm = view({ uploadInsurancePolicy })
    await vm.uploadInsurancePolicy({ target: { files: [{}], value: 'chosen' } })
    assert.equal(vm.insForm.fileId, 'old-file'); assert.ok(vm.insuranceError.value); assert.equal(vm.busy.value, false)
  }
})

test('a late upload cannot bind its file into the next context', async () => {
  let resolve; const vm = view({ uploadInsurancePolicy: () => new Promise(done => { resolve = done }) })
  const uploading = vm.uploadInsurancePolicy({ target: { files: [{}] } })
  vm.changeContext(); vm.insForm.fileId = 'next-context-file'
  resolve({ fileId: 'late-file' }); await uploading
  assert.equal(vm.insForm.fileId, 'next-context-file')
})

test('a late submission cannot reload or display success in the next context', async () => {
  let resolve; const vm = view({ saveInsurance: () => new Promise(done => { resolve = done }) })
  const saving = vm.saveInsurance(); vm.changeContext(); resolve({}); await saving
  assert.equal(vm.reads.length, 0); assert.equal(vm.notices.length, 0)
})

test('renewal is enabled only by the server and still respects history mode', async () => {
  let writes = 0; const vm = view({ saveInsurance: async () => { writes++ } })
  vm.insuranceMeta.value = { id: '9', version: 6, status: 'VERIFIED', canRenew: true }
  await vm.saveInsurance(); assert.equal(writes, 1)
  vm.my.value.historyMode = true
  await vm.saveInsurance(); assert.equal(writes, 1)
})
