import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const page = fs.readFileSync(
  path.resolve(here, '../src/pages/teacher/academic-affairs/index.vue'),
  'utf8'
)

test('Teacher Today consumes server-projected todayItems instead of recomputing weekday and parity in the page', () => {
  assert.match(page, /todayItems:\s*\[\]/)
  assert.match(page, /this\.todayItems = \(results\[0\]\.value && results\[0\]\.value\.todayItems\) \|\| \[\]/)
  assert.match(page, /todayCourses\(\)\s*\{[\s\S]*this\.todayItems/)
  assert.doesNotMatch(page, /new Date\(\)\.getDay\(\)/)
  assert.doesNotMatch(page, /function activeInWeek\(/)
})

test('each executable Teacher Today occurrence opens its exact attendance deep-link while full schedule remains separate', () => {
  assert.match(page, /@click="openTodayCourse\(item\)"/)
  assert.match(page, /item\.attendanceRoute/)
  assert.match(page, /return go\(item\.attendanceRoute\)/)
  assert.match(page, /完整课表 ›/)
  assert.match(page, /@click="go\('\/pages\/teacher\/my-schedule\/index'\)"/)
  assert.match(page, /attendanceExecutable \? '去点名 ›' : '待任务确认'/)
})

test('non-executable formal class remains visible but cannot silently fall through to attendance', () => {
  assert.match(page, /item\.attendanceBlockReason/)
  assert.match(page, /toast\(item\.attendanceBlockReason\)/)
  assert.match(page, /'is-disabled': !item\.attendanceExecutable/)
})

test('calendar no-class states are explicit and never fall back to another course', () => {
  assert.match(page, /calendarSource === 'HOLIDAY'/)
  assert.match(page, /calendarSource === 'SWAP_SOURCE'/)
  assert.match(page, /calendarSource === 'OUT_OF_TERM'/)
  assert.match(page, /没有正式课堂点名任务/)
  assert.match(page, /正式课程已按调休安排迁移/)
})
