import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/pages/student/internship/insurance/index.vue', import.meta.url), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
function view(api = {}, upload = async () => ({ fileId: 'new-file' })) {
  const notices = []
  const def = new Function('studentApi', 'chooseSingleFile', 'uploadBusinessFile', 'toast', source)(api, async () => ({ name: 'fixture.pdf' }), upload, message => notices.push(message))
  const vm = def.data()
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(def.computed)) Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  vm.info = { id: '9007199254740999', version: 3, status: 'VERIFIED', canRenew: true }
  vm.form = { insurerName: '虚构保险机构', policyNo: 'FIXTURE-01', effectiveDate: '2026-09-01', expiryDate: '2027-02-28', fileId: 'old-file' }
  return { vm, notices }
}

test('mobile renewal carries reviewed version and reloads school review status', async () => {
  const calls = []; let reads = 0
  const { vm } = view({ submitInternshipInsurance: async body => calls.push(body) })
  vm.load = async () => { reads++ }
  await vm.submit(); assert.equal(calls[0].expectedVersion, 3); assert.equal(reads, 1)
  vm.info.canRenew = false; await vm.submit(); assert.equal(calls.length, 1)
  vm.info.canRenew = true; vm.historyMode = true; await vm.submit(); assert.equal(calls.length, 1)
})

test('mobile conflict retains edits and does not automatically read or retry', async () => {
  let writes = 0; const { vm } = view({ submitInternshipInsurance: async () => { writes++; throw { code: 409001 } } })
  vm.load = async () => assert.fail('must preserve the form')
  await vm.submit(); await vm.submit()
  assert.equal(writes, 1); assert.equal(vm.form.fileId, 'old-file'); assert.equal(vm.conflict, true)
})

test('mobile upload failure or missing file ID retains the prior material', async () => {
  for (const upload of [async () => { throw new Error('上传失败') }, async () => ({})]) {
    const { vm } = view({}, upload); await vm.pickFile()
    assert.equal(vm.form.fileId, 'old-file'); assert.ok(vm.submitError)
  }
})

test('mobile upload in progress and missing version block submission', async () => {
  const { vm } = view({ submitInternshipInsurance: async () => assert.fail('unexpected submit') })
  vm.uploading = true; await vm.submit(); vm.uploading = false
  vm.info.version = null; await vm.submit(); assert.match(vm.submitError, /版本缺失/)
})

test('late mobile write cannot reload a departed page', async () => {
  let resolve; const { vm, notices } = view({ submitInternshipInsurance: () => new Promise(done => { resolve = done }) })
  vm.load = async () => assert.fail('page departed')
  const pending = vm.submit(); vm.requestSeq++; resolve({}); await pending
  assert.equal(notices.length, 0)
})
