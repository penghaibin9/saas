import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'
import { academicFlowText } from '../src/modules/academicAffairs/config/academicFlowRegistry.js'
import * as results from '../src/modules/academicAffairs/components/parallel-a/resultState.js'

const hours = { expectedContactHours: 36, scheduledContactHours: 36, missingContactHours: 0, excessContactHours: 0, weeklyOverloadCount: 0, scheduledItemCount: 2 }
const withHours = data => data && Object.hasOwn(data, 'complete') ? { ...hours, ...data } : data
const ok = data => ({ code: 0, data: withHours(data) })
const row = { batchId: '9007199254740993', batchName: '本学期正式课表', status: 'PRE_PUBLISHED' }
const ready = () => ({ complete: true, schoolGate: { ready: true, blockers: [], requiredBatchIds: [row.batchId] } })
function instance(api = {}, summary = ready(), intent = 'pub') {
  const value = page('AaSchedulePublishView', { academicFlowText, ...results, academicAffairsApi: api }, {
    ctx: { currentRole: { roleCode: 'ACADEMIC_ADMIN' }, dataScope: { scope: 'TENANT_ALL' } },
    focusGate: { invalidate() {} }
  })
  value.state.gate = { visible: true, loading: false, submitting: false, batch: row, summary: withHours(summary), intent }
  value.state.load = async () => {}; value.state.loadRecords = async () => {}
  value.state.statusLabel = status => ({ PUBLISHED: '已发布', PRE_PUBLISHED: '预发布' })[status] || '待核对'
  return value
}

test('新学时核验缺失或周超量时即使旧门禁通过仍不可发布', async () => {
  for (const summary of [ready(), { ...ready(), ...hours, weeklyOverloadCount: 1 }, { ...ready(), ...hours, missingContactHours: 4, excessContactHours: 4 }]) {
    const { state } = instance()
    state.gate.summary = summary
    assert.equal(state.gateActionReady, false)
    let writes = 0; state.act = async () => { writes++ }
    await state.confirmGateAction()
    assert.equal(writes, 0)
    assert.match(state.commandError, /学时|超量/)
  }
  let writes = 0
  const { state } = instance({ getScheduleSummary: async () => ({ code: 0, data: ready() }), getScheduleBatch: async () => ok(row), publishSchedule: async () => { writes++ } })
  await state.confirmGateAction()
  assert.equal(writes, 0)
  assert.match(state.commandError, /尚未取得计划总学时/)
})

test('重复开课组即使收到矛盾完整状态也不开放发布，重新回读同样阻断', async () => {
  const conflict = { ...ready(), ...hours, duplicateTaskGroupCount: 1, duplicateTaskGroups: [{ courseId: '5324', classId: '4670', taskIds: ['14944', '14945'] }] }
  let writes = 0
  const { state } = instance({ getScheduleSummary: async () => ok(conflict), getScheduleBatch: async () => ok(row), publishSchedule: async () => { writes++ } }, conflict)
  assert.equal(state.gateActionReady, false)
  const item = state.gateChecklist.find(check => check.label === '开课来源无重复')
  assert.equal(item.ok, false)
  assert.match(item.detail, /重复 1 组/)
  await state.confirmGateAction()
  assert.equal(writes, 0)
  assert.match(state.commandError, /重复开课/)
  state.gate.summary = { ...ready(), ...hours, duplicateTaskGroupCount: 0 }
  await state.confirmGateAction()
  assert.equal(writes, 0)
  assert.match(state.commandError, /重复开课/)
})

test('正式发布同时要求批次完整和全校明确就绪，缺失或非布尔值均不能写', async () => {
  for (const summary of [null, {}, { complete: true }, { complete: true, schoolGate: null },
    { complete: true, schoolGate: { ready: false } }, { complete: true, schoolGate: { ready: 'true' } },
    { complete: 'true', schoolGate: { ready: true } }, { complete: false, schoolGate: { ready: true } }]) {
    const { state } = instance({}, summary)
    let calls = 0; state.act = async () => { calls++ }
    assert.equal(state.gateActionReady, false)
    await state.confirmGateAction()
    assert.equal(calls, 0)
  }
})

test('预发布仍只受原批次条件控制，全校未就绪不阻断公共课预发布', async () => {
  for (const schoolGate of [undefined, { ready: false, blockers: [{ code: 'COLLEGE_NOT_READY', message: '其它学院尚未完成排课' }] }]) {
    let written = false
    const summary = { complete: true, schoolGate }
    const { state } = instance({
      getScheduleSummary: async id => { assert.equal(id, row.batchId); return ok(summary) },
      getScheduleBatch: async () => ok({ ...row, status: written ? 'PRE_PUBLISHED' : 'DRAFT' }),
      prePublishSchedule: async id => { assert.equal(id, row.batchId); written = true; return ok({ ...row, status: 'PRE_PUBLISHED' }) },
      publishSchedule: async () => { throw new Error('预发布不得调用正式发布') }
    }, summary, 'pre')
    assert.equal(state.gateActionReady, true)
    await state.confirmGateAction()
    assert.equal(written, true); assert.equal(state.pendingWrite, null); assert.equal(state.gate.submitting, false)
    assert.match(state.receipt.title, /预发布并核对/)
  }
})

