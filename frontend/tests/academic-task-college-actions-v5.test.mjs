import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { setImmediate } from 'node:timers'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import { matchPermission } from '../src/config/navPlan.js'
import * as teaching from '../src/modules/academicAffairs/constants/teaching.js'
import * as results from '../src/modules/academicAffairs/components/parallel-a/resultState.js'
import { readTaskPages } from '../src/modules/academicAffairs/components/parallel-a/taskFacts.js'
import * as flow from '../src/modules/academicAffairs/config/academicFlowRegistry.js'

const ok = data => ({ code: 0, data })
const listed = rows => ok({ list: rows, total: rows.length })
const ctx = (scope = 'COLLEGE') => ({ currentRole: { roleCode: 'CUSTOM_COLLEGE_ROLE' }, dataScope: { scope }, permissionPatterns: ['academicAffairs.teachingTask.*'] })
const row = { taskId: '9007199254740997', batchId: '9007199254740993', courseId: '7', teacherKey: 'teacher', teacherName: '任课教师', status: 'ASSIGNED', weeklyHours: 2, totalHours: 32, startWeek: 1, endWeek: 16, expectedStudents: 20 }
const second = { ...row, taskId: '9007199254740999' }
const workbench = (allowed = true, batchId = row.batchId) => ({ batchId, actions: { canAssign: allowed, canAdjust: allowed, canEditComposition: allowed } })
function instance(name, api = {}, getBatch = async () => ok(workbench())) {
  return page(name, { ...teaching, ...results, ...flow, matchPermission, readTaskPages,
    academicAffairsApi: { listAllTasks: async () => listed([row, second]), getBatchTasks: async () => listed([row]), ...api },
    teachingTaskWorkbenchApi: { getBatch }
  }, { ctx: ctx() })
}

test('学校仅查看：有动作权限也不能打开学院调整、合班或拆班确认', async () => {
  for (const scope of ['TENANT_ALL', 'SCHOOL', 'ASSIGNED', 'NONE']) {
    let reads = 0
    const a = instance('AaTaskAdjustView', {}, async () => { reads++; return ok(workbench()) }).state
    a.ctx = ctx(scope); a.loading = false
    await a.openAdjust(row)
    assert.equal(a.adjust.visible, false); assert.equal(a.canAdjust, false); assert.match(a.scopeReadOnlyReason, /责任学院/)
    const m = instance('AaTaskMergeSplitView', {}, async () => { reads++; return ok(workbench()) }).state
    m.ctx = ctx(scope); m.loading = false; m.all = [row, second]; m.selected = [row.taskId, second.taskId]
    await m.openMerge({ key: 'merge' }); await m.openSplit({ ...row, isMerged: true })
    assert.equal(m.mergeDialog.visible, false); assert.equal(m.splitRow, null); assert.equal(reads, 0)
  }
})

test('学院调整先只读核所选批次，后端不允许或对象不符时不开放表单', async () => {
  for (const body of [workbench(false), workbench(true, 'other-batch')]) {
    const { state } = instance('AaTaskAdjustView', {}, async id => { assert.equal(id, row.batchId); return ok(body) })
    state.loading = false
    await state.openAdjust(row)
    assert.equal(state.adjust.visible, false); assert.equal(state.canAdjust, false); assert.ok(state.actionError)
  }
  const { state } = instance('AaTaskAdjustView')
  state.loading = false; await state.openAdjust(row)
  assert.equal(state.adjust.visible, true); assert.equal(state.canAdjust, true); assert.equal(state.adjust.taskId, row.taskId)
})

test('调整确认前回读已撤销的动作，不发送写请求并保留原修改', async () => {
  let reads = 0, writes = 0
  const { state } = instance('AaTaskAdjustView', { adjustTask: async () => { writes++ } }, async () => ok(workbench(++reads === 1)))
  state.loading = false; await state.openAdjust(row)
  state.adjust.reason = '核对正式学时后调整'; state.adjust.weeklyHours = 3
  await state.doAdjust()
  assert.equal(reads, 2); assert.equal(writes, 0); assert.equal(state.adjust.reason, '核对正式学时后调整'); assert.equal(state.adjust.weeklyHours, 3)
  assert.equal(state.adjust.submitting, false); assert.equal(state.receipt, null); assert.match(state.actionError, /不允许调整/)
})

test('学院调整写后按原批次和字符串任务身份回读正式值', async () => {
  let writes = 0
  const { state } = instance('AaTaskAdjustView', {
    adjustTask: async (id, body) => { assert.equal(id, row.taskId); assert.equal(body.weeklyHours, 3); writes++; return ok({}) },
    getBatchTasks: async id => { assert.equal(id, row.batchId); return listed([{ ...row, weeklyHours: 3 }]) }
  })
  state.loading = false; await state.openAdjust(row); state.adjust.reason = '核对正式学时后调整'; state.adjust.weeklyHours = 3
  await state.doAdjust()
  assert.equal(writes, 1); assert.equal(state.receipt.pending, false); assert.equal(state.adjust.submitting, false)
})

