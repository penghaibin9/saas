import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const selection = fs.readFileSync(path.join(root, 'src/pages/student/academic-affairs/selection.vue'), 'utf8')
const schedule = fs.readFileSync(path.join(root, 'src/pages/student/academic-affairs/schedule.vue'), 'utf8')
const academicHome = fs.readFileSync(path.join(root, 'src/pages/student/academic-affairs/index.vue'), 'utf8')
const studentHome = fs.readFileSync(path.join(root, 'src/pages/student/home/index.vue'), 'utf8')
const teacherSchedule = fs.readFileSync(path.join(root, 'src/pages/teacher/my-schedule/index.vue'), 'utf8')

test('student miniapp selection shows published meeting context and a clear success handoff', () => {
  assert.match(selection, /course\.scheduleItems/)
  assert.match(selection, /时间待排 · 以正式课表为准/)
  assert.match(selection, /名单锁定且课表正式发布后会进入我的课表/)
  assert.match(selection, /pages\/student\/academic-affairs\/schedule/)
  assert.match(selection, /\['SELECTED', 'LOCKED'\]/)
})

test('student miniapp keeps business blockers readable instead of collapsing them into generic load failure', () => {
  assert.match(selection, /Promise\.allSettled/)
  assert.match(selection, /normalizeError\(reason\)\.text/)
  assert.match(selection, /reason\.decisionTrace \|\| null/)
  assert.match(selection, /businessError[\s\S]*\? 'ready'/)
})

test('student miniapp consumes backend todayItems and refreshes whenever shown', () => {
  assert.match(schedule, /this\.todayItems = data\.todayItems \|\| \[\]/)
  assert.match(schedule, /onShow\(\) \{ this\.load\(\) \}/)
  assert.doesNotMatch(schedule, /new Date\(\)\.getDay\(\)/)
  assert.match(schedule, /calendarSource === 'HOLIDAY'/)
  assert.match(schedule, /calendarSource === 'SWAP_SOURCE'/)
  assert.match(schedule, /calendarSource === 'OUT_OF_TERM'/)
})

test('student miniapp keeps schedule and selection reachable before orientation completes', () => {
  assert.match(studentHome, /查看今天上什么课/)
  assert.match(studentHome, /pages\/student\/academic-affairs\/schedule/)
  assert.match(studentHome, /pages\/student\/academic-affairs\/selection/)
  assert.match(studentHome, /课表与选课始终可查看/)
  assert.doesNotMatch(studentHome, /完成报到后，课表、成绩/)
})

test('student academic home consumes the same server-projected Today truth', () => {
  assert.match(academicHome, /this\.todayItems = schedule\.todayItems \|\| \[\]/)
  assert.match(academicHome, /return this\.todayItems/)
  assert.match(academicHome, /calendarSource === 'OUT_OF_TERM'/)
  assert.doesNotMatch(academicHome, /new Date\(\)\.getDay\(\)/)
})

test('teacher miniapp full timetable leads with the same server-projected Today truth', () => {
  assert.match(teacherSchedule, /this\.todayItems = \(data && data\.todayItems\) \|\| \[\]/)
  assert.match(teacherSchedule, /onShow\(\) \{ this\.load\(\) \}/)
  assert.match(teacherSchedule, /item\.attendanceRoute/)
  assert.match(teacherSchedule, /go\(item\.attendanceRoute\)/)
  assert.doesNotMatch(teacherSchedule, /new Date\(\)\.getDay\(\)/)
})
