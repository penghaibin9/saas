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

test('ordinary teacher attendance creation stays TeachingTask-first', () => {
  assert.match(page, /:disabled="!form\.teachingTaskId \|\| !form\.sessionDate \|\| creating"/)
  assert.match(page, /sessionTypes: \['常规', '实训', '晚自习', '其他'\]/)
  assert.doesNotMatch(page, /sessionTypes:\s*\[[^\]]*ADMIN_SPECIAL/)
  assert.match(page, /teachingTaskId: Number\(this\.form\.teachingTaskId\)/)
})

test('ADMIN_SPECIAL provenance is visible but never exposed as a teacher creation option', () => {
  assert.match(page, /session\.sourceType === 'ADMIN_SPECIAL'/)
  assert.match(page, /active\.sourceType === 'ADMIN_SPECIAL'/)
  assert.match(page, /管理员特殊补录/)
  assert.match(page, /普通教师端不会提供此创建入口/)
})
