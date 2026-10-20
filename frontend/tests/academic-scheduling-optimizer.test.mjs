// Keep candidate behavior tests inside the normal frontend discovery set.
import '../../tests/scheduling_kit/candidate-controller.test.mjs'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'

function panel() {
  const source = readFileSync(new URL('../src/modules/academicAffairs/components/AaSchedulingOptimizerPanel.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component =')
  const context = { AaScheduleGrid: {}, matchPermission: () => true, optimizerLabel: () => '排课条件待核对', diagnosticLabels: {}, safeBusinessMessage: (message, fallback) => message || fallback }
  vm.runInNewContext(script, context)
  return context.component
}

test('优化器保留分段欠学时任务，重排复选只改变旧模式量不改变权威学时', async () => {
  const component = panel()
  const task = { id: '14944', remainingPeriods: 0, autoPeriods: 2, optimizerSupported: false, expectedContactHours: 36, scheduledContactHours: 26, missingContactHours: 10, excessContactHours: 0, weeklyOverloadCount: 0 }
  const state = { ...component.methods, state: { context: { tasks: [task], canGenerate: true } }, replaceAuto: false, confirmed: true, reason: '核对学校排课', anchor: '2026-09-07', ctx: { permissionPatterns: [] } }
  state.tasks = component.computed.tasks.call(state)
  assert.equal(state.tasks.length, 1)
  assert.match(state.taskHoursText(state.tasks[0]), /缺 10 学时/)
  assert.equal(component.computed.canGenerate.call(state), false)
  state.replaceAuto = true
  state.tasks = component.computed.tasks.call(state)
  assert.equal(state.tasks[0].remainingPeriods, 2)
  assert.match(state.taskHoursText(state.tasks[0]), /已排 26 学时.*缺 10 学时/)
  assert.equal(component.computed.canGenerate.call(state), false)
  assert.equal(state.blockerText({ code: 'SEGMENTED_ACTIVITY_PLAN_REQUIRED', message: '该课程需要分段安排，请先手工补排。' }), '该课程需要分段安排，请先手工补排。')
  assert.match(state.taskHoursText({ remainingPeriods: 2 }), /待核对/)
  const source = readFileSync(new URL('../src/modules/academicAffairs/components/AaSchedulingOptimizerPanel.vue', import.meta.url), 'utf8')
  const template = source.match(/<tbody>[\s\S]*?<\/tbody>/)[0] + source.match(/<ul v-if="state.context\?\.blockers\?\.length">[\s\S]*?<\/ul>/)[0]
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  state.state.context.blockers = [{ code: 'SEGMENTED_ACTIVITY_PLAN_REQUIRED', message: '该课程需要分段安排，请先手工补排。' }]
  const html = await renderToString(Vue.createSSRApp({ render, setup: () => ({ ...state, visibleTasks: state.tasks, parities: {}, patterns: {}, gaps: {}, text: { pattern: '连排规则', gap: '间隔' } }) }))
  assert.match(html, /缺 10 学时/)
  assert.match(html, /该课程需要分段安排，请先手工补排/)
  assert.doesNotMatch(html, /SEGMENTED_ACTIVITY_PLAN_REQUIRED/)
})
