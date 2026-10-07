import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { emptyConflict, isConflict, captureConflict } from '../src/modules/internship/composables/conflictGuard.js'
const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/StudentEvalView.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace(/ {2}components: \{[\s\S]*?ActionReceipt, AppInlineAlert \},/, '').replace('export default', 'return')
function setup(api = {}, download = async () => {}) {
  const def = new Function('studentEvalApi', 'downloadAttachment', 'emptyConflict', 'isConflict', 'captureConflict', 'canCode', 'toast', 'ENTERPRISE_EVAL_COMMENT', 'REJECT_STUDENT_EVAL', 'ADVISOR_EVAL_COMMENT', script)(api, download, emptyConflict, isConflict, captureConflict, () => true, { success() {}, error() {} }, [], [], [])
  const targets = []
  const vm = { ...def.data(), ctx: {}, batchStore: { selectedBatchId: '1', withBatchQuery: q => ({ ...q, batchId: '1' }) }, $route: { query: {}, fullPath: '/student-evals' }, $router: { replace: t => targets.push(t), push: t => targets.push(t) } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(def.computed)) if (key !== 'batchStore') Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, def, targets }
}
const record = (extra = {}) => ({ id: '8', batchId: '1', version: 2, submitStatus: 'SUBMITTED', reviewStatus: 'PENDING', advisorOpinion: '已保存的指导意见', mentorOpinion: '', ...extra })
function select(vm, row = record()) { vm.selectedId = row.id; vm.detail.data = row; vm.restoreComment() }

