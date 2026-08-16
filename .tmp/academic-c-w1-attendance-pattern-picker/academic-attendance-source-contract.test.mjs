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

test('ordinary attendance chooses a server-projected formal schedule pattern instead of free slot input', () => {
  assert.match(page, /:range="formalPatternLabels"/)
  assert.match(page, /@change="onPatternPick"/)
  assert.match(page, /选择正式上课节次（必填）/)
  assert.doesNotMatch(page, /type="number"[^>]*v-model="form\.slotNo"/)
  assert.doesNotMatch(page, /placeholder="第几节（必填）"/)
  assert.match(page, /formalPatterns\(\)\s*\{[\s\S]*selectedTask[\s\S]*formalSchedulePatterns/)
  assert.match(page, /formalPatternLabels\(\)\s*\{[\s\S]*第\$\{pattern\.slotNo\}节/)
  assert.match(page, /selectedPattern\(\)\s*\{[\s\S]*patternIndex/)
  assert.match(page, /hasValidSlot\(\)\s*\{[\s\S]*selectedPattern[\s\S]*pattern\.slotNo/)
  assert.match(page, /onPatternPick\(event\)\s*\{[\s\S]*this\.patternIndex[\s\S]*this\.form\.slotNo = String\(pattern\.slotNo\)/)
  assert.match(page, /formalOccurrenceReady/)
  assert.match(page, /formalScheduleIssue/)
  assert.match(page, /:disabled="!form\.teachingTaskId \|\| !form\.sessionDate \|\| !hasValidSlot \|\| creating"/)
  assert.match(page, /slotNo: Number\(this\.form\.slotNo\)/)
})

test('deep-link seed must map to the current task and one current formal pattern', () => {
  assert.match(page, /onLoad\(options = \{\}\)\s*\{[\s\S]*this\.routeSeed = this\.parseOccurrenceSeed\(options\)[\s\S]*this\.loadTasks\(\)/)
  assert.match(page, /parseOccurrenceSeed\(options = \{\}\)/)
  assert.match(page, /const anySeed = Boolean\(taskIdRaw \|\| sessionDate \|\| slotRaw\)/)
  assert.match(page, /Number\.isInteger\(taskId\)[\s\S]*Number\.isInteger\(slotNo\)/)
  assert.match(page, /this\.taskOptions\.findIndex\(\(task\) => String\(task\.teachingTaskId\) === seed\.teachingTaskId\)/)
  assert.match(page, /const patternIndex = this\.formalPatterns\.findIndex\(\(pattern\) => Number\(pattern\.slotNo\) === Number\(seed\.slotNo\)\)/)
  assert.match(page, /if \(patternIndex < 0\)[\s\S]*this\.taskSelectionInvalid = true[\s\S]*toast\('该正式课次节次已不在当前发布课表中'/)
  assert.match(page, /this\.patternIndex = patternIndex[\s\S]*this\.form\.sessionDate = seed\.sessionDate[\s\S]*this\.form\.slotNo = String\(this\.formalPatterns\[patternIndex\]\.slotNo\)/)
  assert.match(page, /if \(!seed\)\s*\{[\s\S]*this\.taskIndex = 0[\s\S]*this\.applyTask\(this\.taskOptions\[0\]\)[\s\S]*return/)
  assert.doesNotMatch(page, /if \(!seed\)\s*\{[\s\S]{0,160}this\.applyOccurrenceSeed\(\)/)
  assert.match(page, /loadTasks\(\)\s*\{[\s\S]*this\.applyOccurrenceSeed\(\)[\s\S]*\.catch/)
  assert.match(page, /onTaskPick\(event\)\s*\{[\s\S]*this\.routeSeed = null[\s\S]*this\.taskSelectionInvalid = false/)
})

test('ADMIN_SPECIAL provenance remains visible and unavailable as an ordinary teacher creation choice', () => {
  assert.match(page, /session\.sourceType === 'ADMIN_SPECIAL'/)
  assert.match(page, /active\.sourceType === 'ADMIN_SPECIAL'/)
  assert.match(page, /管理员特殊补录/)
  assert.match(page, /普通教师端不会提供此创建入口/)
  assert.match(page, /sessionTypes: \['常规', '实训', '晚自习', '其他'\]/)
  assert.doesNotMatch(page, /sessionTypes:\s*\[[^\]]*ADMIN_SPECIAL/)
})
