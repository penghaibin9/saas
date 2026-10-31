import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import * as registry from '../src/modules/academicAffairs/config/academicFlowRegistry.js'

const permissionSource = readFileSync(new URL('../src/config/navPlan.js', import.meta.url), 'utf8')
const matchPermission = new Function(`${permissionSource.match(/export function matchPermission\(patterns, code\) \{[\s\S]*?\n\}/)[0].replace('export ', '')}; return matchPermission`)()

const ok = data => ({ code: 0, data })
const id = '9007199254740993'
const batch = extra => ({ batchId: id, status: 'ARRANGED', batchName: '期末考试', publishAction: { allowed: true }, ...extra })
const course = extra => ({ examCourseId: '9007199254740995', status: 'PENDING_CONFIRM', confirmAction: { allowed: true }, ...extra })
const readiness = extra => ({ batchId: id, canPublish: true, blockingReasons: [], ...extra })
function instance(api = {}, convenienceApi = {}) {
  const value = page('AaExamConsoleView', { ...registry, matchPermission,
    academicAffairsExamApi: { getBatch: async () => ok(batch()), listCourses: async () => ok({ list: [course()], total: 1 }), batchStats: async () => ok({}), ...api },
    academicAffairsExamConvenienceApi: { getReadiness: async () => ok(readiness()), ...convenienceApi }
  })
  value.state.ctx.permissionPatterns = ['academicAffairs.exam.manage', 'academicAffairs.exam.arrange', 'academicAffairs.exam.publish']
  value.state.ctx.dataScope = { scope: 'TENANT_ALL' }; value.state.current = batch()
  value.state.readiness = readiness(); value.state.courses = [course()]; value.state.load = async () => {}
  return value
}

test('考试发布仅严格许可及同单真实就绪可办，未知和非布尔值不能写', async () => {
  for (const action of [null, undefined, {}, { allowed: false }, { allowed: 'true' }, { allowed: 1 }]) {
    const { state } = instance(); state.current.publishAction = action
    assert.equal(state.canPublishExam, false); await state.lc('publishBatch', '发布'); assert.equal(state.confirmVisible, false)
  }
  for (const ready of [null, {}, readiness({ canPublish: false }), readiness({ canPublish: 'true' }), readiness({ batchId: 'other' })]) {
    const { state } = instance(); state.readiness = ready
    assert.equal(state.canPublishExam, false); await state.lc('publishBatch', '发布'); assert.equal(state.confirmVisible, false)
  }
})

test('课程行缺许可不能确认，学校看到学院办理原因', async () => {
  let writes = 0
  const { state } = instance({ confirmCourse: async () => { writes++ } })
  for (const action of [undefined, { allowed: 'true' }, { allowed: false, reason: '由开课责任学院确认，学校不能代办。' }]) {
    state.courses = [course({ confirmAction: action })]
    await state.confirm(state.courses[0], 'CONFIRM'); assert.equal(writes, 0)
  }
  assert.match(state.examActionError, /学校不能代办/)
})

test('课程确认前回读当前页同一行，撤权、换行、读取失败均不写', async () => {
  for (const kind of ['revoked', 'missing', 'error']) {
    let writes = 0
    const { state } = instance({ listCourses: async () => kind === 'error' ? { code: 403, message: '当前学院已无办理权限' } : ok({ list: kind === 'missing' ? [] : [course({ confirmAction: { allowed: false, reason: '当前任职已失效' } })] }), confirmCourse: async () => { writes++ } })
    state.ctx.dataScope.scope = 'COLLEGE'
    await state.confirm(state.courses[0], 'CONFIRM')
    assert.equal(writes, 0); assert.ok(state.examActionError); assert.equal(state.examActionBusy, false)
  }
})

test('学院正常确认使用正式字符串对象并写后回读，下一岗位仍是校教务处', async () => {
  let writes = 0, reads = 0
  const { state } = instance({
    listCourses: async () => { reads++; return ok({ list: [course(writes ? { status: 'CONFIRMED', confirmAction: { allowed: false } } : {})] }) },
    confirmCourse: async (courseId, action) => { assert.equal(courseId, '9007199254740995'); assert.equal(action, 'CONFIRM'); writes++; return ok({}) }
  })
  state.ctx.dataScope.scope = 'COLLEGE'
  await state.confirm(state.courses[0], 'CONFIRM')
  assert.equal(writes, 1); assert.equal(reads, 2); assert.equal(state.courses[0].status, 'CONFIRMED'); assert.equal(state.examActionBusy, false)
})

