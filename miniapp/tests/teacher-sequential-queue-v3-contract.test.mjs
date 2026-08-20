import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('T5 MobileSequentialQueue is windowed and single-object only', () => {
  const component = read('src/components/teacher/MobileSequentialQueue.vue')
  assert.match(component, /WINDOW_RADIUS = 2/)
  assert.match(component, /this\.items\.slice\(start, end\)/)
  assert.match(component, /emits: \['open', 'action', 'next'\]/)
  assert.match(component, /currentItem/)
  assert.match(component, /conflict/)
  assert.match(component, /连续处理已停止/)
  assert.doesNotMatch(component, /Promise\.all/)
  assert.doesNotMatch(component, /itemIds|ids\s*:/)
})

test('T5 leave queue uses canonical single-record commands and reloads truth before advancing', () => {
  const page = read('src/pages/teacher/affairs-leave/index.vue')
  assert.match(page, /MobileSequentialQueue/)
  assert.match(page, /sequentialConflict/)
  assert.match(page, /affairsContractApi\.approveLeave\(x\.id/)
  assert.match(page, /affairsContractApi\.rejectLeave\(x\.id/)
  assert.match(page, /affairsContractApi\.returnLeave\(x\.id/)
  assert.match(page, /return this\.load\(\)\.then\(\(\) => this\.afterSequentialSuccess/)
  // The conflict branch may be expressed directly (`===`) or by a complementary non-conflict
  // guard (`!==`). The production contract is behavioral: 409 never reopens stale input, while
  // a non-conflict failure preserves the typed draft and offers a retry.
  assert.match(page, /if \(n\.kind !== 'conflict'\)/)
  assert.match(page, /if \(retry\) setTimeout\(retry, 0\)/)
  assert.match(page, /this\.sequentialConflict = true/)
  assert.match(page, /return this\.load\(\)\.catch\(\(\) => \{\}\)/)
  assert.doesNotMatch(page, /approveLeave\([^\n]*\[/)
  assert.doesNotMatch(page, /rejectLeave\([^\n]*\[/)
})

test('T5 internship weekly and abnormal queues stop on conflict and never batch ids', () => {
  const page = read('src/pages/teacher/internship-review/index.vue')
  assert.match(page, /MobileSequentialQueue/)
  assert.match(page, /tab === 'weekly'/)
  assert.match(page, /PENDING_REVIEW/)
  assert.match(page, /PENDING_HANDLE/)
  assert.match(page, /teacherApi\.reviewWeekly\(w\.id/)
  assert.match(page, /teacherApi\.handleCheckin\(c\.id/)
  assert.match(page, /return this\.load\(\)\.then\(\(\) => this\.afterSequentialSuccess/)
  assert.match(page, /连续处理已停止并刷新服务器状态/)
  assert.match(page, /this\.sequentialConflict = true/)
  assert.doesNotMatch(page, /reviewWeekly\([^\n]*\[/)
  assert.doesNotMatch(page, /handleCheckin\([^\n]*\[/)
})

test('T5 abnormal queue carries the exact read-snapshot version into the canonical command adapter', () => {
  const api = read('src/services/teacherApi.js')
  const adapter = read('src/services/teacherSequentialV3Api.js')

  assert.match(api, /teacherSequentialV3/)
  assert.match(api, /getWeeklyReports:[\s\S]*teacherSequentialV3\.getInternshipReviewQueue/)
  assert.match(api, /handleCheckin:[\s\S]*teacherSequentialV3\.handleCheckin/)
  assert.doesNotMatch(api, /handleCheckin:[^\n]*real\.handleCheckinReal/)

  assert.match(adapter, /const exceptionVersions = new Map\(\)/)
  assert.match(adapter, /expectedVersion = rememberExceptionVersion\(id, e\.version\)/)
  assert.match(adapter, /exceptionVersions\.get\(key\)/)
  assert.match(adapter, /\/teacher-mobile\/internship\/exceptions\/\$\{encodeURIComponent\(key\)\}\/handle/)
  assert.match(adapter, /data: \{ action, comment: comment \|\| '', expectedVersion \}/)
  assert.match(adapter, /error\.code = 'DATA_CONFLICT'/)
  assert.match(adapter, /exceptionVersions\.delete\(key\)/)
  assert.doesNotMatch(adapter, /localStorage|setStorageSync|Promise\.all|itemIds|exceptionIds/)
})

test('T5 only advances after server reload and cannot auto-advance while conflict is set', () => {
  const leave = read('src/pages/teacher/affairs-leave/index.vue')
  const internship = read('src/pages/teacher/internship-review/index.vue')
  assert.match(leave, /if \(this\.sequentialConflict \|\| this\.acting\) return/)
  assert.match(internship, /if \(!this\.sequentialConflict && !this\.acting/)
  for (const source of [leave, internship]) {
    assert.match(source, /afterSequentialSuccess/)
    assert.match(source, /sequentialIndex/)
  }
})
