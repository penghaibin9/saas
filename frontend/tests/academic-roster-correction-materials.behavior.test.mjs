import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'
const source = parse(fs.readFileSync(new URL('../src/modules/academicAffairs/views/AaRosterCorrectionListView.vue', import.meta.url), 'utf8')).descriptor.script.content
const script = source.replace(/^import[^\n]*\n/gm, '').replace(/  components: \{[\s\S]*?\},/, '').replace('export default', 'return')
function view(api = {}, sdk = {}) {
  const definition = new Function('academicAffairsApi', 'fileSdk', 'toast', script)(api, { normalize: file => file, ...sdk }, { success() {}, error() {} })
  const vm = { $route: { query: {} } }
  Object.assign(vm, definition.data.call(vm))
  for (const [key, fn] of Object.entries(definition.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(definition.computed)) Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  vm.load = async () => {}
  vm.form = { studentId: '9007199254740999', fieldKey: 'ID_CARD', newValue: 'fixture-only', reason: '虚构测试资料更正' }
  return vm
}
test('identity correction requires evidence and never submits unsafe files', async () => {
  let writes = 0
  const vm = view({ createRosterCorrection: async () => { writes++; return { code: 0 } } })
  await vm.submitCreate(); assert.equal(writes, 0); assert.match(vm.formError, /证明材料/)
  vm.materialFiles = [{ fileId: '9007199254740998', readyForBusiness: false }]
  await vm.submitCreate(); assert.equal(writes, 0); assert.match(vm.formError, /安全/)
})
test('ready uploaded evidence reaches the formal correction command as string IDs', async () => {
  let payload
  const vm = view({ createRosterCorrection: async body => { payload = body; return { code: 0 } } })
  vm.materialFiles = [{ fileId: '9007199254740998', readyForBusiness: true }]
  vm.createVisible = true; await vm.submitCreate()
  assert.deepEqual(payload.materialFileIds, ['9007199254740998'])
  assert.equal(payload.studentId, '9007199254740999'); assert.equal(vm.createVisible, false)
})
test('correction rejects duplicate submit and retains fields and evidence after failure', async () => {
  let reject; let writes = 0
  const vm = view({ createRosterCorrection: () => { writes++; return new Promise((_, fail) => { reject = fail }) } })
  vm.materialFiles = [{ fileId: '12', readyForBusiness: true }]; vm.createVisible = true
  const pending = vm.submitCreate(); await vm.submitCreate()
  assert.equal(writes, 1); reject(new Error('网络断开')); await pending
  assert.equal(vm.createVisible, true); assert.equal(vm.form.newValue, 'fixture-only')
  assert.equal(vm.materialFiles[0].fileId, '12'); assert.equal(vm.submitting, false)
  assert.match(vm.formError, /网络断开/)
})
test('uploading blocks submit and closing, while a new student clears old evidence', async () => {
  let writes = 0
  const vm = view({ createRosterCorrection: async () => { writes++; return { code: 0 } } })
  vm.materialBusy = true; vm.createVisible = true
  await vm.submitCreate(); vm.closeCreate()
  assert.equal(writes, 0); assert.equal(vm.createVisible, true)
  vm.materialBusy = false; vm.materialFiles = [{ fileId: '12' }]
  vm.onStudentChange('8', [{ raw: { realName: '测试乙' } }])
  assert.deepEqual(vm.materialFiles, []); assert.equal(vm.form.studentName, '测试乙')
})
test('non-identity correction may submit without material and upload errors preserve input', async () => {
  let payload
  const vm = view({ createRosterCorrection: async body => { payload = body; return { code: 1, message: '请核实学号' } } })
  vm.form.fieldKey = 'STUDENT_NO'; vm.onMaterialError(new Error('上传失败'))
  assert.equal(vm.form.newValue, 'fixture-only')
  await vm.submitCreate(); assert.deepEqual(payload.materialFileIds, [])
  assert.equal(vm.formError, '请核实学号')
})


test('review with required missing or inaccessible evidence cannot approve', async () => {
  let writes = 0
  const vm = view({ reviewRosterCorrection: async () => { writes++; return { code: 0 } } }, { metadata: async () => { throw new Error('无权访问材料') } })
  vm.approveDialog = { visible: true, row: { correctionId: '2', status: 'PENDING', fieldKey: 'ID_CARD', materialFileIds: [] } }
  await vm.loadReviewMaterials(); await vm.doApprove()
  assert.equal(writes, 0); assert.match(vm.reviewMaterialsError, /缺少/)
  vm.approveDialog.row.materialFileIds = ['9007199254740998']
  await vm.loadReviewMaterials(); await vm.doApprove()
  assert.equal(writes, 0); assert.match(vm.reviewMaterialsError, /无权访问/)
})
test('review retry reads exact evidence and allows only safe authorized material', async () => {
  let ready = false; const ids = []; let writes = 0
  const vm = view({ reviewRosterCorrection: async () => { writes++; return { code: 0 } } }, { metadata: async id => { ids.push(id); return { fileId: id, readyForBusiness: ready, canPreview: ready } } })
  vm.approveDialog = { visible: true, row: { correctionId: '2', status: 'PENDING', fieldKey: 'ID_CARD', materialFileIds: ['9007199254740998'] } }
  await vm.loadReviewMaterials(); assert.equal(vm.reviewMaterialsReady, false)
  await vm.doApprove(); assert.equal(writes, 0)
  ready = true; await vm.loadReviewMaterials(); assert.equal(vm.reviewMaterialsReady, true)
  await vm.doApprove(); assert.equal(writes, 1)
  assert.deepEqual(ids, ['9007199254740998', '9007199254740998'])
})
test('late material response cannot populate a different correction review', async () => {
  let resolve
  const vm = view({}, { metadata: () => new Promise(done => { resolve = done }) })
  vm.approveDialog.row = { correctionId: '1', materialFileIds: ['11'] }
  const old = vm.loadReviewMaterials()
  vm.approveDialog.row = { correctionId: '2', fieldKey: 'GRADE', materialFileIds: [] }
  await vm.loadReviewMaterials()
  resolve({ fileId: '11', readyForBusiness: true, canPreview: true }); await old
  assert.deepEqual(vm.reviewMaterials, []); assert.equal(vm.reviewMaterialsLoading, false)
})
test('review double click is blocked and transport failure releases the original review', async () => {
  let reject; let writes = 0
  const vm = view({ reviewRosterCorrection: () => { writes++; return new Promise((_, fail) => { reject = fail }) } })
  vm.approveDialog = { visible: true, row: { correctionId: '2', status: 'PENDING', fieldKey: 'GRADE', materialFileIds: [] } }
  const pending = vm.doApprove(); await vm.doApprove(); assert.equal(writes, 1)
  reject(new Error('连接中断')); await pending
  assert.equal(vm.acting, false); assert.equal(vm.approveDialog.visible, true)
})

test('correction return only permits the original internship compliance route', () => {
  const vm = view()
  vm.$route.query.returnTo = '/admin/internship/compliance?tab=overview&batchId=7'
  assert.equal(vm.internshipReturn, vm.$route.query.returnTo)
  for (const target of ['https://outside.invalid', '//outside.invalid', '/admin/internship/compliance-fake', ['/admin/internship/compliance']]) {
    vm.$route.query.returnTo = target; assert.equal(vm.internshipReturn, '')
  }
})
