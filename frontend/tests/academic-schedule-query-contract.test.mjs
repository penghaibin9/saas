import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { academicAffairsRoutes } from '../src/modules/academicAffairs/academic-affairs.routes.js'
import { canEnterRoute, clearPermissionPatterns, setModuleEntitlements, setPermissionPatterns } from '../src/security/permissionGate.js'

const root = path.resolve(import.meta.dirname, '..')
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

test('调停课学院与学校审批身份均可进入现行审批页，无审批权限仍拒绝', () => {
  const route = academicAffairsRoutes.flatMap(row => row.children || []).find(row => row.path === 'schedule-change/approval')
  assert.ok(route)
  try {
    setModuleEntitlements(['ACADEMIC_AFFAIRS'])
    for (const code of ['academicAffairs.scheduleChange.collegeReview', 'academicAffairs.scheduleChange.academicReview']) {
      setPermissionPatterns([code, 'academicAffairs.scheduleChange.view'])
      assert.equal(canEnterRoute(route.meta), true, code)
    }
    setPermissionPatterns(['academicAffairs.scheduleChange.view', 'academicAffairs.scheduleChange.apply'])
    assert.equal(canEnterRoute(route.meta), false)
    setPermissionPatterns(['academicAffairs.scheduleChange.academicReview'])
    setModuleEntitlements([])
    assert.equal(canEnterRoute(route.meta), false, '个人审批权限不能代替学校模块授权')
  } finally { clearPermissionPatterns() }
})

test('weekly schedule query covers all five operational dimensions with searchable pickers', () => {
  const source = read('src/modules/academicAffairs/views/AaWeekScheduleView.vue')
  for (const label of ['班级', '教师', '教室', '学生', '教学班']) {
    assert.match(source, new RegExp(`label: '${label}'`))
  }
  for (const picker of ['AppClassPicker', 'AppTeacherPicker', 'AppClassroomPicker', 'AppStudentPicker', 'AppTeachingClassPicker']) {
    assert.match(source, new RegExp(`<${picker}`))
  }
  assert.match(source, /teacher: this\.teacherName \|\| '本人课表'/)
  assert.doesNotMatch(source, /teacher: `教师 \$\{this\.teacherKey\}`/)
})

test('teacher schedule responses expose a display name instead of forcing internal keys into the UI', () => {
  const teacherView = read('src/modules/academicAffairs/views/AaTeacherScheduleView.vue')
  const backend = read('../backend/app/modules/academic_affairs/services/academic_affairs_schedule_teacher_relation_guard.py')
  assert.match(teacherView, /teacherName \|\| '本人'/)
  assert.match(teacherView, /res\.data\.teacherName/)
  assert.match(backend, /"teacherName": next/)
})

test('academic teacher selectors submit the stable login name as teacher_key', () => {
  const adapter = read('src/components/common/picker/orgAdapters.js')
  const academicAdapter = read('src/modules/academicAffairs/pickerAdapters.js')
  const teacherDirectory = read('../backend/app/modules/academic_affairs/services/academic_affairs_course_service.py')
  assert.match(adapter, /query\?\.valueField === 'loginName'/)
  assert.match(adapter, /t\.loginName \?\? t\.teacherKey/)
  assert.match(academicAdapter, /query\?\.valueField === 'loginName'/)
  assert.match(academicAdapter, /firstDefined\(t, \['loginName', 'teacherKey'\]\)/)
  assert.match(teacherDirectory, /"loginName": u\.login_name or ""/)

  for (const view of [
    'AaScheduleViewsView.vue',
    'AaTeacherScheduleView.vue',
    'AaWeekScheduleView.vue',
    'AaSemesterScheduleView.vue',
    'AaScheduleExportView.vue',
    'AaTaskDetailView.vue',
    'AaTaskAdjustView.vue',
    'AaTeacherAssignConsoleView.vue',
    'AaTeachingClassDetailView.vue',
    'AaExamConsoleView.vue'
  ]) {
    const source = read(`src/modules/academicAffairs/views/${view}`)
    assert.match(source, /teacherKeyQuery: \{ valueField: 'loginName' \}/, view)
    assert.match(source, /<AppTeacherPicker[^>]+:query="teacherKeyQuery"/, view)
  }
})

test('schedule routes remain available for class teacher room student and teaching class queries', () => {
  const routes = read('src/modules/academicAffairs/academic-affairs.routes.js')
  for (const segment of ['schedule/class/', 'schedule/teacher/', 'schedule/room/', 'schedule/student/', 'schedule/teaching-class/']) {
    assert.match(routes, new RegExp(segment.replaceAll('/', '\\/')))
  }
})

test('semester schedule renders the union of formal scope batches without misleading print', () => {
  const source = read('src/modules/academicAffairs/views/AaSemesterScheduleView.vue')
  const backend = read('../backend/app/modules/academic_affairs/services/academic_affairs_schedule_service.py')

  assert.match(backend, /def _current_published_batches/)
  assert.match(backend, /"batchIds": batch_ids/)
  assert.match(source, /this\.batchIds = res\.data\.batchIds/)
  assert.match(source, /this\.batchIds\.length === 1/)
})
