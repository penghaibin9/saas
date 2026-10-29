import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { randomUUID } from 'node:crypto'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import * as teaching from '../src/modules/academicAffairs/constants/teaching.js'
import { safeLocalizedText } from '../src/utils/presentationSafety.js'
import { ROLE_LABELS } from '../src/modules/workflow/constants/workflow.constants.js'
import { formatDateTime } from '../src/utils/dateUtils.js'

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

test('排课任务教室要求使用资源字典中文名称，未知类型不外露内部码', () => {
  const { methods } = page('AaSchedulingConsoleView')
  assert.equal(methods.roomRequirementText('MULTIMEDIA'), '教室要求：多媒体教室')
  assert.equal(methods.roomRequirementText('COMPUTER'), '教室要求：机房')
  assert.equal(methods.roomRequirementText('FUTURE_ROOM'), '教室要求：类型待核对')
  assert.equal(methods.roomRequirementText(null), '教室类型不限')
})

test('排课检查失败不把网络错误说明为已发现冲突', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaScheduleMaintainView.vue', import.meta.url), 'utf8')
  const snippet = source.match(/<div class="aa-preflight__head">[\s\S]*?<\/div>/)[0]
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const html = await renderToString(Vue.createSSRApp({ render, data: () => ({ preflight: { loading: false, result: { allowed: false, blockers: ['网络连接中断'] } } }) }))
  assert.match(html, /暂不能排入，请查看原因/)
  assert.doesNotMatch(html, /存在硬冲突|可以排入/)
})

test('原课程定位仍严格核对关联，错误说明不暴露内部编号', () => {
  const { methods } = page('AaScheduleMaintainView')
  const item = { itemId: 'internal-item-123', batchId: 'internal-batch-456', classId: 'internal-class-789', taskId: 'wrong-task' }
  const state = { focusItemId: item.itemId, batchId: item.batchId, classId: item.classId, focusTaskId: 'correct-task', focusTermId: '', items: [item] }
  methods.locateFocusedItem.call(state)
  assert.equal(state.focusedItem, null)
  assert.match(state.focusItemError, /信息不一致/)
  assert.doesNotMatch(state.focusItemError, /internal-|wrong-task|correct-task/)
  item.taskId = 'correct-task'
  methods.locateFocusedItem.call(state)
  assert.equal(state.focusedItem, item)
  assert.equal(state.focusItemError, '')
  state.items = [item, item]
  methods.locateFocusedItem.call(state)
  assert.equal(state.focusedItem, null)
  assert.match(state.focusItemError, /重复的定位信息/)
})

test('原课程编号仅在默认关闭的实施信息内，教师和上课时段仍可见', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaScheduleMaintainView.vue', import.meta.url), 'utf8')
  const snippet = source.match(/<section v-else-if="focusedItem"[\s\S]*?<\/section>/)[0].replace('v-else-if', 'v-if')
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const { methods } = page('AaScheduleMaintainView')
  const html = await renderToString(Vue.createSSRApp({ render, data: () => ({ className: '软件班', focusedItem: { courseName: '数学', teacherName: '李老师', weekday: 2, slotNo: 3, startWeek: 1, endWeek: 16, classroom: '教学楼101', itemId: 'internal-item', batchId: 'internal-batch', classId: 'internal-class', taskId: 'internal-task' } }), methods: { weekdayLabel: methods.weekdayLabel },
    components: { AppStatusTag: { render() { return Vue.h('span', this.$slots.default()) } } }
  }))
  assert.match(html, /软件班[\s\S]*李老师[\s\S]*周二/)
  assert.match(html, /<details><summary>实施人员使用/)
  assert.doesNotMatch(html, /<details[^>]*\bopen\b/)
  assert.doesNotMatch(html.replace(/<details>[\s\S]*?<\/details>/, ''), /internal-/)
  assert.match(html, /internal-item[\s\S]*internal-task/)
})