test('姓名显示更正不冒充换任课教师，正式身份变化才说明教师重确认及原批次重审', async () => {
  const { state } = instance('AaTaskAdjustView')
  state.loading = false; await state.openAdjust(row)
  state.adjust.teacherName = '更正后的教师姓名'
  assert.equal(state.teacherChangedInDialog, false)
  state.adjust.teacherKey = 'another-teacher'
  assert.equal(state.teacherChangedInDialog, true)
  state.handleFailure({ code: 409001, message: '已有课表，不能直接更换教师' })
  assert.match(state.receipt.next, /正式任课关系/); assert.match(state.receipt.next, /排课变更/)
  assert.equal(state.adjust.teacherKey, 'another-teacher')
})

test('调整办理条件的迟到响应不能打开新身份或已卸载页面', async () => {
  for (const change of ['identity', 'unmount']) {
    const pending = deferred(), { state, definition } = instance('AaTaskAdjustView', {}, () => pending.promise)
    state.loading = false
    const run = state.openAdjust(row)
    if (change === 'identity') { state.ctx = ctx('TENANT_ALL'); definition.watch.ctx.handler.call(state) }
    else definition.beforeUnmount.call(state)
    pending.resolve(ok(workbench())); await run
    assert.equal(state.adjust.visible, false); assert.deepEqual(Object.keys(state.batchWorkbench), [])
  }
})

test('合班候选只读加载不为每行请求批次，选定同批次才读取一次办理条件', async () => {
  let reads = 0
  const { state } = instance('AaTaskMergeSplitView', {}, async id => { reads++; assert.equal(id, row.batchId); return ok(workbench()) })
  await state.load(); assert.equal(reads, 0)
  state.selected = [row.taskId, second.taskId]
  assert.equal(state.canMerge, false)
  await state.openMerge({ key: 'merge' })
  assert.equal(reads, 1); assert.equal(state.mergeDialog.visible, true); assert.equal(state.canMerge, true)
})

test('合班和拆班均依赖当前批次canEditComposition，不由权限或状态推导', async () => {
  const merged = { ...row, isMerged: true }
  const { state } = instance('AaTaskMergeSplitView', {}, async () => ok(workbench(false)))
  state.loading = false; state.all = [row, second, merged]; state.selected = [row.taskId, second.taskId]
  // Candidate IDs must remain unique in the formal list.
  state.all = [row, second]
  await state.openMerge({ key: 'merge' })
  assert.equal(state.mergeDialog.visible, false); assert.equal(state.canMerge, false)
  await state.openSplit(merged)
  assert.equal(state.splitRow, null); assert.equal(state.canSplit(merged), false); assert.match(state.actionError, /不允许合拆班/)
})

test('确认合班前动作被撤销或候选已确认时不发送写请求并保留备注', async () => {
  for (const changed of ['authority', 'candidate']) {
    let reads = 0, writes = 0
    const { state } = instance('AaTaskMergeSplitView', { listAllTasks: async () => listed(changed === 'candidate' ? [{ ...row, status: 'TEACHER_CONFIRMED' }] : [row, second]), mergeTasks: async () => { writes++ } }, async () => ok(workbench(++reads === 1)))
    state.loading = false; state.all = [row, second]; state.selected = [row.taskId, second.taskId]
    await state.openMerge({ key: 'merge' }); state.mergeDialog.note = '正式名单核对备注'
    await state.doMerge()
    assert.equal(writes, 0); assert.equal(state.mergeDialog.note, '正式名单核对备注'); assert.equal(state.merging, false)
    assert.ok(state.actionError || state.error)
  }
})

test('学院合班使用相同批次动作并回读正式合并关系', async () => {
  let merged = false
  const { state } = instance('AaTaskMergeSplitView', {
    listAllTasks: async () => listed(merged ? [{ ...row, isMerged: true }, { ...second, status: 'MERGED', mergedIntoId: row.taskId }] : [row, second]),
    mergeTasks: async ids => { assert.deepEqual(Array.from(ids), [row.taskId, second.taskId]); merged = true; return ok({}) }
  })
  state.loading = false; state.all = [row, second]; state.selected = [row.taskId, second.taskId]
  await state.openMerge({ key: 'merge' }); await state.doMerge()
  assert.equal(merged, true); assert.equal(state.receipt.pending, false); assert.equal(state.merging, false); assert.equal(state.selected.length, 0)
})

test('学院拆班在提交前再读动作，撤销不写，允许时回读正式还原关系', async () => {
  for (const allowed of [false, true]) {
    let reads = 0, split = false
    const merged = { ...row, isMerged: true }
    const { state } = instance('AaTaskMergeSplitView', {
      listAllTasks: async () => listed(split ? [row] : [merged]),
      splitTask: async id => { assert.equal(id, row.taskId); split = true; return ok({}) }
    }, async () => ok(workbench(++reads === 1 || allowed)))
    state.loading = false; state.all = [merged]
    await state.openSplit(merged); assert.equal(state.splitRow, merged)
    await state.doSplit(merged)
    assert.equal(split, allowed); assert.equal(reads, 2); assert.equal(state.merging, false)
    if (allowed) { assert.equal(state.receipt.pending, false); assert.equal(state.splitRow, null) }
    else assert.match(state.actionError, /不允许合拆班/)
  }
})

