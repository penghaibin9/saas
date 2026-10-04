import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import * as teaching from '../src/modules/academicAffairs/constants/teaching.js'

// Execute the page's actual Options API methods with controlled transport responses.
function page(name, dependencies = {}, globals = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/\s+as\s+/g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const context = { dependencies, ...globals }
  vm.runInNewContext(script, context)
  return context.component
}

test('排课学时缺额按权威结果显示，旧课位缺排与超排不能互相抵消', () => {
  const component = page('AaSchedulingConsoleView')
  const state = { ...component.methods, workbench: { expectedHours: 8, scheduledHours: 7, missing: [{ remainingSessions: 4 }], over: [{ expectedSessions: 2, scheduledSessions: 5 }] } }
  assert.equal(component.computed.repairRemaining.call(state), 4)
  assert.equal(state.contactMetrics(state.workbench).known, false)
  state.workbench = { expectedContactHours: 36, scheduledContactHours: 26, missingContactHours: 12, excessContactHours: 2, weeklyOverloadCount: 1, scheduledItemCount: 2 }
  assert.equal(component.computed.repairRemaining.call(state), 12)
  const metrics = state.contactMetrics(state.workbench)
  assert.equal(metrics.scheduled, 26)
  assert.equal(metrics.excess, 2)
  assert.equal(metrics.itemCount, 2)
  state.workbench = { ...state.workbench, batchStatus: 'PUBLISHED', missingContactHours: 0 }
  state.repairRemaining = 0
  assert.equal(component.computed.hasPublishedGap.call(state), true)
})

test('发布清单按总计划学时及逐周超量显示，未知学时不能显示通过', () => {
  const component = page('AaSchedulePublishView')
  const state = { ...component.methods, gate: { summary: { complete: true, expectedContactHours: 36, scheduledContactHours: 36, missingContactHours: 0, excessContactHours: 0, weeklyOverloadCount: 1 } } }
  let checks = component.computed.gateChecklist.call(state)
  assert.equal(checks.find(row => row.label === '计划总学时完整').ok, true)
  assert.equal(checks.find(row => row.label === '每周学时未超量').ok, false)
  state.gate.summary = { complete: true }
  checks = component.computed.gateChecklist.call(state)
  assert.equal(checks.find(row => row.label === '计划总学时完整').ok, false)
  assert.match(checks.find(row => row.label === '计划总学时完整').detail, /待核对/)
})

test('纠错回执区分课位条数和展开学时，未知回执不伪造学时', async () => {
  const messages = []
  let receipt = { batchId: '47', scheduledItemCount: 9, expectedContactHours: 36, scheduledContactHours: 26, missingContactHours: 10, excessContactHours: 0, weeklyOverloadCount: 0 }
  const component = page('AaSchedulingConsoleView', { toast: { success: text => messages.push(text) }, academicAffairsApi: { startScheduleCorrection: async () => ({ code: 0, data: receipt }) } })
  const state = { ...component.methods, workbenchBatchId: '44', correctionTargetTask: null, commandContextKey: () => 'same', loadWorkbench: async () => {} }
  await state.createCorrectionDraft('补齐课程计划')
  assert.match(messages[0], /保留 9 条现有课位/)
  assert.match(messages[0], /已排 26 学时.*缺 10 学时/)
  receipt = { batchId: '48', scheduledSessions: 9, remainingSessions: 1 }
  await state.createCorrectionDraft('重新核对计划')
  assert.match(messages[1], /待核对/)
  assert.doesNotMatch(messages[1], /已排 9 学时|缺 1 学时/)
})

test('传统自动排课新增量是课位条数，分段漏排显示实际周段与缺学时', async () => {
  const messages = []
  const component = page('AaSchedulingConsoleView', { toast: { success: text => messages.push(text) }, academicAffairsSchedulingApi: { autoSchedule: async () => ({ code: 0, data: { placedSessions: 3 } }) } })
  const state = { ...component.methods, autoBatchId: '47', commandContextKey: () => 'same' }
  await state.runAuto(false)
  assert.equal(messages[0], '已新增 3 条课位')
  assert.match(state.autoMissText({ startWeek: 6, endWeek: 18, needSessions: 2, placedSessions: 1, missingContactHours: 13 }), /第 6—18 周.*缺 13 学时.*1 \/ 2 条课位/)
  assert.match(state.autoMissText({ needSessions: 2, placedSessions: 1 }), /待核对/)
})

