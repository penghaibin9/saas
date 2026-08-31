import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('教务首页待办展示具体对象、责任、时限、变化与下一步', () => {
  const dashboard = read('../src/modules/academicAffairs/views/AaDashboardView.vue')

  for (const contract of [
    'todoItems', 'todo.businessId', 'todo.entityType', 'todo.ownerRole', 'todo.deadline',
    'todo.recentChange', 'todo.reason', 'todo.nextStep', 'todo.primaryAction', 'todo.exactRoute'
  ]) assert.ok(dashboard.includes(contract), `缺少具体待办合同：${contract}`)

  assert.ok(dashboard.includes('具体到业务对象、责任原因与下一步动作'))
  assert.ok(dashboard.includes('@click="goTarget(todo.exactRoute)"'), '具体任务卡必须落到业务对象')
})

test('五类具体待办的目标页消费业务对象 ID', () => {
  const collegeReview = read('../src/modules/academicAffairs/views/AaGradeCollegeReviewView.vue')
  const publish = read('../src/modules/academicAffairs/views/AaGradePublishView.vue')
  const warning = read('../src/modules/academicAffairs/views/AaWarningConsoleView.vue')
  const graduation = read('../src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue')
  const router = read('../../backend/app/modules/academic_affairs/routers/grade_core_router.py')

  assert.ok(collegeReview.includes('query?.taskId'))
  assert.ok(publish.includes('query?.taskId'))
  assert.ok(collegeReview.includes('taskId: this.focusTaskId'))
  assert.ok(publish.includes('taskId: this.focusTaskId'))
  assert.ok(warning.includes('query.warningId'))
  assert.ok(graduation.includes('q.resultId'))
  assert.ok(router.includes('taskId: Optional[int] = None'))
})
