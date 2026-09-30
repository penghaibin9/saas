import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import * as flow from '../src/modules/academicAffairs/academicFlowContext.js'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('教务首页待办展示具体对象、责任、时限、状态与下一步', () => {
  const dashboard = read('../src/modules/academicAffairs/views/AaDashboardView.vue')
  const workspace = read('../src/modules/academicAffairs/components/AaOverviewWorkspace.vue')

  assert.ok(dashboard.includes("activePanel === 'todos'"), '教务待办入口必须加载正式责任队列工作区')
  assert.ok(dashboard.includes('AaOverviewWorkspace'), '教务总览和待办必须共用正式责任队列')
  for (const contract of ['todoId', 'sourceBizId', 'responsibility', 'assignmentReason', 'dueAt', 'blocker', 'allowedActions', 'routeExact', 'typedRouteTarget']) {
    assert.ok(workspace.includes(contract), `缺少具体待办合同：${contract}`)
  }

  for (const label of ['来源对象', '责任岗位', '截止时间', '下一步', '办理入口']) assert.ok(workspace.includes(label), `缺少待办展示字段：${label}`)
  assert.ok(workspace.includes('statusLabel(row.status)'), '具体任务必须展示正式待办状态')
  assert.ok(workspace.includes('@click="openTodo(row)"'), '具体任务必须通过校验后的 typed route 落到业务对象')
  assert.ok(workspace.includes("row.allowedActions?.includes('OPEN')"), '没有正式 OPEN 能力的任务不得进入对象')
})

test('五类具体待办的目标页消费业务对象 ID', async () => {
  const collegeReview = read('../src/modules/academicAffairs/views/AaGradeCollegeReviewView.vue')
  const publish = read('../src/modules/academicAffairs/views/AaGradePublishView.vue')
  const warning = read('../src/modules/academicAffairs/views/AaWarningConsoleView.vue')
  const graduation = read('../src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue')
  const router = read('../../backend/app/modules/academic_affairs/routers/grade_core_router.py')

  assert.ok(collegeReview.includes('query?.taskId'))
  assert.ok(collegeReview.includes('taskId: this.focusTaskId'))
  assert.ok(warning.includes('query.warningId'))
  assert.ok(graduation.includes('q.resultId'))
  assert.ok(router.includes('taskId: Optional[int] = None'))

  const calls = []
  const sandbox = { dependencies: { ...flow, academicAffairsApi: { getGradeTasks: async query => {
    calls.push(query)
    return { code: 0, data: { list: [{ gradeTaskId: query.taskId, status: 'PUBLISHED' }], total: 1 } }
  } } } }
  vm.runInNewContext(publish.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component ='), sandbox)
  const component = sandbox.component
  const state = { ...component.data(), ...component.methods,
    academicFlow: { identity: () => 'same-school-role', restorePosition() {} } }
  state.readGate = flow.createAcademicRequestGate(() => state.contextKey())
  for (const taskId of ['9007199254740999', '9007199254740997']) {
    state.$route = { fullPath: `/admin/academic-affairs/grade-publish?taskId=${taskId}`, query: { taskId } }
    await state.syncRoute()
    assert.equal(calls.at(-1).taskId, taskId)
    assert.equal(calls.at(-1).status, undefined)
    assert.equal(calls.at(-1).page, 1)
    assert.equal(state.rows.length, 1)
    assert.equal(state.rows[0].gradeTaskId, taskId)
    assert.equal(state.focusTaskId, taskId)
    assert.equal(state.error, '')
  }
  assert.equal(calls.length, 2)
})
