import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'

const view = readFileSync(new URL('../src/modules/graduation/views/GraduationRiskArchiveView.vue', import.meta.url), 'utf8')

test('U7 archive missing-item links preserve exact student and batch/source context', () => {
  assert.match(view, /name:\s*'graduation-student-detail'/)
  assert.match(view, /params:\s*\{ id: String\(sid\) \}/)
  assert.match(view, /source:\s*'archive'/)
  assert.match(view, /batchId:\s*String\(this\.batchStore\.selectedBatchId\)/)
  assert.match(view, /name\.includes\('任务书'\).*tab = 'taskbook'/s)
  assert.match(view, /name\.includes\('开题'\).*tab = 'proposals'/s)
  assert.match(view, /name\.includes\('中期'\).*tab = 'midterm'/s)
  assert.match(view, /name\.includes\('查重'\).*tab = 'plagiarisms'/s)
  assert.match(view, /name\.includes\('成果'\).*tab = 'finals'/s)

  // The old broad-workbench jumps lost gdStudentId and could reopen the wrong row.
  for (const old of [
    '/admin/graduation/process?panel=taskbook',
    '/admin/graduation/process?panel=midterm',
    '/admin/graduation/defense-grade?panel=review',
    '/admin/graduation/finals'
  ]) assert.ok(!view.includes(old), `stale broad deep-link remains: ${old}`)
})

test('U7 dirty archive rows are visibly read-only and preview reasons are human-readable', () => {
  assert.ok(view.includes("selectedArchive.dataAnomaly ? '查看学生档案 →' : '去补齐 →'"))
  assert.ok(view.includes('历史主档异常，当前归档记录仅允许只读查看'))
  assert.ok(view.includes("dirty_data: '历史主档异常（只读）'"))
})