test('发布记录未知操作不误标为作废，原已知操作分别显示', () => {
  const { methods } = page('AaSchedulePublishView')
  assert.equal(methods.recordActionLabel('PUBLISH'), '发布')
  assert.equal(methods.recordActionLabel('VOID_REISSUE'), '作废重发')
  for (const value of ['NEW_OPERATION', 'constructor', '']) assert.equal(methods.recordActionLabel(value), '其他操作')
})

test('读取到目标状态但未确认本次请求时，发布与作废仍为待确认且不清除待办', async () => {
  const component = page('AaSchedulePublishView', { ...teaching, isDeniedResult: () => false })
  for (const [kind, expectedStatus, title] of [['pub', 'PUBLISHED', '发布结果待确认'], ['pre', 'PRE_PUBLISHED', '预发布结果待确认'], ['void', 'ARCHIVED', '作废结果待确认']]) {
    const pending = { identity: 'same', kind, batchId: '987654321012345678', expectedStatus, acknowledged: false }
    const data = { batchId: pending.batchId, batchName: '测试课表', status: expectedStatus, activeTruth: { truthStatus: 'VERIFIED', isCurrent: true, activeBatchId: pending.batchId } }
    const state = { ...component.methods, identityKey: 'same', pendingWrite: pending,
      focusContextKey: () => 'same-context', readFormalBatch: async () => ({ code: 0, data }), disposed: false }
    await state.reconcilePendingExact()
    assert.equal(state.pendingWrite, pending)
    assert.equal(state.receipt.pending, true)
    assert.equal(state.receipt.title, title)
    assert.equal(state.receipt.object, '测试课表')
    assert.match(state.receipt.next, /确认前不要重复提交/)
    assert.doesNotMatch(JSON.stringify(state.receipt), /987654321012345678|正式头|回读/)
  }
})

test('维护和发布页的版本摘要不泄露编号，矛盾数据不能显示尚未发布', () => {
  for (const name of ['AaScheduleMaintainView', 'AaSchedulePublishView']) {
    const component = page(name, { formatDateTime })
    const read = (key, batch) => component.computed?.[key]
      ? component.computed[key].call({ scheduleBatch: batch }) : component.methods[key](batch)
    const batch = { batchId: '991', activeTruth: { truthStatus: 'VERIFIED', activeBatchId: '992', scopeType: 'COLLEGE', scopeId: '987654321012345678', headVersion: 2 } }
    assert.equal(read('formalScopeText', batch), '指定学院')
    assert.equal(read('activeBatchText', batch), '其他已发布批次')
    assert.equal(read('headVersionText', batch), '第2版')
    assert.equal(read('headPublishedAtText', batch), '时间待核对')
    assert.equal(read('activeBatchText', { activeTruth: { truthStatus: 'NOT_PUBLISHED', activeBatchId: '992' } }), '待核对')
    assert.equal(read('activeBatchText', { activeTruth: { truthStatus: 'NOT_PUBLISHED' } }), '尚未发布')
  }
})

test('调整记录汉化角色和操作，未知代码不冒充已知状态', () => {
  const component = page('AaScheduleAdjustmentLogView', { safeLocalizedText, ROLE_LABELS })
  const methods = component.methods
  assert.equal(methods.actionLabel('OPEN_CORRECTION_DRAFT'), '发起课表纠错')
  assert.equal(methods.actionLabel('NEW_INTERNAL_ACTION'), '其他操作')
  assert.equal(methods.typeLabel('NEW_INTERNAL_TYPE'), '其他事项')
  assert.equal(methods.roleLabel('COLLEGE_ADMIN'), '二级学院管理员')
  assert.equal(methods.roleLabel('NEW_INTERNAL_ROLE'), '其他业务角色')
  assert.equal(methods.roleLabel('本校排课负责人'), '本校排课负责人')
})

