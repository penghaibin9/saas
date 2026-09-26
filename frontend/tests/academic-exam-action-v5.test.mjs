import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import * as registry from '../src/modules/academicAffairs/config/academicFlowRegistry.js'

const ok = data => ({ code: 0, data })
const id = '9007199254740993'
const batch = extra => ({ batchId: id, status: 'ARRANGED', batchName: '期末考试', publishAction: { allowed: true }, ...extra })
const course = extra => ({ examCourseId: '9007199254740995', status: 'PENDING_CONFIRM', confirmAction: { allowed: true }, ...extra })
const readiness = extra => ({ batchId: id, canPublish: true, blockingReasons: [], ...extra })
function instance(api = {}, convenienceApi = {}) {
  const value = page('AaExamConsoleView', { ...registry,
    academicAffairsExamApi: { getBatch: async () => ok(batch()), listCourses: async () => ok({ list: [course()], total: 1 }), batchStats: async () => ok({}), ...api },
    academicAffairsExamConvenienceApi: { getReadiness: async () => ok(readiness()), ...convenienceApi }
  })
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