test('重复开课任务只提供教学任务核对入口，不引导补排或创建纠错草稿', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaSchedulingConsoleView.vue', import.meta.url), 'utf8')
  const template = source.match(/<template #cell-ops="\{ row \}">([\s\S]*?)<\/template>/)[1]
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const component = page('AaSchedulingConsoleView')
  let destination
  const state = { ...component.methods, row: { taskId: '14944', classId: '4670', issueType: 'SOURCE_CONFLICT', canSchedule: true }, hasPublishedGap: true, canCorrectSchedule: true, workbench: { batchStatus: 'PUBLISHED', termId: '52' }, $router: { push: route => { destination = typeof route === 'string' ? { path: route, query: {} } : route } } }
  const visible = { ...state }
  delete visible.$router
  const html = await renderToString(Vue.createSSRApp({ render, setup: () => visible }))
  assert.match(html, /核对重复开课任务/)
  assert.doesNotMatch(html, /去排课|创建草稿后补排/)
  state.openTask(state.row)
  assert.equal(destination.path, '/admin/academic-affairs/teaching-tasks')
  assert.equal(destination.query.termId, '52')
  destination = null
  state.openCorrectionDraft(state.row)
  assert.equal(destination.path, '/admin/academic-affairs/teaching-tasks')
  assert.equal(destination.query.termId, '52')
})

test('教学任务核对保留权威学期及大编号，切换或清空上下文不携带旧学期', () => {
  const component = page('AaSchedulingConsoleView')
  let destination
  const state = { ...component.methods, workbench: { termId: '1000000000000000052' }, termId: '51', $route: { query: { termId: '50', batchId: '47', classId: '4670', returnToken: 'old' } }, $router: { push: route => { destination = typeof route === 'string' ? { path: route, query: {} } : route } } }
  state.runWorkbenchAction('TEACHING_TASKS')
  assert.equal(destination.path, '/admin/academic-affairs/teaching-tasks')
  assert.equal(destination.query.termId, '1000000000000000052')
  assert.deepEqual(Object.keys(destination.query), ['termId'])

  state.workbench = null
  state.termId = '1000000000000000053'
  state.openTeachingTasks()
  assert.equal(destination.query.termId, '1000000000000000053')
  state.workbench = { termId: 54 }
  state.openTeachingTasks()
  assert.equal(destination.query.termId, '54')

  state.workbench = null
  state.termId = ''
  state.openTeachingTasks()
  assert.equal(destination.path, '/admin/academic-affairs/teaching-tasks')
  assert.deepEqual(Object.keys(destination.query), [])
})

test('新建课表须明确学院或全校范围，学院编号按字符串传递', async () => {
  const writes = []
  const component = page('AaScheduleBatchListView', { academicAffairsApi: { createScheduleBatch: async body => { writes.push(body); return { code: 0 } } }, toast: { success() {}, error() {} } })
  const state = Object.assign(component.data(), component.methods, { ctx: {}, load: async () => {} })
  state.draft.termId = '52'
  await state.createBatch()
  assert.equal(writes.length, 0)
  state.draft.collegeId = '1000000000000000128'
  await state.createBatch()
  assert.equal(writes[0].collegeId, '1000000000000000128')
  state.draft = { termId: '52', scopeType: 'SCHOOL', collegeId: '128' }
  await state.createBatch()
  assert.equal(writes[1].collegeId, undefined)
})

test('已发布课表的补排入口精确携带原批次', () => {
  const component = page('AaScheduleBatchListView')
  let destination
  component.methods.openWorkbench.call({ $router: { push: route => { destination = route } } }, { batchId: '41' })
  assert.equal(destination.path, '/admin/academic-affairs/scheduling')
  assert.equal(destination.query.batchId, '41')
})

test('历史和未知课表批次只进入查看，草稿和预发布才进入编排', () => {
  const component = page('AaScheduleBatchListView', teaching)
  let destination
  const state = Object.assign(component.data(), component.methods, { $router: { push: route => { destination = route } } })
  for (const status of ['SUPERSEDED', 'VOIDED', 'ARCHIVED', 'PUBLISHED', 'UNKNOWN']) {
    const row = { batchId: '9007199254740997', status }
    state.openBatch(row)
    assert.equal(destination.path, '/admin/academic-affairs/schedule/9007199254740997/views')
    state.openBatch(row, 'edit')
    assert.equal(destination.path, '/admin/academic-affairs/schedule/9007199254740997/views')
  }
  for (const status of ['DRAFT', 'PRE_PUBLISHED']) {
    const row = { batchId: '9007199254740997', status }
    state.openBatch(row)
    assert.equal(destination.path, '/admin/academic-affairs/schedule/9007199254740997/edit')
    state.openBatch(row, 'views')
    assert.equal(destination.path, '/admin/academic-affairs/schedule/9007199254740997/views')
  }
  assert.equal(state.statusLabel('SUPERSEDED'), '已被新版本替代')
})

