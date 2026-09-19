import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const root = new URL('../src/views/academic/', import.meta.url)
const attendance = readFileSync(new URL('StudentAcademicReadOnlyView.vue', root), 'utf8')
const schedule = readFileSync(new URL('StudentScheduleView.vue', root), 'utf8')

test('attendance record only links when the API supplied a formal schedule item', () => {
  assert.match(attendance, /v-if="attendanceScheduleRoute\(row\)"/)
  assert.match(attendance, /课位回链未提供/)
  assert.match(attendance, /\^\\d\+\$/)
  assert.match(attendance, /week: String\(week\)/)
  assert.match(attendance, /from: 'attendance'/)
})

test('schedule consumes the linked lesson and authoritative week from route query', () => {
  assert.match(schedule, /function applyRouteContext\(\)/)
  assert.match(schedule, /selectedLessonId\.value = String\(route\.query\.lesson \|\| ''\)/)
  assert.match(schedule, /weekOptions\.value\.includes\(requestedWeek\)/)
  assert.match(schedule, /watch\(\(\) => \[route\.query\.lesson, route\.query\.week\], applyRouteContext/)
  assert.match(schedule, /const selectedLessonDate = computed/)
  assert.match(schedule, /返回考勤记录/)
})