test('发布开框前回读资格与就绪，缺项或撤权不能开框', async () => {
  for (const outcome of ['revoked', 'not-ready', 'failed']) {
    const { state } = instance({ getBatch: async () => ok(batch(outcome === 'revoked' ? { publishAction: { allowed: false, reason: '校教务责任任职失效' } } : {})) }, {
      getReadiness: async () => outcome === 'failed' ? { code: 503 } : ok(readiness({ canPublish: outcome !== 'not-ready' }))
    })
    await state.lc('publishBatch', '发布')
    assert.equal(state.confirmVisible, false); assert.ok(state.examActionError); assert.equal(state.examActionBusy, false)
  }
})

test('发布开框后发送前再次回读，同账号撤权不提交', async () => {
  let reads = 0, writes = 0
  const { state } = instance({ getBatch: async () => ok(batch({ publishAction: ++reads === 1 ? { allowed: true } : { allowed: false, reason: '已撤销本批次发布责任' } })), publishBatch: async () => { writes++ } })
  await state.lc('publishBatch', '发布'); assert.equal(state.confirmVisible, true)
  await state.onConfirm(); assert.equal(reads, 2); assert.equal(writes, 0); assert.match(state.examActionError, /已撤销/); assert.equal(state.saving, false)
})

test('正常已编排批次保持原正式发布命令与写后回读', async () => {
  let reads = 0, writes = 0
  const { state } = instance({ getBatch: async () => { reads++; return ok(batch(writes ? { status: 'PUBLISHED', publishAction: { allowed: false } } : {})) }, publishBatch: async batchId => { assert.equal(batchId, id); writes++; return ok(batch({ status: 'PUBLISHED' })) } })
  await state.lc('publishBatch', '发布'); await state.onConfirm()
  assert.equal(writes, 1); assert.equal(reads, 3); assert.equal(state.current.status, 'PUBLISHED'); assert.equal(state.saving, false)
})

test('考试已结束或已归档只读回批次事实，不再请求发布就绪或提示再次发布', async () => {
  for (const status of ['FINISHED', 'ARCHIVED']) {
    let readinessReads = 0
    const { state } = instance({ getBatch: async () => ok(batch({ status, responsibility: null, nextStep: null, publishAction: null })) }, {
      getReadiness: async () => { readinessReads++; return ok(readiness({ canPublish: false, blockingReasons: ['考试批次尚未进入可发布阶段'] })) }
    })
    await state.refresh()
    assert.equal(state.current.status, status)
    assert.equal(state.readiness, null)
    assert.equal(state.readinessError, '')
    assert.equal(readinessReads, 0)
    assert.doesNotMatch(state.objectBar.blocker, /发布|就绪/)
    if (status === 'ARCHIVED') {
      assert.equal(state.objectBar.owner, '学校已完成考务归档')
      assert.equal(state.objectBar.blocker, '已归档，无当前办理阻断')
      assert.equal(state.objectBar.nextOwner, '已办结，后续按权限查阅')
    } else {
      assert.match(state.objectBar.owner, /责任尚未配置/)
      assert.equal(state.objectBar.blocker, '考试已结束，待完成归档')
    }
  }
})

test('非终态缺责任继续提示配置，已归档若有正式后续责任仍展示服务端事实', () => {
  const { state } = instance()
  state.current = batch({ status: 'ARRANGED', responsibility: null, nextStep: null })
  assert.match(state.objectBar.owner, /责任尚未配置/)
  state.current = batch({ status: 'ARCHIVED', responsibility: { orgName: '校教务处', resolved: true }, nextStep: { label: '核对查阅申请' } })
  assert.match(state.objectBar.owner, /校教务处/)
  assert.equal(state.objectBar.nextOwner, '核对查阅申请')
})

test('课程或发布回读中换身份、换批次、离页或卸载都不能接收许可和写入', async () => {
  for (const action of ['course', 'publish']) for (const change of ['identity', 'batch', 'route', 'unmount']) {
    const pending = deferred(); let writes = 0
    const { state, definition } = instance({ getBatch: () => pending.promise, confirmCourse: async () => { writes++ }, publishBatch: async () => { writes++ } })
    const running = action === 'course' ? state.confirm(state.courses[0], 'CONFIRM') : state.lc('publishBatch', '发布')
    if (change === 'identity') { state.ctx.currentRole = { roleCode: 'OTHER' }; state.resetModeAndLoad() }
    if (change === 'batch') { state.current = batch({ batchId: 'other' }); definition.watch['current.batchId'].call(state) }
    if (change === 'route') { state.$route.fullPath = '/other'; state.resetModeAndLoad() }
    if (change === 'unmount') definition.beforeUnmount.call(state)
    pending.resolve(ok(batch())); await running; await state.onConfirm()
    assert.equal(writes, 0); assert.equal(state.confirmVisible, false); assert.equal(state.examActionBusy, false)
  }
})