test('真实课表批次动作模板不把历史和未知状态显示成继续排课', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaScheduleBatchListView.vue', import.meta.url), 'utf8')
  const template = source.match(/<div class="aa-actions">[\s\S]*?<\/div>/)[0]
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const component = page('AaScheduleBatchListView', teaching)
  for (const status of ['SUPERSEDED', 'VOIDED', 'ARCHIVED', 'PUBLISHED', 'UNKNOWN', 'DRAFT', 'PRE_PUBLISHED']) {
    const html = await renderToString(Vue.createSSRApp({ render, setup: () => ({ ...component.data(), ...component.methods, row: { batchId: '41', status } }) }))
    if (['DRAFT', 'PRE_PUBLISHED'].includes(status)) assert.match(html, /继续排课/)
    else { assert.doesNotMatch(html, /继续排课/); assert.match(html, /查看/) }
  }
})

test('publication record failure remains an error; retry clears it after success', async () => {
  let response = { code: 403, message: '无查看发布记录权限' }
  const component = page('AaSchedulePublishView', {
    academicAffairsApi: { getSchedulePublishRecords: async () => response },
    readAllPages: async (loadPage) => loadPage(1, 200),
    isDeniedResult: (result) => Number(result?.status || result?.code) === 403
  })
  const state = Object.assign(component.data(), component.methods, { focusGate: { invalidate() {} } })
  await state.loadRecords()
  assert.equal(state.recError, '无查看发布记录权限')
  assert.equal(state.recLoading, false)
  response = { code: 0, data: { list: [{ recordId: 'record-1' }] } }
  await state.loadRecords()
  assert.equal(state.recError, '')
  assert.equal(state.records[0].recordId, 'record-1')
})

test('today transport failure keeps the weekly schedule usable without claiming no classes', async () => {
  const component = page('AaTeacherScheduleView', {
    currentUserFromToken: () => ({ loginName: 'teacher-1' }),
    academicAffairsApi: {
      getTeacherSchedule: async () => ({ code: 0, data: { items: [{ itemId: 'lesson-1' }] } }),
      getMyTeacherToday: async () => { throw new Error('今日课表暂不可用') }
    }
  })
  const state = Object.assign(component.data.call({ $route: { params: {} } }), component.methods, {
    teacherKey: 'teacher-1', isSelfView: true, $router: { replace: async () => {} }
  })
  await state.load()
  assert.equal(state.error, '')
  assert.equal(state.items[0].itemId, 'lesson-1')
  assert.equal(state.todayError, '今日课表暂不可用')
  assert.equal(state.loading, false)
})

test('今日课表权限拒绝不得伪装今天无课，正式周课表继续可用', async () => {
  const component = page('AaTeacherScheduleView', {
    currentUserFromToken: () => ({ loginName: 'teacher-1' }),
    academicAffairsApi: {
      getTeacherSchedule: async () => ({ code: 0, data: { items: [{ itemId: 'lesson-1' }] } }),
      getMyTeacherToday: async () => ({ code: 403, message: '无今日课表访问权限' })
    }
  })
  const state = Object.assign(component.data.call({ $route: { params: {} } }), component.methods, {
    teacherKey: 'teacher-1', isSelfView: true, $router: { replace: async () => {} }
  })
  await state.load()
  assert.equal(state.todayError, '无今日课表访问权限')
  assert.equal(state.items[0].itemId, 'lesson-1')
})

test('switching query while a response is pending cannot display the previous object', async () => {
  let resolve
  const response = new Promise((done) => { resolve = done })
  const component = page('AaScheduleViewsView', {
    academicAffairsApi: { getScheduleClassView: () => response }
  })
  const state = Object.assign(component.data(), component.methods, { query: 'class-a', batchId: 'batch-1' })
  const pending = state.loadView()
  state.query = 'class-b'
  state.resetView()
  resolve({ code: 0, data: { items: [{ itemId: 'class-a-lesson' }] } })
  await pending
  assert.equal(state.loadedQuery, '')
  assert.equal(state.items.length, 0)
  assert.equal(state.loading, false)
})

