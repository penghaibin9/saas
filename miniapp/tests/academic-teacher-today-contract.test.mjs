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

test('Teacher Today refreshes server truth every time the cached page becomes visible again', () => {
  assert.match(page, /onLoad\(\)\s*\{[\s\S]*statusBarHeight[\s\S]*\}\s*,\s*onShow\(\)\s*\{\s*this\.load\(\)\s*\}/)
  const onLoad = page.match(/onLoad\(\)\s*\{([\s\S]*?)\n\s*\},\n\s*onShow\(\)/)?.[1] || ''
  assert.doesNotMatch(onLoad, /this\.load\(\)/)
})

test('Teacher Today action label and route are server-projected and existing sessions open exactly', () => {
  assert.match(page, /@click="openTodayCourse\(item\)"/)
  assert.match(page, /item\.attendanceRoute/)
  assert.match(page, /return go\(item\.attendanceRoute\)/)
  assert.match(page, /item\.attendanceActionLabel/)
  assert.match(page, /item\.attendanceRoute \? ' ›' : ''/)
  assert.match(page, /'is-disabled': !item\.attendanceRoute/)
  assert.doesNotMatch(page, /item\.attendanceExecutable \? '去点名 ›' : '待任务确认'/)
  assert.match(page, /完整课表 ›/)
  assert.match(page, /@click="go\('\/pages\/teacher\/my-schedule\/index'\)"/)
})

test('blocked Teacher Today occurrence explains the server reason and never invents a write route', () => {
  assert.match(page, /item\.attendanceBlockReason/)
  assert.match(page, /toast\(item\.attendanceBlockReason\)/)
  assert.match(page, /item\.attendanceActionLabel \|\| \(item\.attendanceRoute \? '去点名' : '暂不可操作'\)/)
})

test('APPLIED schedule change evidence is visible without inventing non-effective change states', () => {
  assert.match(page, /item\.changeType === 'ADJUST'/)
  assert.match(page, />已调课<\/text>/)
  assert.match(page, /item\.changeType === 'MAKEUP'/)
  assert.match(page, />补课<\/text>/)
  assert.doesNotMatch(page, /SUBMITTED[^\n]*已调课/)
  assert.doesNotMatch(page, /APPROVED[^\n]*已调课/)
})

test('calendar no-class states are explicit and never fall back to another course', () => {
  assert.match(page, /calendarSource === 'HOLIDAY'/)
  assert.match(page, /calendarSource === 'SWAP_SOURCE'/)
  assert.match(page, /calendarSource === 'OUT_OF_TERM'/)
  assert.match(page, /没有正式课堂点名任务/)
  assert.match(page, /正式课程已按调休安排迁移/)
})