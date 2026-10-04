import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'

const url = new URL('../src/modules/academicAffairs/components/teaching-tasks/AaTaskSourceReview.vue', import.meta.url)
function component(api) {
  const source = readFileSync(url, 'utf8')
  const context = { teachingTaskWorkbenchApi: api }
  vm.runInNewContext(source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component ='), context)
  return context.component
}
function state(c, overrides = {}) {
  const props = { taskId: '1000000000000000001', termId: '52', otherTasks: [{ taskId: '1000000000000000002', label: '另一教学任务' }], contextKey: 'school-a:47' }
  const result = Object.assign(props, c.data.call(props), c.methods, overrides)
  Object.defineProperty(result, 'reviewKey', { get: () => c.computed.reviewKey.call(result) })
  return result
}
const response = () => ({ code: 0, data: { termId: '52', taskIds: ['1000000000000000001', '1000000000000000002'], tasks: [{ taskId: '1000000000000000001', courseName: '计算机基础', sourceProgramName: '原培养方案', formationModeLabel: '行政班', teacherName: '教师甲', teacherIdentityProven: true, rosterCount: 20 }], checks: [{ code: 'TEACHER_DIFFERENCE', label: '任课关系', status: 'BLOCKED', message: '正式任课关系不一致，请先核对' }], status: 'BLOCKED', summary: '来源核对存在差异', reviewOnly: true, nextStep: { label: '核对正式任课关系', description: '请责任学院核对；本页不确认承接。' } } })

test('来源核对只调用读取接口并保真大编号，阻断结果可见且没有承接确认动作', async () => {
  const calls = []
  const c = component({ getSourceReview: async (...args) => { calls.push(args); return response() } })
  const s = state(c)
  await s.load()
  assert.deepEqual(calls, [['1000000000000000001', '1000000000000000002']])
  assert.equal(s.state, 'ready')
  const source = readFileSync(url, 'utf8')
  const render = new Function('Vue', compile(source.match(/<template>([\s\S]*?)<\/template>/)[1], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const html = await renderToString(Vue.createSSRApp({ render, setup: () => s }))
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
