import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from 'vue/server-renderer'
import { TODO_TYPE_LABELS, resolveRecipe } from '../src/modules/workbench/config/workbenchRecipes.js'
import { safeLocalizedText, isTechnicalUiMessage } from '../src/utils/presentationSafety.js'

const source = readFileSync(new URL('../src/modules/workbench/views/WorkbenchView.vue', import.meta.url), 'utf8').replaceAll('\r', '')
const method = source.split('    todoMeta(t) {')[1].split('\n    }\n')[0]
const todoMeta = new Function('t', 'TODO_TYPE_LABELS', 'safeLocalizedText', 'isTechnicalUiMessage', method)
const show = (todo, role) => todoMeta.call({ recipe: resolveRecipe(role) }, todo, TODO_TYPE_LABELS, safeLocalizedText, isTechnicalUiMessage)

test('待办类型复用已有中文名称，未知代码不外露', () => {
  assert.equal(show({ todoType: 'RISK_HANDLE' }), '风险待处置')
  assert.equal(show({ todoType: 'AA_SCHEDULE_CHANGE_APPROVAL' }), '调停课待审')
  assert.equal(show({ todoType: 'UNRECOGNIZED_ACTION' }), '其他事项')
  assert.equal(show({ todoType: 'constructor' }), '其他事项')
  assert.equal(show({ todoType: '__proto__' }), '其他事项')
  assert.equal(show({}), '其他事项')
  assert.equal(show({ moduleName: '内部 UNKNOWN_ACTION', todoType: 'RISK_HANDLE' }), '风险待处置')
})

test('待办读取失败时不把默认零值显示成没有待办', async () => {
  const snippet = source.match(/<header class="wb-section-head"><h2>待我办理[\s\S]*?<\/header>/)[0]
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const error of ['', '读取失败']) {
    const html = await renderToString(Vue.createSSRApp({ data: () => ({ error, loading: false, todoTotal: 0 }), methods: { showBusinessQueue() {} }, render }))
    assert.ok(html.includes(error ? '<small>—</small>' : '<small>0</small>'))
  }
})

test('待办保留中文业务名称和经办人，不改原数据与跳转', () => {
  const todo = { moduleName: '课程调整', todoType: 'AA_SCHEDULE_CHANGE_APPROVAL', assigneeName: '测试教师', typedRouteTarget: '/approved-route', recordId: '1000000000000000007' }
  const original = structuredClone(todo)
  assert.equal(show(todo), '课程调整 · 测试教师')
  assert.deepEqual(todo, original)
})

test('导师批阅与评阅人评阅沿用各自角色配方的业务名称', () => {
  assert.equal(show({ todoType: 'GD_FINAL_REVIEW' }, 'GD_MENTOR'), '成果待批阅')
  assert.equal(show({ todoType: 'GD_FINAL_REVIEW' }, 'GD_REVIEWER'), '成果待评阅')
})

test('资助待办正文不再展示数据库编号，也不把待核验改为未填写', () => {
  for (const [todoType, expected] of [['WORK_STUDY_REVIEW', '勤工助学'], ['STUDENT_LOAN_CONFIRM', '助学贷款'], ['FEE_REDUCTION_FULFILL', '减免临补']]) {
    assert.equal(show({ todoType, recordId: '1000000000000000007', bizId: '123' }), expected)
    assert.equal(show({ todoType }), expected)
  }
})

test('非学工角色也有中文折叠标题，不使用浏览器默认英文标题', async () => {
  const snippet = source.match(/<details :open="!showStudentAffairs"[^>]*>[\s\S]*?<\/summary>/)[0] + '</details>'
  const render = new Function('Vue', compile(snippet, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const showStudentAffairs of [true, false]) {
    const html = await renderToString(Vue.createSSRApp({ data: () => ({ showStudentAffairs }), render }))
    assert.match(html, /<summary>我的待办与个人设置<\/summary>/)
    assert.equal(/<details[^>]*\bopen\b/.test(html), !showStudentAffairs)
  }
})

test('逾期数字已在汇总显示时不重复提醒，隐藏汇总后仍保留提醒及其他风险', () => {
  const body = source.match(/visibleRiskItems\(\) \{([\s\S]*?)\n {4}\}/)[1]
  const visible = new Function(body)
  const context = { riskItems: [{ key: 'overdue', count: 2 }, { key: 'academicWarning', count: 3 }], visibleSummaryCues: [{ source: 'summary.overdue' }] }
  assert.deepEqual(visible.call(context), [{ key: 'academicWarning', count: 3 }])
  context.visibleSummaryCues = []
  assert.equal(visible.call(context).length, 2)
})

test('学工数据正常时数字只在业务行展示，加载或失败时保留独立审批入口', async () => {
  const view = readFileSync(new URL('../src/modules/workbench/components/StudentAffairsPriorityPanel.vue', import.meta.url), 'utf8')
  const script = view.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
  const options = new Function('matchPermission', 'studentAffairsApi', script)(() => true, {})
  const template = view.slice(view.indexOf('<template>') + 10, view.lastIndexOf('</template>'))
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  for (const [loading, error] of [[false, ''], [true, ''], [false, '读取失败']]) {
    const html = await renderToString(Vue.createSSRApp({ ...options, render, data: () => ({ ...options.data(), loading, error, dashboard: {
      summaryCards: [{ key: 'pendingLeave', value: 3, drillPath: '/leave' }, { key: 'riskStudents', value: 5, drillPath: '/risk' }], riskSummary: { openStudentCount: 5 }
    } }) }, { pending: 2, ctx: { permissionPatterns: ['*'], currentRole: {}, dataScope: {} } }))
    assert.equal(html.includes('priority-brief'), loading || !!error)
    assert.match(html, /<strong>2<\/strong>/)
    if (!loading && !error) {
      assert.match(html, /<strong>3<\/strong>/)
      assert.match(html, /<strong>5<\/strong>/)
    }
  }
})
