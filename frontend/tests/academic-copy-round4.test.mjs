import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { page } from './academic-pc-parallel-b-harness.mjs'
import { matchPermission } from '../src/config/navPlan.js'

const read = name => readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
const compileRender = template => new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)

test('确认队列不预设当前审核阶段，保留真实批次状态和详情选择', async () => {
  const rows = [{ batchId: '9007199254740997', batchName: '秋季教学任务', termLabel: '2026秋', status: 'APPROVED', nextAction: { label: '可进入排课' } }]
  const wrapper = { setup: (_, { slots }) => () => Vue.h('section', slots.default?.()) }
  const components = {
    ModulePageShell: wrapper,
    AppButton: { setup: (_, { slots }) => () => Vue.h('button', slots.default?.()) },
    AppTermEntityPicker: { render: () => Vue.h('input') },
    AppStatusTag: { props: ['label'], setup: p => () => Vue.h('span', p.label) },
    AaTeachingTaskStageRail: { render: () => Vue.h('p', '固定预设阶段') },
    AaTaskDetailView: { props: ['selectedBatchId'], setup: p => () => Vue.h('section', { 'data-batch': p.selectedBatchId }, '批次详情') },
    EmptyState: { props: ['title'], setup: p => () => Vue.h('p', p.title) }, ErrorState: wrapper, LoadingState: wrapper
  }
  for (const selectedBatchId of ['', rows[0].batchId]) {
    const html = await renderToString(Vue.createSSRApp({
      data: () => ({ ctx: { currentRole: {}, dataScope: {} }, rows, selectedBatchId, loading: false, error: '', page: 1, total: 1, termId: '', status: '', keyword: '' }),
      methods: { taskBatchColor: () => 'success', statusLabel: () => '已通过', selectBatch() {}, changePage() {}, query() {}, load() {} },
      render: compileRender(parse(read('AaTaskConfirmView')).descriptor.template.content), components
    }))
    assert.match(html, /秋季教学任务/)
    assert.match(html, /已通过/)
    assert.match(html, /可进入排课/)
    assert.doesNotMatch(html, /固定预设阶段|批次 #/)
    assert.equal(html.includes('批次详情'), !!selectedBatchId)
  }
})

test('选任务时调整规则默认折叠，进入调整后隐藏总则，换人确认、重审和已排课限制保留', async () => {
  const template = read('AaTaskAdjustView').match(/<details v-if="!adjust.visible" class="mp-note">[\s\S]*?<\/details>/)?.[0]
  assert.ok(template)
  const show = visible => renderToString(Vue.createSSRApp({ render: compileRender(template), data: () => ({ adjust: { visible } }) }))
  const html = await show(false)
  assert.match(html, /<details class="mp-note">/)
  assert.doesNotMatch(html, /<details[^>]*\sopen/)
  for (const rule of ['新教师本人确认', '学校终审也须重新办理', '已有课表请走排课变更', '已并入合班']) assert.ok(html.includes(rule))
  assert.doesNotMatch(await show(true), /<details|哪些调整需要重新确认/)
})

test('精简合班说明后仍要求同批次同课程版本，学校只读范围不增加权限', () => {
  const { state } = page('AaTaskMergeSplitView', { matchPermission }, { ctx: { permissionPatterns: ['*'], dataScope: { scope: 'COLLEGE' } } })
  state.loading = false
  state.all = ['1', '2'].map(taskId => ({ taskId, batchId: 'b', courseId: 'v1', status: 'ASSIGNED' }))
  state.selected = ['1', '2']; state.batchWorkbench = { batchId: 'b', actions: { canEditComposition: true } }
  assert.equal(state.canMerge, true)
  state.all[1].courseId = 'v2'; assert.equal(state.canMerge, false)
  state.all[1].courseId = 'v1'; state.all[1].batchId = 'other'; assert.equal(state.canMerge, false)
  state.all[1].batchId = 'b'; state.ctx.dataScope.scope = 'TENANT_ALL'; assert.equal(state.canMerge, false)
})