test('真实发布按钮接受已编排阶段但被无资格或未知就绪禁用，课程按钮不替学校代办', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaExamConsoleView.vue', import.meta.url), 'utf8')
  const publish = source.match(/<AppButton\s+v-if="\['COURSE_CONFIRMED', 'ARRANGED'\][\s\S]*?>发布<\/AppButton>/)[0]
  const confirm = source.match(/<button v-if="row.confirmAction[\s\S]*?<\/span>/)[0]
  for (const [snippet, shouldShow] of [[publish, true], [confirm, false]]) {
    const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
    const { state } = instance(); state.current.publishAction = { allowed: false, reason: '当前不具备学校发布责任' }; state.row = course({ confirmAction: { allowed: false, reason: '由开课责任学院确认' } })
    delete state.$route; delete state.$router
    const app = Vue.createSSRApp({ render, setup: () => state, components: { AppButton: { props: ['disabled'], setup: (props, { slots }) => () => Vue.h('button', { disabled: props.disabled }, slots.default?.()) } } })
    const html = await renderToString(app)
    if (shouldShow) assert.match(html, /<button disabled[^>]*>发布/)
    else { assert.doesNotMatch(html, /<button/); assert.match(html, /由开课责任学院确认/) }
  }
})


test('全校只读范围不授予考务写动作，名单与考场仍能读取', async () => {
  const writes = []
  const { state } = instance(Object.fromEntries(['createBatch', 'confirmBatchCourses', 'finishBatch', 'archiveBatch', 'setSchedule', 'addPatrol', 'addRoom'].map(name => [name, async () => { writes.push(name); return ok({}) }])), { previewCourses: async () => { writes.push('preview'); return ok({}) }, confirmCourses: async () => { writes.push('circle'); return ok({}) } })
  state.ctx.permissionPatterns = ['academicAffairs.exam.view']
  state.current = batch({ status: 'COURSE_CONFIRMED' }); state.form = { termId: '1', batchName: '考试' }
  state.selectedTaskIds = ['T']; state.coursePreview = { previewToken: 'preview' }
  state.openCreate(); await state.openAddCourse(); state.openAutoPlan(); state.openSchedule(course())
  await state.submitCreate(); await state.previewCourses(); await state.confirmCourses(); await state.runAutoArrange(); await state.submitSchedule(); await state.submitPatrol(); await state.submitRoom()
  for (const fn of ['confirmBatchCourses', 'finishBatch', 'archiveBatch', 'publishBatch']) await state.lc(fn, '办理')
  assert.equal(writes.length, 0); assert.equal(state.confirmVisible, false)
  assert.equal(state.canManageExam, false); assert.equal(state.canArrangeExam, false); assert.equal(state.canPublishPermission, false)
  assert.equal(state.createVisible, false); assert.equal(state.courseVisible, false); assert.equal(state.autoPlanVisible, false); assert.equal(state.schedVisible, false)
})

test('考务管理编排发布权限独立，学院编排不取得学校批次管理', () => {
  const { state } = instance()
  for (const [code, key] of [['manage', 'canManageExam'], ['arrange', 'canArrangeExam'], ['publish', 'canPublishPermission']]) {
    state.ctx.permissionPatterns = ['academicAffairs.exam.' + code]
    for (const candidate of ['canManageExam', 'canArrangeExam', 'canPublishPermission']) assert.equal(state[candidate], candidate === key)
  }
  state.ctx.dataScope = { scope: 'COLLEGE' }; state.ctx.permissionPatterns = ['academicAffairs.exam.arrange']
  assert.equal(state.canArrangeExam, true); assert.equal(state.canManageExam, false)
})

test('考务确认窗口打开后撤权不得发送批次管理请求', async () => {
  let writes = 0
  const { state } = instance({ finishBatch: async () => { writes++; return ok(batch()) } })
  state.current = batch({ status: 'PUBLISHED' }); await state.lc('finishBatch', '结束')
  assert.equal(state.confirmVisible, true)
  state.ctx.permissionPatterns = ['academicAffairs.exam.view']; await state.onConfirm()
  assert.equal(writes, 0)
})

test('自动时间安排返回后撤销编排权限不能继续第二次写请求', async () => {
  let writes = 0
  const pending = deferred()
  const { state } = instance({ autoArrange: async () => { writes++; return ok({}) } }, { autoTimes: () => pending.promise })
  state.autoPlan = { dates: ['2027-07-05'], sessions: [{ start: '09:00', end: '11:00' }], maxPerDayPerClass: 1 }
  const running = state.runAutoArrange(); state.ctx.permissionPatterns = ['academicAffairs.exam.view']
  pending.resolve(ok({})); await running
  assert.equal(writes, 0); assert.equal(state.autoArranging, false)
})


test('缓考只有正式节点许可才显示审核，辅导员使用首审接口并携带版本', async () => {
  const calls=[]
  const {state}=instance({deferCounselorReview:async(...args)=>{calls.push(args);return ok({deferId:'71',version:4,status:'TEACHER_CONFIRM'})},deferList:async()=>ok({list:[calls.length?{deferId:'71',version:4,status:'TEACHER_CONFIRM'}:{deferId:'71',version:3,status:'COUNSELOR_REVIEW',allowedActions:['APPROVE']}],total:1})})
  state.$route.query.tab='defer'
  const row={deferId:'71',status:'COUNSELOR_REVIEW',version:3,allowedActions:['APPROVE','RETURN','REJECT']}
  assert.equal(state.canReviewDefer({...row,allowedActions:[]}),false)
  assert.equal(state.canReviewDefer({...row,version:undefined}),false)
  state.openDeferDecision(row,'APPROVE');await state.submitDeferDecision()
  assert.equal(calls.length,1);assert.equal(calls[0][3],3)
})

test('缓考确认窗口没有当前节点许可，不提交学校代办请求', async () => {
  let writes=0
  const {state}=instance({deferReview:async()=>{writes++}})
  state.deferDecisionRow={deferId:'71',status:'COLLEGE_REVIEW',version:1,allowedActions:[]}
  state.deferDecisionAction='APPROVE';await state.submitDeferDecision()
  assert.equal(writes,0)
})


test('缓考审批回读错对象不报成功、不关闭确认窗口', async()=>{
 let writes=0
 const row={deferId:'71',version:1,status:'COLLEGE_REVIEW',allowedActions:['APPROVE']}
 const {state}=instance({deferReview:async()=>{writes++;return ok({...row,version:2,status:'ACADEMIC_FINAL'})},deferList:async()=>ok({list:[writes?{...row,deferId:'72'}:row],total:1})})
 state.$route.query.tab='defer';state.openDeferDecision(row,'APPROVE');await state.submitDeferDecision()
 assert.equal(writes,1);assert.equal(state.deferConfirmVisible,true);assert.equal(state.saving,false)
})

test('缓考原版本已变化时，前端回读阻止提交', async()=>{
 let writes=0
 const row={deferId:'71',version:1,status:'COLLEGE_REVIEW',allowedActions:['APPROVE']}
 const {state}=instance({deferReview:async()=>{writes++},deferList:async()=>ok({list:[{...row,version:2}],total:1})})
 state.$route.query.tab='defer';state.openDeferDecision(row,'APPROVE');await state.submitDeferDecision()
 assert.equal(writes,0);assert.equal(state.deferConfirmVisible,true)
})


test('考务切换身份清掉旧提交忙状态，迟到审批不锁住新岗位',async()=>{
 const pending=deferred()
 const row={deferId:'71',version:1,status:'COLLEGE_REVIEW',allowedActions:['APPROVE']}
 const {state}=instance({deferReview:()=>pending.promise,deferList:async()=>ok({list:[row],total:1})})
 state.$route.query.tab='defer';state.openDeferDecision(row,'APPROVE');const writing=state.submitDeferDecision()
 await new Promise(resolve=>setImmediate(resolve));assert.equal(state.saving,true)
 state.ctx={...state.ctx,currentRole:{roleCode:'OTHER'}};state.resetModeAndLoad()
 assert.equal(state.saving,false);assert.equal(state.deferDecisionRow,null)
 pending.resolve(ok({...row,version:2,status:'ACADEMIC_FINAL'}));await writing
 assert.equal(state.saving,false);assert.equal(state.deferConfirmVisible,false)
})
