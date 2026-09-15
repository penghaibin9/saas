import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const selection = fs.readFileSync(path.join(root, 'src/pages/student/academic-affairs/selection.vue'), 'utf8')
const schedule = fs.readFileSync(path.join(root, 'src/pages/student/academic-affairs/schedule.vue'), 'utf8')
const status = fs.readFileSync(path.join(root, 'src/pages/student/academic-affairs/status.vue'), 'utf8')
const registration = fs.readFileSync(path.join(root, 'src/pages/student/academic-affairs/registration.vue'), 'utf8')
const academicHome = fs.readFileSync(path.join(root, 'src/pages/student/academic-affairs/index.vue'), 'utf8')
const studentHome = fs.readFileSync(path.join(root, 'src/pages/student/home/index.vue'), 'utf8')
const teacherSchedule = fs.readFileSync(path.join(root, 'src/pages/teacher/my-schedule/index.vue'), 'utf8')

test('student miniapp selection distinguishes published meeting context and authoritative outcomes', () => {
  assert.match(selection, /course && course\.scheduleItems/)
  assert.match(selection, /时间待排 · 以正式课表为准/)
  assert.match(selection, /查看正式课表/)
  assert.match(selection, /pages\/student\/academic-affairs\/schedule/)
  assert.match(selection, /\['SELECTED', 'LOCKED'\]/)
  assert.match(selection, /已报名待抽签/)
  assert.match(selection, /结果待核实/)
})

test('student miniapp keeps course and personal-record failures independent and readable', () => {
  assert.match(selection, /Promise\.allSettled/)
  assert.match(selection, /consumeReadError\('courses'/)
  assert.match(selection, /consumeReadError\('records'/)
  assert.match(selection, /normalizeError\(reason\)/)
  assert.match(selection, /reason\.decisionTrace/)
  assert.match(selection, /courseState/)
  assert.match(selection, /recordsState/)
})

test('student miniapp consumes backend todayItems and refreshes whenever shown', () => {
  assert.match(schedule, /this\.todayItems = data\.todayItems \|\| \[\]/)
  assert.match(schedule, /onShow\(\) \{ this\.load\(\) \}/)
  assert.doesNotMatch(schedule, /new Date\(\)\.getDay\(\)/)
  assert.match(schedule, /calendarSource === 'HOLIDAY'/)
  assert.match(schedule, /calendarSource === 'SWAP_SOURCE'/)
  assert.match(schedule, /calendarSource === 'OUT_OF_TERM'/)
})

test('student schedule carries the formal task identity into attendance detail', () => {
  assert.match(schedule, /teachingTaskId=\$\{encodeURIComponent\(String\(item\.taskId\)\)\}/)
  assert.ok(schedule.includes("if (/^[1-9]\\d*$/.test(String(item && item.taskId || '')))"))
})

test('student miniapp keeps schedule and selection reachable before orientation completes', () => {
  assert.match(studentHome, /查看课表/)
  assert.match(studentHome, /pages\/student\/academic-affairs\/schedule/)
  assert.match(studentHome, /pages\/student\/academic-affairs\/selection/)
  // 新生保留真实入口，但不能文案承诺绕过学校授权或办理条件。
  assert.match(studentHome, /<HomeQuickServices/)
  assert.match(fs.readFileSync(path.join(root, 'src/pages/student/home/HomeQuickServices.vue'), 'utf8'), /全部服务/)
  assert.doesNotMatch(studentHome, /将自动解锁/)
  assert.doesNotMatch(studentHome, /完成报到后，课表、成绩/)
})

test('student academic home consumes the same server-projected Today truth', () => {
  assert.match(academicHome, /this\.todayItems = \(schedule\.todayItems \|\| \[\]\)\.map/)
  assert.match(academicHome, /return this\.todayItems/)
  assert.match(academicHome, /calendarSource === 'OUT_OF_TERM'/)
  assert.doesNotMatch(academicHome, /new Date\(\)\.getDay\(\)/)
})

test('student academic home keeps its secondary evaluation read bounded', () => {
  assert.match(academicHome, /getMyEvaluationTasks\(\{ page: 1, pageSize: 20 \}\)/)
  assert.doesNotMatch(academicHome, /studentApi\.getMyEvaluationTasks\(\)(?:,|\))/)
})

test('student status-change candidates use server paging instead of an all-school target map', () => {
  assert.match(status, /getTransferOptions\(\{ \.\.\.params, target, page, pageSize: TRANSFER_OPTION_PAGE_SIZE \}\)/)
  assert.match(status, /loadOptionPage\('major', 'major'/)
  assert.match(status, /loadOptionPage\('targetClass', 'class'/)
  assert.match(status, /majorId: selectedMajorId/)
  assert.doesNotMatch(status, /majorClasses/)
  assert.doesNotMatch(status, /getTransferOptions\(\)(?:,|\))/)
})

test('student registration reads server pages and uses the server-wide actionable total on home', () => {
  assert.match(registration, /getMyRegistration\(\{ page, pageSize: PAGE_SIZE, batchId: this\.targetId \|\| undefined \}\)/)
  assert.match(registration, /注册批次分页信息无法核对/)
  assert.match(registration, /changePage\(page\) \{ return this\.load\(page\) \}/)
  assert.doesNotMatch(registration, /studentApi\.getMyRegistration\(\)(?:,|\))/)
  assert.match(academicHome, /getMyRegistration\(\{ page: 1, pageSize: 20 \}\)/)
  assert.match(academicHome, /registrationPayload\?\.actionableTotal/)
  assert.match(academicHome, /registrationPayload\?\.nextActionBatchId/)
})

test('teacher miniapp full timetable leads with the same server-projected Today truth', () => {
  assert.match(teacherSchedule, /this\.todayItems = \(data && data\.todayItems\) \|\| \[\]/)
  assert.match(teacherSchedule, /onShow\(\) \{ this\.load\(\) \}/)
  assert.match(teacherSchedule, /item\.attendanceRoute/)
  assert.match(teacherSchedule, /go\(item\.attendanceRoute\)/)
  assert.doesNotMatch(teacherSchedule, /new Date\(\)\.getDay\(\)/)
})
