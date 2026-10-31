import test from 'node:test'
import assert from 'node:assert/strict'
import { page } from './academic-pc-parallel-b-harness.mjs'
import { matchPermission } from '../src/config/navPlan.js'
import * as teaching from '../src/modules/academicAffairs/constants/teaching.js'
import * as results from '../src/modules/academicAffairs/components/parallel-a/resultState.js'
import { readTaskPages, taskConfirmationEvidence } from '../src/modules/academicAffairs/components/parallel-a/taskFacts.js'

const ok = data => ({ code: 0, data })
const listed = (list, total = list.length) => ok({ list, total })
const ctx = { currentRole: { roleName: '学院教务' }, dataScope: { scope: 'COLLEGE' }, permissionPatterns: ['academicAffairs.teachingTask.*'] }
const task = { taskId: '9007199254740999', batchId: '9007199254740997', courseId: '5', status: 'ASSIGNED', teacherKey: 'teacher', teacherName: '任课教师', weeklyHours: 4 }
const vm = (name, api = {}) => page(name, { ...teaching, ...results, matchPermission, readTaskPages, taskConfirmationEvidence,
  academicAffairsApi: { listAllTasks: async () => listed([task]), getBatchTasks: async () => listed([task]), ...api },
  teachingTaskWorkbenchApi: { getBatch: async () => ok({ batchId: task.batchId, actions: { canAssign: true, canAdjust: true, canEditComposition: true } }) }
}, { ctx }).state

test('教师队列在服务端按本人、学期、状态和搜索分页，不遍历读取全部任务', async () => {
  const calls = []
  const state = vm('AaTeacherTaskConfirmView', { listAllTasks: async p => { calls.push(p); return listed([task], 65) } })
  state.currentTermId = '101'; state.statusFilter = 'ASSIGNED'; state.keyword = '基础'; state.pagination.page = 3
  await state.load()
  assert.equal(calls.length, 1)
  assert.deepEqual({ ...calls[0] }, { mine: true, termId: '101', status: 'ASSIGNED', keyword: '基础', page: 3, pageSize: 20 })
  assert.equal(state.pagination.total, 65)
})

test('合拆班页签将同一批次、学期和搜索条件传到分页查询', async () => {
  const calls = []
  const state = vm('AaTaskMergeSplitView', { listAllTasks: async p => { calls.push(p); return listed([], 45) } })
  state.$route.query = { batchId: task.batchId, termId: '101', keyword: '课程', panel: 'merged', page: '2' }
  state.restoreQuery(); await state.load()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].merged, true); assert.equal(calls[0].mergeable, undefined)
  assert.equal(calls[0].batchId, task.batchId); assert.equal(calls[0].page, 2)
  assert.equal(state.pagination.total, 45)
})

test('学院审核队列筛选与内嵌任务筛选使用不同地址参数', () => {
  const state = vm('AaTaskConfirmView')
  state.$route.query = { batchStatus: 'COLLEGE_CONFIRMED', batchKeyword: '选修', status: 'ASSIGNED', keyword: '数据库', queuePage: '2', page: '4' }
  state.restoreQuery()
  assert.equal(state.status, 'COLLEGE_CONFIRMED'); assert.equal(state.keyword, '选修'); assert.equal(state.page, 2)
})

test('分配超时后只能查询原任务，结果不受当前列表筛选影响', async () => {
  let writes = 0, assigned = false
  const state = vm('AaTeacherAssignConsoleView', {
    assignTeacher: async () => { writes++; throw new Error('连接中断') },
    listAllTasks: async p => p.taskId ? listed([{ ...task, teacherKey: assigned ? 'new-teacher' : task.teacherKey }]) : listed([])
  })
  state.loading = false; state.rows = [task]; state.openAssign(task); state.assign.teacherKey = 'new-teacher'
  await state.doAssign(); await state.doAssign()
  assert.equal(writes, 1); assert.ok(state.pendingAssignment)
  assigned = true; await state.queryPendingAssignment()
  assert.equal(state.pendingAssignment, null); assert.equal(state.receipt.pending, false)
})

test('调整冲突保留原因；换人响应丢失时不得重复提交', async () => {
  let writes = 0
  const state = vm('AaTaskAdjustView', { adjustTask: async () => { writes++; throw new Error('连接中断') } })
  state.loading = false; await state.openAdjust(task); state.adjust.teacherKey = 'new-teacher'; state.adjust.reason = '教师安排发生变化'
  await state.doAdjust(); await state.doAdjust()
  assert.equal(writes, 1); assert.equal(state.adjust.reason, '教师安排发生变化'); assert.ok(state.pendingAdjustment)
})

test('后端明确拒绝调整时保留原因，但不误记为结果未知', async () => {
  const state = vm('AaTaskAdjustView', { adjustTask: async () => { throw { code: 409001, message: '已有课表，不能直接调整' } } })
  state.loading = false; await state.openAdjust(task); state.adjust.reason = '教师安排发生变化'
  await state.doAdjust()
  assert.equal(state.pendingAdjustment, null)
  assert.equal(state.adjust.reason, '教师安排发生变化')
  assert.match(state.error, /已有课表/)
})

test('已通过批次仅有排课查看权限时提供排课入口，并保留学期和返回位置', () => {
  const state = vm('AaTaskBatchListView')
  state.ctx = { ...ctx, permissionPatterns: ['academicAffairs.teachingTask.view'] }
  const row = { batchId: task.batchId, termId: '101', status: 'APPROVED' }
  assert.equal(state.actionLabel(row), '查看办理进度')
  state.ctx = { ...ctx, permissionPatterns: ['academicAffairs.schedule.view'] }
  assert.equal(state.actionLabel(row), '进入本学期排课')
  let target; state.$router.push = value => { target = value }; state.$route.fullPath = '/admin/academic-affairs/teaching-tasks?page=2'
  state.openNext(row)
  assert.equal(target.path, '/admin/academic-affairs/schedule'); assert.equal(target.query.termId, '101'); assert.equal(target.query.batchId, undefined)
  assert.equal(target.query.returnTo, state.$route.fullPath)
})

test('排课和名单只接受开课页面的站内返回地址', () => {
  for (const name of ['AaScheduleBatchListView', 'AaTeachingClassListView']) {
    const state = vm(name)
    for (const target of ['https://example.com/', '//example.com/', '/admin/system/users', 123]) {
      state.$route.query = { returnTo: target }; assert.equal(state.taskReturnTo, '')
    }
    state.$route.query = { returnTo: '/admin/academic-affairs/teaching-tasks/9007199254740997?page=3' }
    assert.equal(state.taskReturnTo, state.$route.query.returnTo)
  }
})

test('教师查看名单携带本人任务的学期、教学班代码与精确返回位置', () => {
  const state = vm('AaTeacherTaskConfirmView')
  let target; state.$router.push = value => { target = value }; state.$route.fullPath = '/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId=9'
  state.openTeachingClass({ termId: '101', teachingClassCode: 'CLASS-1' })
  assert.equal(target.query.view, 'classes'); assert.equal(target.query.termId, '101')
  assert.equal(target.query.keyword, 'CLASS-1'); assert.equal(target.query.returnTo, state.$route.fullPath)
})
