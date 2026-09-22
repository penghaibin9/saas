import test from 'node:test'
import assert from 'node:assert/strict'
import { getVisibleNavPlan } from '../src/config/navPlan.js'
import {
  academicTeacherActiveModule,
  academicTeacherDefaultPath,
  filterAcademicTeacherSearchResults,
  projectAcademicTeacherModules
} from '../src/modules/academicAffairs/config/academicTeacherNavigation.js'

const ctx = {
  currentRole: { roleCode: 'ACADEMIC_TEACHER' },
  permissionPatterns: [
    'academicAffairs.teachingTask.view', 'academicAffairs.schedule.view',
    'academicAffairs.classroom.view', 'academicAffairs.scheduleChange.apply',
    'academicAffairs.scheduleChange.view', 'academicAffairs.grade.input',
    'academicAffairs.gradeChange.apply', 'academicAffairs.attendance.view',
    'academicAffairs.textbook.view', 'academicAffairs.textbook.selection.manage',
    'academicAffairs.lab.view', 'academicAffairs.resourceOccupancy.view',
    'academicAffairs.program.view', 'academicAffairs.course.view'
  ]
}

function sourceModules() {
  return getVisibleNavPlan({ includePlanned: false, permissionPatterns: ctx.permissionPatterns, ctxKey: 'teacher-projection' })
    .find(group => group.key === 'academic-affairs')?.children || []
}

test('ACADEMIC_TEACHER gets the bounded six-workspace daily teaching IA', () => {
  const modules = projectAcademicTeacherModules(sourceModules(), ctx)
  assert.deepEqual(modules.map(row => row.label), [
    '我的教学', '我的课表', '课表查询', '成绩与考勤', '教材与资源', '教学资料'
  ])
  const labels = modules.flatMap(row => row.children.map(leaf => leaf.label))
  for (const expected of [
    '今日教学', '教学任务确认', '个人课表', '调停课申请', '我的调停课记录',
    '班级课表', '教室课表', '教学班课表', '周课表', '学期课表',
    '成绩录入与提交', '成绩更正申请', '课堂考勤统计', '考勤场次查询',
    '教材选用', '教室预约', '实训室预约', '资源占用查询', '培养方案', '课程库'
  ]) assert.ok(labels.includes(expected), expected)
  for (const forbidden of ['排课规则', '自动排课', '教务发布（发布/退回/归档）', '费用台账', '教材库存']) {
    assert.equal(labels.includes(forbidden), false, forbidden)
  }
})

test('teacher center landing uses dedicated today page and public-shell page ids are unique', () => {
  const modules = projectAcademicTeacherModules(sourceModules(), ctx)
  assert.equal(academicTeacherDefaultPath(ctx), '/admin/academic-affairs/teacher/today')
  assert.equal(academicTeacherActiveModule(modules, '/admin/academic-affairs/teacher/today', ctx), 'aa-teacher-my-teaching')
  assert.equal(academicTeacherActiveModule(modules, '/admin/academic-affairs/schedule/teacher/teacher01', ctx), 'aa-teacher-my-schedule')
  const leaves = modules.flatMap(row => row.children)
  assert.equal(new Set(leaves.map(row => row.leafId)).size, leaves.length)
  assert.notEqual(
    leaves.find(row => row.label === '今日教学')?.leafId,
    leaves.find(row => row.label === '个人课表')?.leafId
  )
})

test('teacher global search cannot re-expose administrator academic pages or student search', () => {
  const modules = sourceModules()
  const source = [
    { kind: '学生', label: '张三', to: '/admin/student/1' },
    { kind: '功能/页面', label: '排课规则', to: '/admin/academic-affairs/scheduling?tab=rules' },
    { kind: '功能/页面', label: '方案控制台', to: '/admin/academic-affairs/programs/console' },
    { kind: '功能/页面', label: '个人课表', to: '/admin/academic-affairs/schedule/teacher' },
    { kind: '帮助文档', label: '帮助', to: '/admin/help?topic=x' }
  ]
  const result = filterAcademicTeacherSearchResults(source, ctx, modules)
  assert.deepEqual(result.map(row => row.label), ['个人课表', '帮助'])
})
