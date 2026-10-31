import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compile } from '@vue/compiler-dom'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { page } from './academic-pc-parallel-b-harness.mjs'
import { matchPermission } from '../src/config/navPlan.js'

const source = name => readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
const button = { props: ['disabled'], setup: (props, { slots }) => () => Vue.h('button', { disabled: props.disabled }, slots.default?.()) }
function render(template, state) {
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  return renderToString(Vue.createSSRApp({ data: () => state, render, components: { AppButton: button, AppStatusTag: { render: () => null } } }))
}

test('跨批次分配队列不把首行当作当前任务，指定批次仍能返回', async () => {
  const template = source('AaTeacherAssignConsoleView').match(/<template(?: v-if="batchId")? #actions>([\s\S]*?)<\/template>/)[1]
  const state = { primaryRow: { taskId: 'hidden-task', batchId: 'hidden-batch' }, canAssign: () => true, openAssign() {}, openBatch() {}, batchId: '' }
  const queue = await render('<div v-if="batchId">' + template + '</div>', state)
  assert.doesNotMatch(queue, /分配当前任务|来源批次|返回批次/)
  assert.match(await render(template, { ...state, batchId: '34' }), /返回批次/)
})

test('行内分配保留允许状态，无权限和已确认任务不出现分配动作', async () => {
  const content = source('AaTeacherAssignConsoleView')
  const template = content.match(/<template #cell-actions="\{ row \}">([\s\S]*?)<\/template>/)[1]
  for (const [patterns, status, allowed] of [
    [['academicAffairs.teachingTask.assign'], 'PENDING_ASSIGN', true],
    [['academicAffairs.teachingTask.assign'], 'ASSIGNED', true],
    [['academicAffairs.teachingTask.assign'], 'TEACHER_CONFIRMED', false],
    [['academicAffairs.teachingTask.view'], 'PENDING_ASSIGN', false]
  ]) {
    const { state } = page('AaTeacherAssignConsoleView', { matchPermission }, { ctx: { permissionPatterns: patterns } })
    const html = await render(template, { row: { status, teacherKey: '' }, assign: { submitting: false }, canAssign: row => state.canAssign(row), openAssign() {} })
    assert.equal(/<button[^>]*>分配<\/button>/.test(html), allowed)
  }
})

test('成绩任务显示课程和教学班，内部课程编号不出现在列表正文', async () => {
  const template = source('AaGradeEntryView').match(/<li v-for="t in myTasks"[\s\S]*?<\/li>/)[0]
  const html = await render(template, {
    myTasks: [{ gradeTaskId: '9007199254740997', courseId: '9007199254740998', courseName: '软件测试', teachingClassName: '软件2601班', status: 'DRAFT' }],
    isAdminRole: true, writeBusy: false, statusColor: () => 'default', statusLabel: () => '未开始', canRemind: () => false, openTask() {}
  })
  assert.match(html, /软件测试/)
  assert.match(html, /软件2601班/)
  assert.match(html, /进入/)
  assert.doesNotMatch(html, /9007199254740998|课程ID/)
})
