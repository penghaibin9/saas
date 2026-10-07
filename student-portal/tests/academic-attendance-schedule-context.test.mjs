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
  assert.match(schedule, /function routeWeek\(\)/)
  assert.match(schedule, /portalApi\.academicSchedule\(requestedWeek\)/)
  assert.match(schedule, /watch\(\(\) => \[route\.query\.lesson, route\.query\.week, route\.query\.attendanceSessionId, route\.query\.from\]/)
  assert.match(schedule, /const selectedLessonDate = computed/)
  assert.match(schedule, /返回考勤记录/)
})

test('attendance links retain the exact owning session id and reject missing or rounded numeric identities', () => {
  const body = attendance.match(/function attendanceScheduleRoute\(row\) \{([\s\S]*?)\n\}/)[1]
  const link = new Function('row', body)
  const sessionId = '9007199254740993123', itemId = '9007199254740993124'
  assert.deepEqual(link({ sessionId, scheduleItemId: itemId, weekNo: 2 }), {
    path: '/academic/schedule', query: { lesson: itemId, attendanceSessionId: sessionId, from: 'attendance', week: '2' }
  })
  assert.equal(link({ scheduleItemId: itemId }), null)
  assert.equal(link({ sessionId: Number(sessionId), scheduleItemId: itemId }), null)
  assert.equal(link({ sessionId, scheduleItemId: Number(itemId) }), null)
})

test('the attendance API preserves existing no-argument calls and encodes the exact string session filter', async () => {
  const source = readFileSync(new URL('../src/services/portalApi.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace('export const portalApi =', 'const portalApi =').replace(/^export default portalApi\s*$/m, '')
  const calls = []
  const api = new Function('request', 'fileSdk', source + '\nreturn portalApi')((url) => { calls.push(url); return Promise.resolve({}) }, {})
  await api.academicAttendance()
  await api.academicAttendance({ session_id: '9007199254740993123' })
  assert.deepEqual(calls, ['/portal/academic/attendance', '/portal/academic/attendance?session_id=9007199254740993123'])
})
