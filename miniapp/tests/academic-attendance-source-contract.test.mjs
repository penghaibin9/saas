import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const page = fs.readFileSync(
  path.resolve(here, '../src/pages/teacher/academic-affairs/attendance.vue'),
  'utf8'
)

test('ordinary teacher attendance creation requires a complete formal occurrence coordinate', () => {
  assert.match(page, /:disabled="!form\.teachingTaskId \|\| !form\.sessionDate \|\| !hasValidSlot \|\| creating"/)
  assert.match(page, /placeholder="第几节（必填）"/)
  assert.doesNotMatch(page, /第几节（选填）/)
  assert.match(page, /hasValidSlot\(\)\s*\{[\s\S]*Number\.isInteger\(slot\)[\s\S]*slot > 0/)
  assert.match(page, /if \(this\.creating \|\| !this\.form\.teachingTaskId \|\| !this\.form\.sessionDate \|\| !this\.hasValidSlot\) return/)
  assert.match(page, /slotNo: Number\(this\.form\.slotNo\)/)
  assert.doesNotMatch(page, /slotNo: this\.form\.slotNo \? Number\(this\.form\.slotNo\) : undefined/)
  assert.match(page, /sessionTypes: \['常规', '实训', '晚自习', '其他'\]/)
  assert.doesNotMatch(page, /sessionTypes:\s*\[[^\]]*ADMIN_SPECIAL/)
})

test('exact occurrence deep-link never silently falls back to the first teaching task', () => {
  assert.match(page, /onLoad\(options = \{\}\)\s*\{[\s\S]*this\.routeSeed = this\.parseOccurrenceSeed\(options\)[\s\S]*this\.loadTasks\(\)/)
  assert.match(page, /parseOccurrenceSeed\(options = \{\}\)/)
  assert.match(page, /const anySeed = Boolean\(taskIdRaw \|\| sessionDate \|\| slotRaw\)/)
  assert.match(page, /Number\.isInteger\(taskId\)[\s\S]*Number\.isInteger\(slotNo\)/)
  assert.match(page, /\^\\d\{4\}-\\d\{2\}-\\d\{2\}\$/)
  assert.match(page, /this\.taskOptions\.findIndex\(\(task\) => String\(task\.teachingTaskId\) === seed\.teachingTaskId\)/)
  assert.match(page, /this\.taskSelectionInvalid = true[\s\S]*this\.applyTask\(null\)[\s\S]*toast\('该正式课次不在本人当前可点名教学任务范围内'/)
  assert.match(page, /this\.taskSelectionInvalid = false[\s\S]*this\.taskIndex = index[\s\S]*this\.form\.sessionDate = seed\.sessionDate[\s\S]*this\.form\.slotNo = seed\.slotNo/)
  assert.match(page, /onTaskPick\(event\)\s*\{[\s\S]*this\.routeSeed = null[\s\S]*this\.taskSelectionInvalid = false/)
  assert.doesNotMatch(page, /onLoad\(\) \{ this\.load\(\); this\.loadTasks\(\) \}/)
})

test('ADMIN_SPECIAL provenance is visible but never exposed as a teacher creation option', () => {
  assert.match(page, /session\.sourceType === 'ADMIN_SPECIAL'/)
  assert.match(page, /active\.sourceType === 'ADMIN_SPECIAL'/)
  assert.match(page, /管理员特殊补录/)
  assert.match(page, /普通教师端不会提供此创建入口/)
})