test('全校核验通过后正式发布沿原命令并回读同一正式头', async () => {
  let writes = 0
  const formal = () => ({ ...row, status: writes ? 'PUBLISHED' : 'PRE_PUBLISHED', activeTruth: { truthStatus: 'VERIFIED', isCurrent: true, activeBatchId: row.batchId, publishedAt: '2026-09-27 12:00:00' } })
  const { state } = instance({
    getScheduleSummary: async id => { assert.equal(id, row.batchId); return ok(ready()) },
    getScheduleBatch: async id => { assert.equal(id, row.batchId); return ok(formal()) },
    publishSchedule: async id => { assert.equal(id, row.batchId); writes++; return ok(formal()) }
  })
  await state.confirmGateAction()
  assert.equal(writes, 1); assert.equal(state.pendingWrite, null); assert.equal(state.gate.submitting, false)
  assert.match(state.receipt.title, /正式发布并核对/)
})

test('确认前全校条件已变化或缺失，重读阻断并显示服务端中文原因', async () => {
  for (const schoolGate of [undefined, { ready: false, blockers: [{ code: 'COLLEGE_NOT_READY', message: '机械学院必需批次尚未完成排课' }] }]) {
    let writes = 0
    const { state } = instance({
      getScheduleSummary: async () => ok({ complete: true, schoolGate }),
      getScheduleBatch: async () => ok(row), publishSchedule: async () => { writes++ }
    })
    await state.confirmGateAction()
    assert.equal(writes, 0); assert.equal(state.gateActionReady, false); assert.equal(state.gate.submitting, false)
    assert.match(state.commandError, schoolGate ? /机械学院必需批次尚未完成排课/ : /尚未取得全校发布核验结果/)
    assert.equal(state.pendingWrite, null)
  }
})

test('确认时核验网络失败不能沿用先前就绪，保留可见错误', async () => {
  let writes = 0
  const { state } = instance({
    getScheduleSummary: async () => { throw new Error('全校核验读取失败') },
    getScheduleBatch: async () => ok(row), publishSchedule: async () => { writes++ }
  })
  await state.confirmGateAction()
  assert.equal(writes, 0); assert.equal(state.gate.summary, null); assert.match(state.commandError, /全校核验读取失败/)
  assert.equal(state.gate.submitting, false)
})

test('另一个批次或身份的迟到全校就绪结果不能覆盖当前检查', async () => {
  for (const change of ['identity', 'batch', 'unmount']) {
    const pending = deferred()
    const { state, definition } = instance({ getScheduleSummary: () => pending.promise })
    const opening = state.openGate(row, 'pub')
    assert.equal(state.gate.summary, null)
    if (change === 'identity') state.ctx = { ...state.ctx, ctxKey: 'new-school' }
    if (change === 'batch') state.gate.batch = { batchId: 'new-batch' }
    if (change === 'unmount') definition.beforeUnmount.call(state)
    pending.resolve(ok(ready())); await opening
    assert.equal(state.gate.summary, null); assert.equal(state.gateActionReady, false)
  }
})

test('全校核验权限拒绝清除先前条件和批次私有事实', async () => {
  let writes = 0
  const { state } = instance({ getScheduleSummary: async () => ({ code: 403001, message: '当前身份无学校发布权限' }), publishSchedule: async () => { writes++ } })
  state.rows = [row]
  await state.confirmGateAction()
  assert.equal(writes, 0); assert.equal(state.rows.length, 0); assert.equal(state.gate.summary, null)
  assert.match(state.error, /无学校发布权限/)
})

test('正式发布模板展示中文阻断和重新检查；预发布不要求学校门禁', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaSchedulePublishView.vue', import.meta.url), 'utf8')
  const template = source.match(/<AppSectionCard compact v-if="gate.visible"[\s\S]*?<\/AppSectionCard>/)[0]
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const intent of ['pub', 'pre']) {
    const { state } = instance({}, { complete: true, schoolGate: { ready: false, blockers: [{ code: 'SCHOOL_GATE_NOT_READY', message: '电气学院尚有HARD冲突1项' }] } }, intent)
    delete state.$route; delete state.$router
    const buttons = []
    const app = Vue.createSSRApp({ render, setup: () => state, components: {
      AppSectionCard: { setup: (_, { slots }) => () => Vue.h('section', slots.default?.()) },
      AppStatusTag: { setup: (_, { slots }) => () => Vue.h('span', slots.default?.()) },
      AppButton: { props: ['disabled'], setup: (props, { slots, attrs }) => () => { const children = slots.default?.(); buttons.push({ disabled: props.disabled, click: attrs.onClick, children }); return Vue.h('button', { disabled: props.disabled }, children) } },
      LoadingState: { render: () => null }
    } })
    const html = await renderToString(app)
    if (intent === 'pub') {
      assert.match(html, /电气学院尚有严重冲突1项/); assert.doesNotMatch(html, /HARD|SCHOOL_GATE_NOT_READY/)
      assert.match(html, /<button disabled[^>]*>确认正式发布并通知师生/)
      assert.match(html, /重新检查发布条件/)
      let refreshed = false; state.openGate = async (batch, mode) => { assert.equal(batch.batchId, row.batchId); assert.equal(mode, 'pub'); refreshed = true }
      const retry = buttons.find(button => button.children.some(child => child.children === '重新检查发布条件'))
      await retry.click(); assert.equal(refreshed, true)
    } else {
      assert.doesNotMatch(html, /全校正式发布核验|电气学院尚有/)
      assert.match(html, /<button(?![^>]*disabled)[^>]*>确认进入预发布/)
    }
  }
})
