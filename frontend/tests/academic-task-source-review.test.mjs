import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { randomUUID } from 'node:crypto'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'

const url = new URL('../src/modules/academicAffairs/components/teaching-tasks/AaTaskSourceReview.vue', import.meta.url)
function component(api) {
  const source = readFileSync(url, 'utf8')
  const context = { teachingTaskWorkbenchApi: api, AaFormationProof: {}, AppConfirmDialog: {}, crypto: { randomUUID } }
  vm.runInNewContext(source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component ='), context)
  return context.component
}
function state(c, overrides = {}) {
  const props = { taskId: '1000000000000000001', termId: '52', otherTasks: [{ taskId: '1000000000000000002', label: '另一教学任务' }], contextKey: 'school-a:47' }
  const result = Object.assign(props, c.data.call(props), c.methods, { events: [], $emit: (...args) => result.events.push(args) }, overrides)
  for (const [key, fn] of Object.entries(c.computed)) Object.defineProperty(result, key, { enumerable: true, get: () => fn.call(result) })
  return result
}
const response = () => ({ code: 0, data: { termId: '52', taskIds: ['1000000000000000001', '1000000000000000002'], tasks: [{ taskId: '1000000000000000001', courseName: '计算机基础', sourceProgramName: '原培养方案', formationModeLabel: '行政班', teacherName: '教师甲', teacherIdentityProven: true, rosterCount: 20 }], checks: [{ code: 'TEACHER_DIFFERENCE', label: '任课关系', status: 'BLOCKED', message: '正式任课关系不一致，请先核对' }], status: 'BLOCKED', summary: '来源核对存在差异', reviewOnly: true, nextStep: { label: '核对正式任课关系', description: '请责任学院核对；本页不确认承接。' } } })

test('来源核对只调用读取接口并保真大编号，阻断结果可见且不开承接确认动作', async () => {
  const calls = []
  const c = component({ getSourceReview: async (...args) => { calls.push(args); return response() } })
  const s = state(c)
  await s.load()
  assert.deepEqual(calls, [['1000000000000000001', '1000000000000000002']])
  assert.equal(s.state, 'ready')
  const source = readFileSync(url, 'utf8')
  const render = new Function('Vue', compile(source.match(/<template>([\s\S]*?)<\/template>/)[1], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const html = await renderToString(Vue.createSSRApp({ render, components: { AaFormationProof: { render: () => null }, AppConfirmDialog: { render: () => null } }, setup: () => { const visible = { ...s }; delete visible.$emit; return visible } }))
  assert.match(html, /正式任课关系不一致/)
  assert.match(html, /原培养方案/)
  assert.doesNotMatch(html, /TEACHER_DIFFERENCE|BLOCKED|1000000000000000001|确认承接<\/button>|canConfirm/)
})

test('超过两条不自动选择比较任务，选择后只核对指定两条', async () => {
  let calls = 0
  const c = component({ getSourceReview: async () => { calls++; return response() } })
  const s = state(c, { otherTasks: [{ taskId: '1000000000000000002', label: '任务二' }, { taskId: '3', label: '任务三' }], selectedOtherTaskId: '' })
  await s.load()
  assert.equal(calls, 0)
  assert.equal(s.state, 'select')
  s.selectedOtherTaskId = '1000000000000000002'
  await s.load()
  assert.equal(calls, 1)
})

test('范围拒绝清空旧结果，上下文切换和销毁丢弃迟到响应', async () => {
  let finish
  let pending = new Promise(resolve => { finish = resolve })
  const c = component({ getSourceReview: () => pending })
  const s = state(c, { result: response().data })
  const load = s.load()
  assert.equal(s.result, null)
  s.contextKey = 'school-b:48'
  finish(response())
  await load
  assert.equal(s.result, null)
  pending = Promise.resolve({ code: 403, message: '无权查看该教学任务' })
  await s.load()
  assert.equal(s.state, 'error')
  assert.equal(s.result, null)
  assert.match(s.error, /无权查看/)
  pending = new Promise(resolve => { finish = resolve })
  const last = s.load()
  c.beforeUnmount.call(s)
  finish(response())
  await last
  assert.equal(s.result, null)
})

test('读取请求客户端只携带指定比较任务，不调用业务确认', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/api/teaching-task-workbench.api.js', import.meta.url), 'utf8')
  const calls = []
  const ctx = { request: async (...args) => { calls.push(args); return response().data } }
  vm.runInNewContext(source.replace(/^import .*$/gm, '').replace('export const teachingTaskWorkbenchApi =', 'api ='), ctx)
  const result = await ctx.api.getSourceReview('1000000000000000001', '1000000000000000002')
  assert.equal(result.code, 0)
  assert.equal(calls[0][0], '/academic-affairs/teaching-tasks/1000000000000000001/source-review')
  assert.equal(calls[0][1].params.otherTaskId, '1000000000000000002')
  assert.equal(calls[0][1].timeoutMs, 15000)
  assert.equal(calls[0][1].method, undefined)
})

test('不同学期或返回对象不一致时禁止显示结果，网络失败保留重读入口', async () => {
  let data = { ...response().data, termId: '53' }
  const c = component({ getSourceReview: async () => ({ code: 0, data }) })
  const s = state(c)
  await s.load()
  assert.equal(s.state, 'error')
  assert.equal(s.result, null)
  data = { ...response().data, taskIds: ['1000000000000000001', '3'] }
  await s.load()
  assert.equal(s.state, 'error')
  assert.equal(s.result, null)
  const failing = component({ getSourceReview: async () => { throw new Error('网络暂不可用，请重新读取') } })
  const failed = state(failing, { result: response().data })
  await failed.load()
  assert.equal(failed.result, null)
  assert.match(failed.error, /网络暂不可用/)
})

test('同名方案按权威版本及前后关系展示，两份来源分别展开且确认后重读当前比较', async () => {
  let reads = 0
  const data = { ...response().data, tasks: [
    { taskId: '1000000000000000001', sourceProgramCourseId: '1000000000000000091', sourceProgramName: '软件技术方案', sourceProgramVersion: 1, sourceRelationLabel: '原方案版本', formationProofLabel: '来源尚未证明' },
    { taskId: '1000000000000000002', sourceProgramCourseId: '1000000000000000092', sourceProgramName: '软件技术方案', sourceProgramVersion: 2, sourceRelationLabel: '后继方案版本', formationProofLabel: '历史依据已正式确认' }
  ] }
  const c = component({ getSourceReview: async () => { reads++; return { code: 0, data } } }), s = state(c)
  await s.load(); s.openFormationProof(s.result.tasks[0])
  assert.equal(s.proofSourceId, '1000000000000000091')
  s.openFormationProof(s.result.tasks[1])
  assert.equal(s.proofSourceId, '1000000000000000092')
  const text = readFileSync(url, 'utf8'), render = new Function('Vue', compile(text.match(/<template>([\s\S]*?)<\/template>/)[1], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  let confirmation
  const proof = { props: ['programCourseId', 'contextKey'], emits: ['confirmed'], setup(_props, { emit }) { confirmation = () => emit('confirmed'); return () => Vue.h('span', '本份来源补证') } }
  const visible = { ...s, reviewKey: s.reviewKey, load: s.load.bind(s) }
  const html = await renderToString(Vue.createSSRApp({ render, components: { AaFormationProof: proof, AppConfirmDialog: { render: () => null } }, setup: () => { delete visible.$emit; return visible } }))
  assert.match(html, /第1版/); assert.match(html, /第2版/); assert.match(html, /原方案版本/); assert.match(html, /后继方案版本/); assert.match(html, /历史依据已正式确认/)
  confirmation(); await Promise.resolve(); await Promise.resolve()
  assert.equal(reads, 2)
  assert.equal(s.proofSourceId, '')
})


const oldId = '1000000000000000001', newId = '1000000000000000002'
const checked = () => ({ ...response().data, status: 'CHECKED', checks: [], summary: '来源核对通过', confirmedHandoff: null,
  handoffAction: { allowed: true, reason: '', executionTaskId: oldId, successorTaskId: newId, expectedSourceFingerprint: 'a'.repeat(64) } })
const handoff = () => ({ handoffId: '1000000000000000088', termId: '52', executionTaskId: oldId, successorTaskId: newId, reason: '已核对正式课程来源', confirmedAt: '2026-10-05T12:00:00', summary: '原任务继续执行，后继来源已承接' })

test('仅采用后端严格授权与执行方向，短原因及错误方向不可提交', async () => {
  let writes = 0, data = checked()
  const c = component({ getSourceReview: async () => ({ code: 0, data }), confirmSourceHandoff: async () => { writes++ } }), s = state(c)
  await s.load(); s.reason = '短'; s.openConfirmation(); await s.confirmHandoff()
  assert.equal(writes, 0); assert.match(s.handoffError, /4至500/)
  s.reason = handoff().reason
  for (const value of [false, 'true', 1]) { s.result.handoffAction.allowed = value; s.openConfirmation(); assert.equal(s.canConfirm, false) }
  s.result.handoffAction.allowed = true; s.result.handoffAction.executionTaskId = '3'
  assert.equal(s.canConfirm, false)
  data = checked(); data.handoffAction.executionTaskId = newId; data.handoffAction.successorTaskId = oldId
  await s.load(); assert.equal(s.canConfirm, true)
  s.openConfirmation(); assert.equal(s.confirmationBody.executionTaskId, newId)
})

test('提交防重复并保真大编号，只有一致正式GET回执才能报完成与刷新', async () => {
  let reads = 0, finish
  const calls = []
  const c = component({ getSourceReview: async () => ({ code: 0, data: reads++ ? { ...checked(), confirmedHandoff: handoff(), handoffAction: { ...checked().handoffAction, allowed: false } } : checked() }),
    confirmSourceHandoff: (...args) => { calls.push(args); return new Promise(resolve => { finish = resolve }) } }), s = state(c)
  await s.load(); s.reason = handoff().reason; s.openConfirmation()
  const pending = s.confirmHandoff(); await s.confirmHandoff()
  assert.equal(calls.length, 1); assert.equal(calls[0][0], oldId); assert.equal(calls[0][1].successorTaskId, newId)
  assert.equal(s.events.length, 0)
  finish({ code: 0, data: handoff() }); await pending
  assert.equal(reads, 2); assert.equal(s.events.length, 1); assert.equal(s.events[0][0], 'confirmed')
  assert.match(s.receipt, /重新读取一致/); assert.equal(s.saving, false)
})

test('网络结果不明保留同一请求与原因，重试不新建标识', async () => {
  const calls = []
  const c = component({ getSourceReview: async () => ({ code: 0, data: checked() }), confirmSourceHandoff: async (...args) => { calls.push(args); return { code: 503001, message: '网络超时' } } }), s = state(c)
  await s.load(); s.reason = handoff().reason; s.openConfirmation(); await s.confirmHandoff()
  const key = calls[0][1].idempotencyKey
  assert.equal(s.events.length, 0); assert.match(s.handoffError, /同一请求标识/)
  s.openConfirmation(); await s.confirmHandoff()
  assert.equal(calls.length, 2); assert.equal(calls[1][1].idempotencyKey, key); assert.equal(calls[1][1].reason, handoff().reason)
})

test('409保留输入并要求人工重读，不自动取新版覆盖提交', async () => {
  let reads = 0, writes = 0
  const c = component({ getSourceReview: async () => { reads++; return { code: 0, data: checked() } }, confirmSourceHandoff: async () => { writes++; return { code: 'DATA_CONFLICT', httpStatus: 409, message: '来源已变化' } } }), s = state(c)
  await s.load(); s.reason = handoff().reason; s.openConfirmation(); await s.confirmHandoff()
  assert.equal(reads, 1); assert.equal(writes, 1); assert.equal(s.reason, handoff().reason); assert.equal(s.needsReload, true)
  s.openConfirmation(); await s.confirmHandoff(); assert.equal(writes, 1)
  await s.load(); assert.equal(s.reason, handoff().reason); assert.equal(s.needsReload, false)
})

test('POST成功但回读缺失或错对象不能报完成，后续正式回读才消除不明确', async () => {
  for (const mismatch of [null, { ...handoff(), handoffId: '1000000000000000099' }]) {
    let reads = 0, data
    const c = component({ getSourceReview: async () => ({ code: 0, data: reads++ ? (data || { ...checked(), confirmedHandoff: mismatch }) : checked() }), confirmSourceHandoff: async () => ({ code: 0, data: handoff() }) }), s = state(c)
    await s.load(); s.reason = handoff().reason; s.openConfirmation(); await s.confirmHandoff()
    assert.equal(s.events.length, 0); assert.equal(s.needsReload, true)
    data = { ...checked(), confirmedHandoff: handoff() }
    await s.load(); assert.equal(s.events.length, 1)
  }
})

test('确认期间切换上下文或销毁丢弃迟到回执，不能刷新其他学校', async () => {
  for (const destroy of [false, true]) {
    let finish, reads = 0
    const c = component({ getSourceReview: async () => { reads++; return { code: 0, data: checked() } }, confirmSourceHandoff: () => new Promise(resolve => { finish = resolve }) }), s = state(c)
    await s.load(); s.reason = handoff().reason; s.openConfirmation(); const pending = s.confirmHandoff()
    if (destroy) c.beforeUnmount.call(s)
    else { s.contextKey = 'school-b:48'; c.watch.reviewKey.handler.call(s) }
    finish({ code: 0, data: handoff() }); await pending
    assert.equal(s.events.length, 0)
    if (!destroy) assert.equal(s.pendingCommand, null)
    assert.ok(reads <= 2)
  }
})

test('承接客户端使用正式POST与请求体、十五秒等待，完整保留错误码', async () => {
  const text = readFileSync(new URL('../src/modules/academicAffairs/api/teaching-task-workbench.api.js', import.meta.url), 'utf8')
  const calls = [], ctx = { request: async (...args) => { calls.push(args); return handoff() } }
  vm.runInNewContext(text.replace(/^import .*$/gm, '').replace('export const teachingTaskWorkbenchApi =', 'api ='), ctx)
  const body = { successorTaskId: newId, reason: handoff().reason, expectedSourceFingerprint: 'a'.repeat(64), idempotencyKey: 'formal-request-001' }
  const result = await ctx.api.confirmSourceHandoff(oldId, body)
  assert.equal(result.code, 0); assert.equal(calls[0][0], `/academic-affairs/teaching-tasks/${oldId}/source-handoff`)
  assert.equal(calls[0][1].method, 'POST'); assert.equal(calls[0][1].body, body); assert.equal(calls[0][1].timeoutMs, 15000)
})


test('首请求超时后指纹变化仍可显式重试原请求，由服务器裁决而不改body或标识', async () => {
  let data = checked(), writes = 0
  const calls = []
  const c = component({ getSourceReview: async () => ({ code: 0, data }), confirmSourceHandoff: async (...args) => { calls.push(args); writes++; return writes === 1 ? { code: 503001, message: '请求超时' } : { code: 'DATA_CONFLICT', httpStatus: 409, message: '当前来源指纹已变化' } } }), s = state(c)
  await s.load(); s.reason = handoff().reason; s.openConfirmation(); await s.confirmHandoff()
  const original = JSON.stringify(calls[0])
  data = { ...checked(), handoffAction: { ...checked().handoffAction, expectedSourceFingerprint: 'b'.repeat(64) } }
  await s.load(); s.openConfirmation(); await s.confirmHandoff()
  assert.equal(writes, 2); assert.equal(JSON.stringify(calls[1]), original)
  assert.equal(s.needsReload, true); assert.match(s.handoffError, /当前来源指纹已变化/); assert.equal(s.events.length, 0)
})

test('未知结果回读到真实条件阻断时等待后端，不沿旧许可提交', async () => {
  let data = checked(), writes = 0
  const c = component({ getSourceReview: async () => ({ code: 0, data }), confirmSourceHandoff: async () => { writes++; return { code: 503001, message: '请求超时' } } }), s = state(c)
  await s.load(); s.reason = handoff().reason; s.openConfirmation(); await s.confirmHandoff()
  data = { ...checked(), status: 'BLOCKED', handoffAction: { ...checked().handoffAction, allowed: false, reason: '后继任务已有真实成绩引用，不能承接' } }
  await s.load(); s.openConfirmation(); await s.confirmHandoff()
  assert.equal(writes, 1); assert.equal(s.canConfirm, false); assert.equal(s.result.handoffAction.reason, '后继任务已有真实成绩引用，不能承接')
})
