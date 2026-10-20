import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { emptyConflict, isConflict, captureConflict } from '../src/modules/internship/composables/conflictGuard.js'
const descriptors = Object.fromEntries(['EnterpriseEvalView', 'EnterpriseEvalFormView'].map(name => [name, parse(fs.readFileSync(new URL(`../src/modules/internship/views/${name}.vue`, import.meta.url), 'utf8')).descriptor]))
function setup(name, api = {}, files = {}) {
  const script = descriptors[name].script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace(/ {2}components: \{[\s\S]*?\},\r?\n/, '').replace('export default', 'return')
  let saved = false
  const def = new Function('enterpriseEvalApi', 'uploadAttachment', 'downloadAttachment', 'emptyConflict', 'isConflict', 'captureConflict', 'canCode', 'toast', 'ENTERPRISE_EVAL_COMMENT', 'window', script)(api, files.upload, files.download, emptyConflict, isConflict, captureConflict, () => true, { success() {}, error() {} }, [], { __SAAS_DIRTY_FORM_GUARD__: { markSaved: () => { saved = true } } })
  const targets = []
  const vm = { ...def.data(), ctx: {}, $refs: {}, batchStore: { selectedBatchId: '1', withBatchQuery: q => ({ ...q, batchId: '1' }) }, $route: { query: {}, fullPath: '/enterprise-evals' }, $router: { push: t => targets.push(t), replace: t => targets.push(t), options: { history: { state: {} } } } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  return { vm, def, targets, isSaved: () => saved }
}
function reviewReady(vm) { vm.selectedId = '8'; vm.detail.data = { id: '8', reviewStatus: 'PENDING', version: 2 }; vm.openReview(vm.detail.data, 'APPROVE') }
function fill(vm) { Object.assign(vm.form, { internshipId: '9007199254740999', mentorName: '测试导师', attendanceScore: 0, skillScore: 80, attitudeScore: 90, collaborationScore: 80, safetyScore: 90, fileId: 'file8' }) }

test('enterprise evaluation list and form templates compile', () => {
  for (const [name, d] of Object.entries(descriptors)) assert.deepEqual(compileTemplate({ source: d.template.content, filename: name + '.vue', id: name }).errors, [])
})
test('old list and same-ID detail are discarded on context reset', async () => {
  let listDone, detailDone
  const { vm } = setup('EnterpriseEvalView', { getEvals: () => new Promise(r => { listDone = r }), getDetail: () => new Promise(r => { detailDone = r }) })
  vm.selectedId = '8'; const list = vm.load(), detail = vm.loadDetail('8')
  vm.batchStore.selectedBatchId = '2'; vm.resetDetail(); vm.rows = [{ id: 'new' }]
  listDone({ code: 0, data: { list: [{ id: 'old' }], total: 8 } }); detailDone({ code: 0, data: { id: '8' } }); await list; await detail
  assert.equal(vm.rows[0].id, 'new'); assert.equal(vm.detail.data, null)
})
test('empty review filter and page survive deep-link restoration', () => {
  const { vm, targets } = setup('EnterpriseEvalView'); vm.load = () => {}
  vm.$route.query = { id: '9007199254740999', page: '3', reviewStatus: '', keyword: '测试', batchId: '1' }; vm.applyQuery()
  assert.equal(vm.page, 3); assert.equal(vm.statusFilter, '')
  vm.onPageChange({ page: 4 }); assert.equal(targets[0].query.page, '4'); assert.equal(targets[0].query.id, '9007199254740999'); assert.equal(targets[0].query.keyword, '测试')
})
test('conflict preserves the review version and comment and blocks retries', async () => {
  let finish, writes = 0
  const { vm } = setup('EnterpriseEvalView', { review: async () => { writes++; return { code: 409001 } }, getDetail: () => new Promise(r => { finish = r }) }); reviewReady(vm)
  const old = vm.onConfirm({ reason: '已核对扫描件内容' }); await Promise.resolve(); assert.equal(vm.conflict.active, true)
  await vm.onConfirm({ reason: '不能重复' }); assert.equal(writes, 1)
  finish({ code: 0, data: { id: '8', version: 3, reviewStatus: 'APPROVED' } }); await old
  assert.equal(vm.pending.version, 2); assert.equal(vm.conflict.kept, '已核对扫描件内容')
})
test('adding an explicit empty status overrides the implicit pending filter even on the same page', () => {
  const { vm, def } = setup('EnterpriseEvalView'); let loads = 0; vm.load = () => { loads++ }
  const previous = { page: '1', batchId: '1' }
  vm.$route.query = { ...previous, reviewStatus: '' }
  def.watch['$route.query'].handler.call(vm, vm.$route.query, previous)
  assert.equal(loads, 1); assert.equal(vm.statusFilter, '')
})
test('late review and failed queue readback never advance a new selection or claim completion', async () => {
  let finish
  const { vm } = setup('EnterpriseEvalView', { review: () => new Promise(r => { finish = r }), getEvals: async () => ({ code: 1, message: '读取失败' }) }); reviewReady(vm)
  const old = vm.onConfirm({ reason: '' }); vm.resetDetail(); vm.selectedId = 'new'
  finish({ code: 0, data: { id: '8', reviewStatus: 'APPROVED' } }); await old
  assert.equal(vm.lastReceipt, null); assert.equal(vm.selectedId, 'new')
  await vm.advanceAfterReview('new'); assert.equal(vm.doneHint, false); assert.equal(vm.selectedId, 'new')
})
test('material download uses the exported helper and ignores an old failure', async () => {
  let reject, fileId
  const { vm } = setup('EnterpriseEvalView', {}, { download: id => { fileId = id; return new Promise((_r, e) => { reject = e }) } })
  vm.detail.data = { attachment: { fileId: '9007199254740999', fileName: '评价.pdf' } }
  const old = vm.downloadAtt(); assert.equal(fileId, '9007199254740999'); vm.resetDetail(); reject(new Error('旧文件失败')); await old
  assert.equal(vm.attachmentError, ''); assert.equal(vm.downloading, false)
})
test('scan is mandatory and noninteger scores cannot be submitted, while zero is valid', async () => {
  const { vm, def } = setup('EnterpriseEvalFormView', { create: () => assert.fail('invalid form must not submit') }); fill(vm)
  vm.form.fileId = ''; await vm.doSubmit(); assert.match(vm.submitError, /扫描件/)
  vm.form.fileId = 'file8'; vm.form.skillScore = 80.5; await vm.doSubmit(); assert.match(vm.submitError, /整数/)
  vm.form.skillScore = 80; assert.equal(def.computed.averageScore.call(vm), '68.0')
})
test('upload blocks submit and late upload cannot bind to another batch form', async () => {
  let finish, calls = 0
  const { vm, def } = setup('EnterpriseEvalFormView', { create: () => assert.fail('upload in progress') }, { upload: () => { calls++; return new Promise(r => { finish = r }) } }); fill(vm)
  const old = vm.onFilePick({ target: { files: [{ name: '评价.pdf' }] } }); await vm.doSubmit(); assert.equal(calls, 1)
  def.watch['batchStore.selectedBatchId'].call(vm)
  finish({ code: 0, data: { fileId: 'oldfile' } }); await old; assert.equal(vm.form.fileId, '')
})
test('failed create keeps input and successful create opens the exact record after clearing dirty state', async () => {
  let fail = true
  const { vm, targets, isSaved } = setup('EnterpriseEvalFormView', { create: async p => { assert.equal(p.attendanceScore, 0); return fail ? { code: 1, message: '来源材料无效' } : { code: 0, data: { id: '9007199254740999' } } } }); fill(vm)
  await vm.doSubmit(); assert.equal(vm.form.mentorName, '测试导师'); assert.equal(vm.submitError, '来源材料无效'); assert.equal(targets.length, 0)
  fail = false; await vm.doSubmit(); assert.equal(isSaved(), true); assert.equal(targets[0].query.id, '9007199254740999'); assert.equal(targets[0].query.batchId, '1')
})
test('invalid submit scrolls and focuses the first invalid field without writing', async () => {
  const { vm } = setup('EnterpriseEvalFormView', { create: () => assert.fail('invalid input') })
  let scrolled = false, focused = false
  vm.$nextTick = async () => {}
  vm.$refs.formRef = { validate: async () => ({ valid: false }), $el: { querySelector: () => ({ scrollIntoView: () => { scrolled = true }, querySelector: () => ({ focus: () => { focused = true } }) }) } }
  await vm.onSubmitClick(); assert.equal(scrolled, true); assert.equal(focused, true)
})