test('student print preserves student query type and calls the student view endpoint', async () => {
  let destination = null
  const view = page('AaScheduleViewsView')
  view.methods.printView.call({
    loading: false, error: '', loadedQuery: 'student-1', query: 'student-1', batchId: 'batch-1', tab: 'student',
    $router: { push: (target) => { destination = target } }
  })
  assert.equal(destination.path, '/admin/academic-affairs/print/schedule/batch-1')
  assert.equal(destination.query.type, 'student')
  assert.equal(destination.query.key, 'student-1')
  let studentCalls = 0
  const print = page('AaPrintScheduleView', { academicAffairsApi: {
    getContext: async () => ({ code: 0, data: { tenantBrandConfig: { schoolName: '测试学校' } } }),
    getTimeSlots: async () => ({ code: 0, data: [] }),
    getScheduleStudentView: async (batch, key) => {
      assert.equal(batch, 'batch-1'); assert.equal(key, 'student-1'); studentCalls++
      return { code: 0, data: { items: [] } }
    },
    getScheduleClassView: () => { throw new Error('Student query must not call class view') }
  } })
  const state = Object.assign(print.data(), { type: 'student', keyText: 'student-1', $route: { params: { batchId: 'batch-1' } } })
  await print.methods.load.call(state)
  assert.equal(studentCalls, 1)
  assert.equal(state.error, '')
})

test('teacher change actions carry a concrete teaching week instead of a method object', () => {
  const component = page('AaTeacherScheduleView', {
    currentUserFromToken: () => ({ loginName: 'teacher-1' }),
    toast: { error() {}, success() {} }
  })
  let destination
  const scope = { $route: { params: {} } }
  const state = Object.assign(component.data.call(scope), component.methods, {
    teacherKey: 'teacher-1', selfKey: 'teacher-1',
    selectedItem: { itemId: '123', startWeek: 1, endWeek: 16 },
    $router: { push: value => { destination = value } }
  })
  Object.defineProperty(state, 'selectedOccurrenceWeek', {
    get: () => component.computed.selectedOccurrenceWeek.call(state)
  })
  state.week = null
  state.applyChange('STOP')
  assert.equal(destination, undefined)
  state.week = 8
  state.applyChange('ADJUST')
  assert.equal(destination.query.occurrenceWeek, '8')
})

test('teacher lesson guidance distinguishes no week, selected week, and management query', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaTeacherScheduleView.vue', import.meta.url), 'utf8')
  const guidance = source.match(/<p v-if="isSelfView && !selectedOccurrenceWeek"[\s\S]*?<p v-else class="mp-note">[\s\S]*?<\/p>/)?.[0]
  assert.ok(guidance, '课位详情应保留连续的三分支提示')
  const render = new Function('Vue', compile(guidance, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const component = page('AaTeacherScheduleView', { currentUserFromToken: () => ({ loginName: 'teacher-1' }) })
  async function guidanceFor(teacherKey, week) {
    const state = Object.assign(component.data.call({ $route: { params: {} } }), component.methods, {
      teacherKey, selfKey: 'teacher-1', week, selectedItem: { itemId: '33103' }
    })
    const isSelfView = component.computed.isSelfView.call(state)
    const selectedOccurrenceWeek = component.computed.selectedOccurrenceWeek.call(state)
    return renderToString(Vue.createSSRApp({ render, setup: () => ({ isSelfView, selectedOccurrenceWeek }) }))
  }
  const noWeek = await guidanceFor('teacher-1', null)
  assert.match(noWeek, /必须先在上方“周次”选择具体教学周/)
  assert.doesNotMatch(noWeek, /当前为管理查询视图/)
  const selectedWeek = await guidanceFor('teacher-1', 6)
  assert.match(selectedWeek, /已选择第6教学周/)
  assert.match(selectedWeek, /交学院审核，审批前不改动正式课表/)
  assert.doesNotMatch(selectedWeek, /当前为管理查询视图/)
  const management = await guidanceFor('other-teacher', 6)
  assert.match(management, /当前为管理查询视图/)
  assert.doesNotMatch(management, /已选择第6教学周/)
})

test('teacher week and semester views reload when switching back to self', () => {
  for (const name of ['AaWeekScheduleView', 'AaSemesterScheduleView']) {
    const component = page(name)
    let loads = 0
    const state = {
      visibleDims: [{ key: 'teacher' }], isAcademicTeacher: true,
      termId: '52', selfKey: 'teacher-1', teacherKey: '',
      items: [{ itemId: 'old' }], note: 'old', error: 'old',
      batchId: 'old-batch', batchIds: ['old-batch'],
      load: () => { loads += 1 }
    }
    component.methods.switchDim.call(state, 'teacher')
    assert.equal(state.teacherKey, 'teacher-1')
    assert.equal(loads, 1)
    assert.equal(state.items.length, 0)
  }
})
