import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const src = (...parts) => fs.readFileSync(path.resolve(here, '..', 'src', ...parts), 'utf8')

test('dedicated teacher today page uses shared ModulePageShell and real teacher facts', () => {
  const source = src('modules/academicAffairs/views/AaTeacherTodayView.vue')
  assert.match(source, /<ModulePageShell/)
  assert.match(source, /getMyTeacherToday/)
  assert.match(source, /listAllTasks\(\{ mine: true/)
  assert.match(source, /scheduleChangeApi\.list/)
  assert.match(source, /academicAffairsTextbookApi\.listSelections/)
  assert.match(source, /academicAffairsClassroomBookingApi\.list/)
  assert.match(source, /academicAffairsLabBookingApi\.list/)
  assert.doesNotMatch(source, /mock/i)
})

test('week and semester schedule remove arbitrary student and teacher lookup from ACADEMIC_TEACHER mode', () => {
  const week = src('modules/academicAffairs/views/AaWeekScheduleView.vue')
  const semester = src('modules/academicAffairs/views/AaSemesterScheduleView.vue')
  for (const text of [week, semester]) {
    assert.match(text, /isAcademicTeacher\(\)/)
    assert.match(text, /visibleDims\(\)/)
    assert.match(text, /\['teacher', 'class', 'room', 'teachingClass'\]/)
    assert.match(text, /v-if="!isAcademicTeacher" class="aa-filter__item"/)
  }
})

test('teacher resource booking workspace is explicitly presented as my booking ledger', () => {
  const source = src('modules/academicAffairs/components/parallel-a/ResourceBookingWorkspace.vue')
  assert.match(source, /isAcademicTeacher\(\)/)
  assert.match(source, /我的当日预约/)
  assert.match(source, /下方台账只显示本人预约/)
})

test('teacher program and course pages are presented as formal read-only references', () => {
  const program = src('modules/academicAffairs/views/AaProgramListView.vue')
  const course = src('modules/academicAffairs/views/AaCourseListView.vue')
  assert.match(program, /仅查看学校已经正式发布、生效或冻结留存的培养方案/)
  assert.match(program, /v-if="!isAcademicTeacher".*opening-plan/)
  assert.match(course, /仅查看已经正式启用的课程版本/)
  assert.match(course, /v-if="!isAcademicTeacher".*downloadCourseTemplate/)
})

test('grade and textbook teacher task pickers request mine scope', () => {
  const grade = src('modules/academicAffairs/views/AaGradeEntryView.vue')
  const textbook = src('modules/academicAffairs/views/AaTextbookConsoleView.vue')
  assert.match(grade, /:query="\{ mine: !isAdminRole \}"/)
  assert.match(textbook, /mine: isAcademicTeacher/)
  assert.match(textbook, /resolveTab\(value\)/)
})

test('teacher schedule pickers stay term-aware so visible objects should be openable', () => {
  const week = src('modules/academicAffairs/views/AaWeekScheduleView.vue')
  const semester = src('modules/academicAffairs/views/AaSemesterScheduleView.vue')
  const klass = src('modules/academicAffairs/views/AaClassScheduleView.vue')
  const teachingClass = src('modules/academicAffairs/views/AaTeachingClassScheduleView.vue')
  for (const text of [week, semester, klass, teachingClass]) {
    assert.match(text, /:query="\{ termId: termId \|\| undefined \}"/)
  }
  assert.match(klass, /initializeTeacherTerm/)
  assert.match(teachingClass, /initializeTeacherTerm/)
})