test('调整记录将技术参数折叠，但完整保留纠错原因和自由填写文字', () => {
  const { methods } = page('AaScheduleAdjustmentLogView')
  const correction = { action: 'OPEN_CORRECTION_DRAFT', detail: 'draftBatchId=123;reason=补排课程；保留原意见;code=用户填写内容' }
  assert.equal(methods.businessDetail.call(methods, correction), '补排课程；保留原意见;code=用户填写内容')
  assert.equal(methods.technicalDetail(correction), true)
  const placement = { action: 'ADD_ITEM', detail: 'taskId=987;周4第2节;prePublishReset=False' }
  assert.equal(methods.businessDetail.call(methods, placement), '周4第2节')
  assert.equal(methods.businessDetail.call(methods, { action: 'TEACHER_OBJECT', detail: 'reason=本人填写意见' }), 'reason=本人填写意见')
  assert.equal(correction.detail, 'draftBatchId=123;reason=补排课程；保留原意见;code=用户填写内容')
})

test('调整记录加载失败和加载中不显示零条或旧计数', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaScheduleAdjustmentLogView.vue', import.meta.url), 'utf8')
  const snippet = source.match(/<div class="aa-adjust-metrics"[\s\S]*?<\/div>/)[0]
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const [loading, error] of [[true, ''], [false, '读取失败'], [false, '']]) {
    const html = await renderToString(Vue.createSSRApp({ render, data: () => ({ loading, error, total: 25 }), methods: { pageTypeCount: () => 10 } }))
    if (loading || error) { assert.doesNotMatch(html, /<strong>25|<strong>10/); assert.equal((html.match(/<strong>—/g) || []).length, 3) }
    else assert.match(html, /<strong>25/)
  }
})

test('导出名称显示不改查询标识，网络中断不推断文件未生成', async () => {
  const component = page('AaScheduleExportView', { academicAffairsApi: { exportScheduleXlsx: async () => { throw new Error() } } })
  const state = Object.assign(component.data(), component.methods, { identifier: '987654321012345678', purpose: '教务存档使用', canExport: true })
  state.onSelectionChange(state.identifier, [{ label: '软件技术班' }])
  assert.equal(state.identifier, '987654321012345678')
  assert.equal(state.selectedName, '软件技术班')
  await state.doExport()
  assert.equal(state.receipt.title, '未能获取课表文件')
  assert.match(state.receipt.description, /未收到文件/)
  assert.doesNotMatch(state.receipt.description, /未生成文件|导出成功/)
  assert.equal(state.exporting, false)
  assert.equal(component.computed.canExport.call({ identifier: state.identifier, purpose: '短', weekStart: 1, weekEnd: 2 }), false)
  assert.equal(component.computed.canExport.call({ identifier: state.identifier, purpose: state.purpose, weekStart: 3, weekEnd: 2 }), false)
})

test('学期课表选择教师时显示姓名并保留原查询，缺少姓名不泄露账号', () => {
  const component = page('AaSemesterScheduleView')
  let loads = 0
  const state = { dim: 'teacher', teacherKey: 'internal-teacher-key', selfKey: 'self-key', teacherName: '', load: () => { loads += 1 } }
  component.methods.onTeacherChange.call(state, state.teacherKey, [{ label: '显示标签', raw: { realName: '李老师' } }])
  assert.equal(component.computed.scheduleObjectName.call(state), '李老师')
  assert.equal(state.teacherKey, 'internal-teacher-key')
  assert.equal(loads, 1)
  component.methods.onTeacherChange.call(state, '', [])
  assert.equal(component.computed.scheduleObjectName.call(state), '课表查询范围')
  assert.equal(loads, 2)
  state.teacherKey = 'self-key'
  assert.equal(component.computed.scheduleObjectName.call(state), '本人')
})

