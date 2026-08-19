import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const page = fs.readFileSync(
  path.resolve(here, '../src/modules/academicAffairs/views/AaAttendanceStatsView.vue'),
  'utf8'
)

test('PC attendance statistics expose Chinese provenance labels', () => {
  assert.match(page, /管理员特殊补录/)
  assert.match(page, /sourceScopeLabel/)
  assert.match(page, /sessionTypeLabel/)
  assert.match(page, /sourceLabel/)
  assert.doesNotMatch(page, /\{ key: 'sessionType', title: '类别' \}/)
})

test('ADMIN_SPECIAL is audit-only and cannot trigger normal absence warning scan from PC', () => {
  assert.match(page, /v-if="sessionType !== 'ADMIN_SPECIAL'"/)
  assert.match(page, /if \(this\.sessionType === 'ADMIN_SPECIAL'\) return/)
  assert.match(page, /特殊补录仅用于审计核对，不进入标准课堂旷课预警/)
})
