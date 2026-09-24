import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/InternshipPlanView.vue', import.meta.url), 'utf8')).descriptor.script.content
  .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[\s\S]*?\n {2}\},/, '')
  .replace('export default', 'return')
function view(api, stubChildren = true) {
  const definition = new Function('planApi', 'canCode', 'isConflict', 'toast', script)(api, () => true, res => res.code === 409001, { success() {}, error() {} })
  const vm = { ...definition.data(), batchId: '1', $route: { query: {} }, ctx: {} }
  for (const [key, method] of Object.entries(definition.methods)) vm[key] = method.bind(vm)
  if (stubChildren) vm.loadAcks = vm.loadProgressSummary = vm.reloadProgress = vm.loadProgress = () => {}
  for (const key of ['canEdit', 'canReview', 'draftSnapshot', 'dirty']) Object.defineProperty(vm, key, { get: () => definition.computed[key].call(vm) })
  return vm
}
test('missing plan stays editable instead of becoming a locked blank plan', async () => {
  const vm = view({ getBatchPlan: async () => ({ code: 0, data: {} }) })
  await vm.onBatchChange(); assert.equal(vm.plan, null); assert.equal(vm.canEdit, true)
})
test('failed plan request is shown as failure and cannot enable editing', async () => {
  const vm = view({ getBatchPlan: async () => ({ code: 503001, message: '服务不可用' }) })
  await vm.onBatchChange(); assert.equal(vm.loadError, '服务不可用'); assert.equal(vm.canEdit, false)
})
test('late plan response cannot overwrite the current batch', async () => {
  let finish
  const vm = view({ getBatchPlan: id => id === '1' ? new Promise(resolve => { finish = resolve }) : Promise.resolve({ code: 0, data: { id: 'new', title: '新批次', tasks: [] } }) })
  const old = vm.onBatchChange(); vm.batchId = '2'; await vm.onBatchChange()
  finish({ code: 0, data: { id: 'old', title: '旧批次' } }); await old
  assert.equal(vm.plan.id, 'new'); assert.equal(vm.form.title, '新批次')
})


test('plan panel navigation retains batch and does not discard unsaved form or tasks', () => {
  const vm = view({}); let target
  vm.$route = { path: '/admin/internship/plans', query: { batchId: '9007199254740999' } }
  vm.$router = { push: value => { target = value } }
  vm.form.title = '未保存计划'; vm.tasks = [{ name: '未保存任务' }]
  vm.selectPanel('tasks')
  assert.equal(target.query.batchId, '9007199254740999'); assert.equal(target.query.panel, 'tasks')
  assert.equal(vm.form.title, '未保存计划'); assert.equal(vm.tasks[0].name, '未保存任务')
})


test('saving carries original version and retains edits made while saving', async () => {
  let finish, payload
  const vm = view({ saveBatchPlan: (id, body) => { payload = body; return new Promise(resolve => { finish = resolve }) } })
  vm.plan = { id: '1', status: 'DRAFT', version: 4 }; vm.form = { title: '实习计划', objectives: '', content: '实习期间按要求完成工作任务并定期提交实习成果材料。' }; vm.tasks = [{ name: '提交报告' }]
  const saving = vm.save(); vm.form.title = '继续修改标题'
  finish({ code: 0, data: { id: '1', status: 'DRAFT', version: 5 } }); await saving
  assert.equal(payload.expectedVersion, 4); assert.equal(vm.form.title, '继续修改标题'); assert.equal(vm.dirty, true)
})

test('conflict preserves draft and blocks replay using a refreshed version', async () => {
  let calls = 0
  const vm = view({ saveBatchPlan: async () => { calls++; return { code: 409001 } } })
  vm.plan = { id: '1', status: 'DRAFT', version: 4 }; vm.form = { title: '实习计划', objectives: '', content: '实习期间按要求完成工作任务并定期提交实习成果材料。' }; vm.tasks = [{ name: '提交报告' }]
  await vm.save(); await vm.save()
  assert.equal(calls, 1); assert.equal(vm.plan.version, 4); assert.equal(vm.form.title, '实习计划'); assert.equal(vm.writeConflict, true)
})

test('un saved changes prevent publication before any request', async () => {
  const vm = view({ publishBatchPlan: () => assert.fail('must save changes first') })
  vm.plan = { id: '1', status: 'DRAFT', version: 4 }; vm.savedSnapshot = 'old'
  await vm.publish()
})


test('failed acknowledgement reload removes stale students and exposes the failure', async () => {
  const vm = view({ getPlanAcks: async () => ({ code: 503001, message: '读取失败' }) }, false)
  vm.acks = [{ id: 'old' }]; await vm.loadAcks()
  assert.deepEqual(vm.acks, []); assert.equal(vm.ackError, '读取失败')
})

test('late task progress results cannot replace newer filters', async () => {
  let finish
  const vm = view({ getTaskProgress: params => params.status === 'SUBMITTED' ? new Promise(resolve => { finish = resolve }) : Promise.resolve({ code: 0, data: { list: [{ id: 'new' }], total: 1 } }) }, false)
  vm.plan = { status: 'PUBLISHED' }; const old = vm.loadProgress()
  vm.progStatus = 'APPROVED'; await vm.loadProgress(); finish({ code: 0, data: { list: [{ id: 'old' }], total: 10 } }); await old
  assert.equal(vm.progRows[0].id, 'new'); assert.equal(vm.progTotal, 1)
})

test('previous batch summary cannot populate current batch counters', async () => {
  let finish
  const vm = view({ getTaskSummary: () => new Promise(resolve => { finish = resolve }) }, false)
  vm.plan = { status: 'PUBLISHED' }; const old = vm.loadProgressSummary(); vm.batchId = '2'
  finish({ code: 0, data: { studentCount: 99 } }); await old
  assert.equal(vm.taskSummary, null)
})


test('task review submits its original version and blocks conflict replay', async () => {
  let body, calls = 0
  const vm = view({ reviewTaskProgress: async (id, payload) => { calls++; body = payload; return { code: 409001 } } })
  vm.openReview({ id: '9007199254740999', version: 3, status: 'SUBMITTED', studentNote: '已完成' }, 'APPROVE')
  await vm.onReviewConfirm({ reason: '' }); await vm.onReviewConfirm({ reason: '' })
  assert.equal(body.expectedVersion, 3); assert.equal(calls, 1); assert.equal(vm.reviewConflict, true)
  assert.equal(vm.pendingReview.studentNote, '已完成')
})

test('task return requires an actionable reason before request', async () => {
  const vm = view({ reviewTaskProgress: () => assert.fail('short return reason must not submit') })
  vm.openReview({ id: '1', version: 3, status: 'SUBMITTED' }, 'REJECT')
  await vm.onReviewConfirm({ reason: '不行' }); assert.match(vm.reviewError, /至少 5 字/)
})


test('task review deep link preserves exact id and return filters', () => {
  const vm = view({}); let target
  vm.$route = { path: '/admin/internship/plans', query: { batchId: '8' } }; vm.$router = { push: value => { target = value } }
  vm.progPage = 3; vm.progStatus = 'SUBMITTED'; vm.progKeyword = '测试'; vm.progTaskOrder = '2'
  vm.openTaskReview({ id: '9007199254740999' })
  assert.equal(target.query.reviewId, '9007199254740999'); assert.equal(target.query.progPage, '3'); assert.equal(target.query.batchId, '8')
  vm.$route.query = target.query; vm.closeTaskReview()
  assert.equal(target.query.reviewId, undefined); assert.equal(target.query.progKeyword, '测试'); assert.equal(target.query.progTaskOrder, '2')
})