test('今日无课提供有效查看指引，避免触发公共空态的创建数据提示', () => {
  const component = page('AaTeacherScheduleView')
  const state = { todayItems: [], calendarSource: '' }
  assert.equal(component.computed.todayNote.call(state), '可在下方查看其他周次的课程安排。')
  for (const calendarSource of ['HOLIDAY', 'SWAP_SOURCE', 'OUT_OF_TERM']) {
    const message = component.computed.todayNote.call({ ...state, calendarSource })
    assert.ok(message)
    assert.doesNotMatch(message, /投影|创建新数据|已核对/)
  }
})

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
  assert.equal(checks.find(row => row.label === '总学时符合计划').ok, true)
  assert.equal(checks.find(row => row.label === '每周学时未超量').ok, false)
  state.gate.summary = { complete: true }
  checks = component.computed.gateChecklist.call(state)
  assert.equal(checks.find(row => row.label === '总学时符合计划').ok, false)
  assert.match(checks.find(row => row.label === '总学时符合计划').detail, /待核对/)
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
  assert.match(html, /查看来源差异/)
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

test('单份形成方式核对只接受当前工作台来源，不依赖重复任务组',()=>{
  const component=page('AaSchedulingConsoleView')
  const state={...component.methods,formationProofSourceId:'old',sourceReview:{},workbench:{taskQueue:[{taskId:'14945',sourceProgramCourseId:'31195'}]}}
  state.openFormationProof({taskId:'14945',sourceProgramCourseId:'31195'});assert.equal(state.formationProofSourceId,'31195');assert.equal(state.sourceReview,null)
  state.openFormationProof({taskId:'14945',sourceProgramCourseId:'31196'});assert.equal(state.formationProofSourceId,'')
  state.workbench=null;state.openFormationProof({taskId:'14945',sourceProgramCourseId:'31195'});assert.equal(state.formationProofSourceId,'')
})

