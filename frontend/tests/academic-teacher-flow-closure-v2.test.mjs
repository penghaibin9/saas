import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const src = (...parts) => fs.readFileSync(path.resolve(here, '..', 'src', ...parts), 'utf8')

test('dedicated teacher today page uses one current-term authoritative workbench', () => {
  const source = src('modules/academicAffairs/views/AaTeacherTodayView.vue')
  assert.match(source, /<ModulePageShell/)
  assert.match(source, /getMyTeacherToday/)
  assert.match(source, /data\.workbench/)
  assert.match(source, /openAttendanceSession/)
  assert.match(source, /开始\/继续点名/)
  assert.doesNotMatch(source, /pageSize:\s*100/)
  assert.doesNotMatch(source, /scheduleChangeApi\.list/)
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


test('schedule change STOP and MAKEUP require one concrete teaching week', () => {
  const source = src('modules/academicAffairs/views/AaScheduleChangeApplyView.vue')
  assert.match(source, /停课教学周/)
  assert.match(source, /补课教学周/)
  assert.match(source, /normalizeOccurrenceFields/)
  assert.match(source, /targetEndWeek = week > 0 \? week : null/)
  assert.doesNotMatch(source, /delete body\.targetStartWeek/)
})

test('PC attendance exposes canonical mark and submit interactions', () => {
  const source = src('modules/academicAffairs/views/AaAttendanceStatsView.vue')
  const api = src('modules/academicAffairs/api/academic-affairs.api.js')
  assert.match(source, /markAttendanceSession/)
  assert.match(source, /submitAttendanceSession/)
  assert.match(api, /attendance\/sessions\/open/)
  assert.match(api, /attendance\/sessions\/\$\{sessionId\}\/mark/)
})

test('teacher workbench deep-links exact business objects', () => {
  const task = src('modules/academicAffairs/views/AaTeacherTaskConfirmView.vue')
  const textbook = src('modules/academicAffairs/views/AaTextbookConsoleView.vue')
  const booking = src('modules/academicAffairs/components/parallel-a/ResourceBookingWorkspace.vue')
  assert.match(task, /query\?\.taskId/)
  assert.match(textbook, /query\?\.selectionId/)
  assert.match(booking, /query\?\.bookingId/)
})