test('student and teacher evaluation template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'StudentEvalView.vue', id: 'student-eval' }).errors, [])
})
test('late list and detail cannot repopulate a switched batch', async () => {
  let finishList, finishDetail
  const { vm } = setup({ getEvals: () => new Promise(r => { finishList = r }), getDetail: () => new Promise(r => { finishDetail = r }) })
  select(vm); const list = vm.load(), detail = vm.loadDetail('8'); vm.batchStore.selectedBatchId = '2'; vm.resetDetail(false)
  finishList({ code: 0, data: { list: [record()], total: 1 } }); finishDetail({ code: 0, data: record() }); await list; await detail
  assert.equal(vm.detail.data, null); assert.deepEqual(vm.rows, [])
})
test('deep link restores view, empty status, keyword and page with large IDs intact', () => {
  const { vm, targets } = setup(); vm.load = () => {}
  vm.$route.query = { view: 'advisor', reviewStatus: '', keyword: '测试', page: '3', id: '9007199254740999' }; vm.applyQuery()
  assert.equal(vm.viewFilter, 'advisor'); assert.equal(vm.statusFilter, ''); assert.equal(vm.page, 3)
  vm.onPageChange({ page: 4 }); assert.equal(targets[0].query.id, '9007199254740999'); assert.equal(targets[0].query.batchId, '1')
})
test('an out-of-batch detail is never rendered', async () => {
  const { vm } = setup({ getDetail: async () => ({ code: 0, data: record({ batchId: '2' }) }) }); vm.selectedId = '8'; await vm.loadDetail('8')
  assert.equal(vm.detail.data, null); assert.match(vm.detail.error, /不属于当前批次/)
})
test('unsaved comments survive selection reset and stale draft versions block saving', async () => {
  const { vm } = setup({ getDetail: async () => ({ code: 0, data: record({ version: 3 }) }), advisorComment: () => assert.fail('stale draft must not save') })
  select(vm); vm.cmtForm.advisorOpinion = '正在填写的完整意见'; vm.resetDetail(); vm.selectedId = '8'; await vm.loadDetail('8')
  assert.equal(vm.cmtForm.advisorOpinion, '正在填写的完整意见'); assert.equal(vm.cmtVersion, 2); assert.equal(vm.commentConflict.active, true)
  await vm.submitComment(); vm.restoreComment(); assert.equal(vm.cmtVersion, 3); assert.equal(vm.commentDirty, false)
})
test('comment conflict keeps text and original version even after successful readback', async () => {
  let writes = 0
  const { vm } = setup({ advisorComment: async () => { writes++; return { code: 409001 } }, getDetail: async () => ({ code: 0, data: record({ version: 4, advisorOpinion: '另一位老师的新意见' }) }) })
  select(vm); vm.cmtForm.advisorOpinion = '我的未保存意见'; await vm.submitComment()
  assert.equal(vm.cmtForm.advisorOpinion, '我的未保存意见'); assert.equal(vm.cmtVersion, 2); assert.equal(vm.commentConflict.active, true)
  await vm.submitComment(); assert.equal(writes, 1)
})
test('failed comment save preserves input and late success cannot change new selection', async () => {
  let finish
  const { vm } = setup({ advisorComment: () => new Promise(r => { finish = r }) }); select(vm); vm.cmtForm.advisorOpinion = '我的未保存意见'
  const first = vm.submitComment(); finish({ code: 1, message: '保存失败' }); await first
  assert.equal(vm.commentError, '保存失败'); assert.equal(vm.cmtForm.advisorOpinion, '我的未保存意见')
  const second = vm.submitComment(); vm.resetDetail(); vm.selectedId = '9'; finish({ code: 0, data: { id: '8', version: 3 } }); await second
  assert.equal(vm.lastReceipt, null); assert.equal(vm.selectedId, '9')
})
test('approval requires saved advisor opinion and excludes concurrent comment changes', () => {
  const { vm } = setup(); select(vm, record({ advisorOpinion: '' }))
  vm.openReview(vm.detail.data, 'APPROVE'); assert.equal(vm.pending, null)
  vm.openReview(vm.detail.data, 'RETURN'); assert.equal(vm.pending.action, 'RETURN')
  vm.pending = null; vm.cmtForm.advisorOpinion = '未保存意见'; vm.openReview(vm.detail.data, 'RETURN'); assert.equal(vm.pending, null)
})
test('review conflict blocks immediate retries and preserves original snapshot', async () => {
  let finish, writes = 0
  const { vm } = setup({ review: async () => { writes++; return { code: 409001 } }, getDetail: () => new Promise(r => { finish = r }) }); select(vm); vm.openReview(vm.detail.data, 'APPROVE')
  const pending = vm.onConfirm({ reason: '审核填写内容' }); await Promise.resolve(); assert.equal(vm.conflict.active, true)
  await vm.onConfirm({ reason: '重复点击' }); assert.equal(writes, 1)
  finish({ code: 0, data: record({ version: 3, reviewStatus: 'APPROVED' }) }); await pending
  assert.equal(vm.pending.version, 2); assert.equal(vm.conflict.kept, '审核填写内容')
})
test('queue readback failure cannot report all records processed', async () => {
  const { vm } = setup({ getEvals: async () => ({ code: 1, message: '读取失败' }) }); select(vm)
  await vm.advanceAfterReview('8'); assert.equal(vm.selectedId, '8'); assert.equal(vm.doneHint, false)
})
test('identity context changes clear drafts and invalidate old selection', () => {
  const { vm, def } = setup(); select(vm); vm.cmtForm.advisorOpinion = '未保存意见'; vm.load = () => {}
  def.watch.ctx.handler.call(vm); assert.deepEqual(vm.commentDrafts, {}); assert.equal(vm.detail.data, null); assert.equal(vm.selectedId, '')
})
test('download errors from a previous record are ignored', async () => {
  let reject
  const { vm } = setup({}, () => new Promise((_r, e) => { reject = e })); select(vm, record({ attachment: { fileId: 'file8' } }))
  const old = vm.downloadAtt(); vm.resetDetail(); reject(new Error('旧文件失败')); await old
  assert.equal(vm.attachmentError, ''); assert.equal(vm.downloading, false)
})