test('来源差异入口只使用当前重复组，超过两条交由核对工作区明确选择', () => {
  const component = page('AaSchedulingConsoleView')
  const state = { ...component.methods, sourceReview: null, workbench: { duplicateTaskGroups: [{ taskIds: ['1000000000000000001', '1000000000000000002', '3'] }], taskQueue: [{ taskId: '1000000000000000002', courseName: '计算机基础', teacherName: '教师乙' }] } }
  state.openSourceReview({ taskId: '1000000000000000001' })
  assert.equal(state.sourceReview.taskId, '1000000000000000001')
  assert.equal(state.sourceReview.otherTasks.length, 2)
  assert.equal(state.sourceReview.otherTasks[0].taskId, '1000000000000000002')
  state.workbench = null
  state.openSourceReview({ taskId: '1000000000000000001' })
  assert.equal(state.sourceReview, null)
  assert.match(state.sourceReviewError, /重新读取/)
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
  assert.match(noWeek, /停课或补课须先选周次/)
  assert.doesNotMatch(noWeek, /仅任课教师本人可申请/)
  const selectedWeek = await guidanceFor('teacher-1', 6)
  assert.match(selectedWeek, /第6教学周的申请/)
  assert.match(selectedWeek, /先交学院审核，教务处终审通过后更新课表/)
  assert.doesNotMatch(selectedWeek, /仅任课教师本人可申请/)
  const management = await guidanceFor('other-teacher', 6)
  assert.match(management, /仅任课教师本人可申请/)
  assert.doesNotMatch(management, /第6教学周的申请/)
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


test('真实父子承接回读后刷新队列，同时保持成功说明和时间可见，切上下文清回执', async () => {
  const oldId = '1000000000000000001', newId = '1000000000000000002'
  const receipt = { handoffId: '1000000000000000088', termId: '52', executionTaskId: oldId, successorTaskId: newId,
    reason: '已核对正式课程来源', confirmedAt: '2026-10-05T12:00:00', summary: '原任务继续执行，后继来源已承接' }
  let finishRefresh, refreshPromise, notifyParent, refreshes = 0, reads = 0
  const parent = page('AaSchedulingConsoleView', { academicAffairsApi: { getScheduleSummary: () => { refreshes++; return new Promise(resolve => { finishRefresh = resolve }) } } })
  const state = { ...parent.methods, sourceReview: { taskId: oldId, otherTasks: [{ taskId: newId }] },
    sourceReviewContext: 'school-a:52:47', sourceHandoffReceipt: null, termId: '52', workbenchBatchId: '47', workbench: { termId: '52' },
    routeContextKey: () => 'school-a:52:47', $route: { query: { batchId: '47' } },
    workbenchGate: { begin: () => () => true }, academicFlow: null }
  Object.defineProperty(state, 'visibleHandoffReceipt', { get: () => parent.computed.visibleHandoffReceipt.call(state) })
  state.onSourceHandoffConfirmed = value => { refreshPromise = parent.methods.onSourceHandoffConfirmed.call(state, value); return refreshPromise }
  const parentText = readFileSync(new URL('../src/modules/academicAffairs/views/AaSchedulingConsoleView.vue', import.meta.url), 'utf8')
  const childBinding = parentText.match(/<AaTaskSourceReview\b[^>]*\/>/)[0]
  const bindingRender = new Function('Vue', compile(childBinding, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const boundReview = { props: ['taskId', 'termId', 'otherTasks', 'contextKey'], emits: ['close', 'confirmed'],
    setup(_props, { emit }) { notifyParent = value => emit('confirmed', value); return () => Vue.h('span', '当前核对工作区') } }
  await renderToString(Vue.createSSRApp({ render: bindingRender, components: { AaTaskSourceReview: boundReview }, setup: () => state }))
  const childText = readFileSync(new URL('../src/modules/academicAffairs/components/teaching-tasks/AaTaskSourceReview.vue', import.meta.url), 'utf8')
  const checked = { termId: '52', taskIds: [oldId, newId], tasks: [], checks: [], reviewOnly: true, status: 'CHECKED',
    handoffAction: { allowed: true, executionTaskId: oldId, successorTaskId: newId, expectedSourceFingerprint: 'a'.repeat(64) }, confirmedHandoff: null }
  const context = { AaFormationProof: {}, AppConfirmDialog: {}, crypto: { randomUUID },
    teachingTaskWorkbenchApi: { getSourceReview: async () => ({ code: 0, data: reads++ ? { ...checked, confirmedHandoff: receipt } : checked }), confirmSourceHandoff: async () => ({ code: 0, data: receipt }) } }
  vm.runInNewContext(childText.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component ='), context)
  const child = context.component, props = { taskId: oldId, termId: '52', otherTasks: [{ taskId: newId }], contextKey: 'school-a:52:47' }
  const c = { ...props, ...child.data.call(props), ...child.methods, $emit(name, value) { if (name === 'confirmed') notifyParent(value) } }
  for (const [key, fn] of Object.entries(child.computed)) Object.defineProperty(c, key, { get: () => fn.call(c) })
  await c.load(); c.reason = receipt.reason; c.openConfirmation(); await c.confirmHandoff()
  assert.equal(reads, 2); assert.equal(refreshes, 1); assert.equal(state.sourceReview, null); assert.equal(state.workbenchLoading, true)
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaSchedulingConsoleView.vue', import.meta.url), 'utf8')
  const template = source.match(/<section v-if="visibleHandoffReceipt"[\s\S]*?<\/section>/)[0]
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  async function visible() { return renderToString(Vue.createSSRApp({ render, setup: () => ({ visibleHandoffReceipt: state.visibleHandoffReceipt }) })) }
  let html = await visible()
  assert.match(html, /正式承接已确认/); assert.ok(html.includes(receipt.reason)); assert.ok(html.includes(receipt.confirmedAt))
  finishRefresh({ code: 0, data: { batchId: '47', termId: '52' } }); await refreshPromise
  assert.equal(state.workbench.batchId, '47'); html = await visible(); assert.ok(html.includes(receipt.confirmedAt))
  state.routeContextKey = () => 'school-b:53:48'
  assert.equal(state.visibleHandoffReceipt, null)
  await state.syncRoute(); assert.equal(state.sourceHandoffReceipt, null)
})


test('预发布课表沿已有写入规则允许补排，正式历史及结果待确认仍只读',()=>{
  const c=page('AaScheduleMaintainView')
  const state={scheduleBatch:null,taskLoadError:'',$route:{query:{classId:'4671'}},classId:'4671',focusItemId:'',focusedItem:null,pendingWrite:null,moving:false}
  for(const status of ['DRAFT','PRE_PUBLISHED','PUBLISHED','ARCHIVED','SUPERSEDED','UNKNOWN']){
    state.scheduleBatch={status};assert.equal(c.computed.canEditBatch.call(state),['DRAFT','PRE_PUBLISHED'].includes(status))
  }
  state.scheduleBatch={status:'PRE_PUBLISHED'};state.pendingWrite={};assert.equal(c.computed.canEditBatch.call(state),false)
  state.pendingWrite=null;state.taskLoadError='来源读取失败';assert.equal(c.computed.canEditBatch.call(state),false)
})


test('排课返回标识失效时仍回到当前批次，无返回服务时保持同一对象',async()=>{
  const {methods}=page('AaScheduleMaintainView'), destinations=[]
  const state={batchId:'47',$route:{query:{returnToken:'expired'}},$router:{push:value=>{destinations.push(value);return Promise.resolve()}}}
  state.academicFlow={back:async(token,fallback)=>{assert.equal(token,'expired');await state.$router.push(fallback)}}
  await methods.returnToQueue.call(state)
  assert.deepEqual(destinations,['/admin/academic-affairs/scheduling?batchId=47'])
  state.academicFlow=null
  await methods.returnToQueue.call(state)
  assert.equal(destinations[1],destinations[0])
  state.batchId='';await methods.returnToQueue.call(state)
  assert.equal(destinations[2],'/admin/academic-affairs/scheduling')
})


test('被替代和归档课表显示只读状态，当前正式课表仍按原流程办理', () => {
  const c=page('AaSchedulingConsoleView')
  const state={workbenchBatchId:'41',workbench:{batchId:'41',batchStatus:'SUPERSEDED',workflow:{steps:[{state:'current',label:'正式发布'}]}},batchStatusLabel:c.methods.batchStatusLabel}
  Object.defineProperty(state,'historicalWorkbench',{get:()=>c.computed.historicalWorkbench.call(state)})
  assert.equal(c.computed.currentStageLabel.call(state),'已被新版本替代')
  state.workbench.batchStatus='ARCHIVED';assert.equal(c.computed.currentStageLabel.call(state),'已归档')
  state.workbench.batchStatus='PUBLISHED';assert.equal(state.historicalWorkbench,false);assert.equal(c.computed.currentStageLabel.call(state),'正式发布')
  state.workbench.batchStatus='SUPERSEDED';state.workbenchBatchId='44';assert.equal(state.historicalWorkbench,false)
})


test('工作台历史课表入口复用带返回标识的正式视图入口', () => {
  const c=page('AaSchedulingConsoleView'), routes=[]
  const state={workbenchBatchId:'41',academicFlow:{captureReturn:()=> 'historical-workbench'},$router:{push:route=>routes.push(route)}}
  state.returnQuery=c.methods.returnQuery.bind(state)
  state.openPublishedSchedule=c.methods.openPublishedSchedule.bind(state)
  c.methods.runWorkbenchAction.call(state,'VIEW_HISTORY')
  assert.equal(routes[0].path,'/admin/academic-affairs/schedule/41/views')
  assert.equal(routes[0].query.returnToken,'historical-workbench')
})
