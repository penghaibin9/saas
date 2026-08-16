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
  assert.match(page, /hasValidSlot\(\)\s*\{[\s\S]*selectedPattern[\s\S]*scheduleItemId = Number\(this\.form\.scheduleItemId\)[\s\S]*scheduleItemId > 0[\s\S]*String\(pattern\.scheduleItemId \|\| ''\) === String\(this\.form\.scheduleItemId \|\| ''\)/)
  assert.match(page, /onPatternPick\(event\)\s*\{[\s\S]*this\.patternIndex[\s\S]*this\.form\.slotNo = pattern \? String\(pattern\.slotNo\) : ''[\s\S]*this\.form\.scheduleItemId = pattern \? String\(pattern\.scheduleItemId \|\| ''\) : ''/)
  assert.match(page, /formalOccurrenceReady/)
  assert.match(page, /formalScheduleIssue/)
  assert.match(page, /:disabled="!form\.teachingTaskId \|\| !form\.sessionDate \|\| !hasValidSlot \|\| creating"/)
})

test('create submits the selected schedule item as an optimistic occurrence identity', () => {
  assert.match(page, /form: \{[^\n]*scheduleItemId: ''/)
  assert.match(page, /scheduleItemId: this\.form\.scheduleItemId \|\| undefined/)
  assert.match(page, /this\.form\.scheduleItemId = ''/)
  assert.match(page, /this\.form\.scheduleItemId = String\(this\.formalPatterns\[patternIndex\]\.scheduleItemId \|\| ''\)/)
  assert.match(page, /slotNo: Number\(this\.form\.slotNo\)/)
})

test('deep-link seed maps to the exact current formal pattern and ambiguous slot-only links fail closed', () => {
  assert.match(page, /onLoad\(options = \{\}\)\s*\{[\s\S]*this\.routeSeed = this\.parseOccurrenceSeed\(options\)[\s\S]*this\.loadTasks\(\)/)
  assert.match(page, /const scheduleItemId = String\(options\.scheduleItemId \|\| ''\)\.trim\(\)/)
  assert.match(page, /const anySeed = Boolean\(taskIdRaw \|\| sessionDate \|\| slotRaw \|\| scheduleItemId\)/)
  assert.match(page, /if \(seed\.scheduleItemId\)[\s\S]*String\(this\.formalPatterns\[candidateIndex\]\.scheduleItemId \|\| ''\) === seed\.scheduleItemId/)
  assert.match(page, /else if \(matchingPatternIndexes\.length === 1\)/)
  assert.match(page, /const ambiguous = !seed\.scheduleItemId && matchingPatternIndexes\.length > 1/)
  assert.match(page, /该节次对应多个正式课表项，请从教师今日课次重新进入/)
  assert.match(page, /该正式课次已不在当前发布课表中/)
  assert.match(page, /this\.patternIndex = patternIndex[\s\S]*this\.form\.scheduleItemId = String\(this\.formalPatterns\[patternIndex\]\.scheduleItemId \|\| ''\)/)
  assert.match(page, /if \(!seed\)\s*\{[\s\S]*this\.taskIndex = 0[\s\S]*this\.applyTask\(this\.taskOptions\[0\]\)[\s\S]*return/)
  assert.doesNotMatch(page, /if \(!seed\)\s*\{[\s\S]{0,160}this\.applyOccurrenceSeed\(\)/)
})

test('ADMIN_SPECIAL provenance remains visible and unavailable as an ordinary teacher creation choice', () => {
  assert.match(page, /session\.sourceType === 'ADMIN_SPECIAL'/)
  assert.match(page, /active\.sourceType === 'ADMIN_SPECIAL'/)
  assert.match(page, /管理员特殊补录/)
  assert.match(page, /普通教师端不会提供此创建入口/)
  assert.match(page, /sessionTypes: \['常规', '实训', '晚自习', '其他'\]/)
  assert.doesNotMatch(page, /sessionTypes:\s*\[[^\]]*ADMIN_SPECIAL/)
})