test('切选任务、切身份和卸载均丢弃迟到合拆班条件，不打开旧批次确认', async () => {
  for (const change of ['selection', 'identity', 'unmount']) {
    const pending = deferred(), { state, definition } = instance('AaTaskMergeSplitView', {}, () => pending.promise)
    state.loading = false; state.all = [row, second]; state.selected = [row.taskId, second.taskId]
    const run = state.openMerge({ key: 'merge' })
    if (change === 'selection') { state.selected = []; definition.watch.selectionKey.call(state) }
    else if (change === 'identity') { state.ctx = ctx('TENANT_ALL'); definition.watch.ctx.handler.call(state) }
    else definition.beforeUnmount.call(state)
    pending.resolve(ok(workbench())); await run
    assert.equal(state.mergeDialog.visible, false); assert.deepEqual(Object.keys(state.batchWorkbench), [])
  }
})

test('学院条件读取403清除旧私有任务且保留可见拒绝说明', async () => {
  const { state, definition } = instance('AaTaskMergeSplitView', {}, async () => ({ code: 403001, message: '当前学院任职已失效' }))
  state.loading = false; state.all = [row, second]; state.selected = [row.taskId, second.taskId]
  await state.openMerge({ key: 'merge' }); definition.watch.selectionKey.call(state)
  assert.equal(state.all.length, 0); assert.equal(state.selected.length, 0); assert.equal(state.actionLoading, false); assert.equal(state.actionError, '当前学院任职已失效')
})

test('已发出的调整和合班回执在身份变更后不回读旧对象或覆盖新界面', async () => {
  const adjustWrite = deferred(); let adjustReadbacks = 0, writeStarted = false
  const a = instance('AaTaskAdjustView', {
    adjustTask: async () => { writeStarted = true; return adjustWrite.promise },
    getBatchTasks: async () => { adjustReadbacks++; return listed([row]) }
  })
  a.state.loading = false; await a.state.openAdjust(row); a.state.adjust.reason = '核对正式学时后调整'
  const adjusting = a.state.doAdjust()
  await new Promise(resolve => setImmediate(resolve)); assert.equal(writeStarted, true)
  a.state.ctx = ctx('TENANT_ALL'); a.definition.watch.ctx.handler.call(a.state)
  adjustWrite.resolve(ok({})); await adjusting
  assert.equal(adjustReadbacks, 0); assert.equal(a.state.receipt, null); assert.equal(a.state.adjust.visible, false)

  const mergeWrite = deferred(); writeStarted = false
  const m = instance('AaTaskMergeSplitView', { mergeTasks: async () => { writeStarted = true; return mergeWrite.promise } })
  m.state.loading = false; m.state.all = [row, second]; m.state.selected = [row.taskId, second.taskId]
  await m.state.openMerge({ key: 'merge' }); const merging = m.state.doMerge()
  await new Promise(resolve => setImmediate(resolve)); assert.equal(writeStarted, true)
  m.state.ctx = ctx('TENANT_ALL'); m.definition.watch.ctx.handler.call(m.state)
  mergeWrite.resolve(ok({})); await merging
  assert.equal(m.state.receipt, null); assert.equal(m.state.mergeDialog.visible, false); assert.equal(m.state.merging, false)
})

test('实际确认模板在批次条件未核实时禁确认，并展示中文只读与错误', async () => {
  for (const name of ['AaTaskAdjustView', 'AaTaskMergeSplitView']) {
    const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
    const templates = source.match(/<AppConfirmDialog[\s\S]*?<\/AppConfirmDialog>/g)
    assert.ok(templates.length)
    for (const template of templates) {
      const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
      const { state } = instance(name)
      state.adjust = { visible: true, taskId: row.taskId }; state.mergeDialog = { visible: true }; state.splitRow = row
      state.actionError = '当前批次不允许办理'
      delete state.$route; delete state.$router
      const app = Vue.createSSRApp({ render, setup: () => state, components: {
        AppConfirmDialog: { props: ['confirmDisabled'], setup: (props, { slots }) => () => Vue.h('section', [Vue.h('button', { disabled: props.confirmDisabled }, '确认'), slots.default?.()]) },
        AppInlineAlert: { props: ['description'], setup: props => () => Vue.h('p', props.description) },
        AaObjectContext: { render: () => null }, AppQuickPhrases: { render: () => null }, AppTeacherPicker: { render: () => null }
      } })
      const html = await renderToString(app)
      assert.match(html, /<button disabled>确认/); assert.match(html, /当前批次不允许办理/)
    }
  }
})

test('真实分配工作区继续以canAssign裁决，学校显示只读责任说明', () => {
  const { state } = instance('AaTaskDetailView')
  state.ctx = ctx('TENANT_ALL'); state.workbench = workbench(false)
  assert.equal(state.schoolReadOnly, true); assert.equal(state.canAssignRow(row), false)
  state.ctx = ctx(); assert.equal(state.canAssignRow(row), false)
  state.workbench = workbench(); assert.equal(state.canAssignRow(row), true)
})
