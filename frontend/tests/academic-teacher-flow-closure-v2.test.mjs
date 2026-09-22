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
  assert.match(source, />考勤<\/AppButton>/)
  assert.match(source, />调课<\/AppButton>/)
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


test('teacher V3 P0 keeps schedule changes occurrence-first', () => {
  const schedule = src('modules/academicAffairs/views/AaTeacherScheduleView.vue')
  const apply = src('modules/academicAffairs/views/AaScheduleChangeApplyView.vue')
  assert.match(schedule, /occurrenceWeek: String\(this\.week \|\| this\.selectedItem\?\.weekNo \|\| ''\)/)
  assert.doesNotMatch(schedule, /this\.week \|\| this\.todayWeek \|\| this\.selectedItem/)
  assert.match(apply, /调整范围/)
  assert.match(apply, /只调整一次课/)
  assert.match(apply, /lockedOccurrenceWeek/)
  assert.match(apply, /this\.form\.targetStartWeek = singleWeek/)
  assert.match(apply, /this\.form\.targetEndWeek = singleWeek/)
  assert.match(apply, /请选择“只调整一次课”或“调整周期课表”/)
})

test('teacher V3 P0 grade entry is formal-roster first', () => {
  const grade = src('modules/academicAffairs/views/AaGradeEntryView.vue')
  assert.match(grade, /v-if="!isAcademicTeacher" v-model="candidateStudentId"/)
  assert.match(grade, /任课教师只按正式教学班名单录入/)
  assert.match(grade, /await this\.loadRoster\(\{ quiet: true \}\)/)
})

test('teacher V3 P0 attendance cannot submit with unmarked students', () => {
  const attendance = src('modules/academicAffairs/views/AaAttendanceStatsView.vue')
  assert.match(attendance, /unmarkedCount > 0/)
  assert.match(attendance, /请全部点名后再提交/)
})

test('teacher V3 P0 schedule ledger removes teacher review dead-end', () => {
  const ledger = src('modules/academicAffairs/views/AaScheduleChangeLedgerView.vue')
  assert.match(ledger, /v-if="canReview".*审批工作台/)
  assert.match(ledger, /从个人课表选择课程/)
  assert.match(ledger, /academicAffairs\.scheduleChange\.academicReview/)
  assert.match(ledger, /academicAffairs\.scheduleChange\.collegeReview/)
})


test('teacher V3 Today preserves designed five-card layout and splits todo state inside the same card', () => {
  const source = src('modules/academicAffairs/views/AaTeacherTodayView.vue')
  for (const label of ['今日课程', '待确认任务', '待录成绩', '调停课审核中', '教材/预约']) {
    assert.match(source, new RegExp(label))
  }
  assert.match(source, /title="我的待办"/)
  assert.match(source, /待我处理/)
  assert.match(source, /办理中/)
  assert.match(source, /workTab/)
  assert.match(source, /firstPath/)
})

test('teacher V3 grade landing is current-term and exact-teaching-task aware', () => {
  const source = src('modules/academicAffairs/views/AaGradeEntryView.vue')
  assert.match(source, /ensureCurrentTerm/)
  assert.match(source, /params\.termId = this\.currentTermId/)
  assert.match(source, /prepareCreateFromTeachingTask/)
  assert.match(source, /mine: true, termId: this\.currentTermId, taskId: id/)
  assert.match(source, /row\.status \|\| ''\)\.toUpperCase\(\) !== 'READY'/)
  assert.match(source, /showHistory/)
})

test('teacher V3 textbook landing defaults current term and revalidates exact task before opening drawer', () => {
  const source = src('modules/academicAffairs/views/AaTextbookConsoleView.vue')
  assert.match(source, /历史选用记录/)
  assert.match(source, /termId: this\.currentTermId/)
  assert.match(source, /openSelectionFromRoute/)
  assert.match(source, /mine: true, termId: this\.currentTermId, taskId/)
  assert.match(source, /this\.selectionForm\.taskId = taskId/)
})


test('teacher V3 resource booking keeps one page but separates availability from cross-date my ledger', () => {
  const source = src('modules/academicAffairs/components/parallel-a/ResourceBookingWorkspace.vue')
  assert.match(source, /找空闲并预约/)
  assert.match(source, /我的预约/)
  assert.match(source, /workspaceTab === 'mine'/)
  assert.match(source, /date: browseResources \? date : undefined/)
  assert.match(source, /teacherBookingNext/)
  assert.match(source, /等待资源管理员审核/)
  assert.match(source, /已通过，可按预约时间使用/)
})


test('teacher V3 schedule conflict preflight keeps the requested change type', () => {
  const source = src('modules/academicAffairs/views/AaScheduleChangeApplyView.vue')
  assert.match(source, /changeType: this\.form\.changeType/)
  assert.match(source, /this\.form\.changeType === 'MAKEUP'/)
  assert.match(source, /endWeek === startWeek/)
})

test('teacher V3 booking route can clear an exact booking focus back to my full ledger', () => {
  const source = src('modules/academicAffairs/components/parallel-a/ResourceBookingWorkspace.vue')
  assert.match(source, /if \(this\.bookingId\) query\.bookingId = this\.bookingId; else delete query\.bookingId/)
})


test('teacher V3 completed flows return to the existing Today page instead of dead-ending', () => {
  const task = src('modules/academicAffairs/views/AaTeacherTaskConfirmView.vue')
  const change = src('modules/academicAffairs/views/AaScheduleChangeApplyView.vue')
  const attendance = src('modules/academicAffairs/views/AaAttendanceStatsView.vue')
  const grade = src('modules/academicAffairs/views/AaGradeEntryView.vue')
  const textbook = src('modules/academicAffairs/views/AaTextbookConsoleView.vue')
  const booking = src('modules/academicAffairs/components/parallel-a/ResourceBookingWorkspace.vue')
  for (const source of [task, change, attendance, grade, textbook, booking]) {
    assert.match(source, /\/admin\/academic-affairs\/teacher\/today/)
  }
  assert.match(task, /本次办理已形成正式状态/)
  assert.match(attendance, /本场考勤已提交/)
  assert.match(grade, /返回今日教学/)
  assert.match(textbook, /教材选用已提交审核/)
  assert.match(booking, /返回今日教学/)
})


test('teacher V3 grade setup enters the real recording workspace immediately after creation', () => {
  const source = src('modules/academicAffairs/views/AaGradeEntryView.vue')
  assert.match(source, /const gradeTaskId = String\(res\.data\?\.gradeTaskId \|\| ''\)/)
  assert.match(source, /await this\.openTask\(\{ gradeTaskId \}\)/)
  assert.match(source, /正在载入正式名单/)
  assert.doesNotMatch(source, /this\.task = res\.data; this\.prepareDeadlineForm\(\); toast\.success\('任务已创建，开始录入'\)/)
})

test('teacher V3 textbook receipt is cleared when identity changes', () => {
  const source = src('modules/academicAffairs/views/AaTextbookConsoleView.vue')
  assert.match(source, /this\.selectionReceipt = null/)
})


test('teacher V3 textbook flow uses honest draft then submit semantics', () => {
  const textbook = src('modules/academicAffairs/views/AaTextbookConsoleView.vue')
  const today = src('modules/academicAffairs/views/AaTeacherTodayView.vue')
  assert.match(textbook, /保存申报草稿/)
  assert.match(textbook, /申报草稿已保存，请确认后提交审核/)
  assert.match(textbook, /selectionDraftReceipt/)
  assert.match(textbook, /提交审核/)
  assert.doesNotMatch(today, /TEXTBOOK_SETUP/)
})
