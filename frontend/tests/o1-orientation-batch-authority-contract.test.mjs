import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8')
const view = read('../src/views/admin/orientation/OrientationStudentListView.vue')
const api = read('../src/modules/orientation/api/orientation.api.js')
const meta = read('../src/modules/orientation/constants/orientation.meta.js')
const backendTemplate = read('../../backend/app/api/v1/import_export.py')
const backendImport = read('../../backend/app/services/domain_import_service.py')
const backendExport = read('../../backend/app/services/domain_export_service.py')
const migration = read('../../backend/alembic/versions/20260901_orientation_batch_o1.py')

test('O1 student ledger selects a real batch for list, create and export', () => {
  assert.match(view, /key: 'batchId', label: '迎新批次'/)
  assert.match(view, /this\.batches\.find\(\(row\) => row\.status !== 'CLOSED'\)/)
  assert.match(view, /batchId: this\.filters\.batchId/)
  assert.match(view, /请先在筛选条件中选择一个迎新批次/)
  assert.match(api, /request\('\/orientation\/batches', \{ params: \{ status: 'ACTIVE', page: 1, pageSize: 1 \} \}\)/)
  assert.match(api, /if \(!batchId\) throw new Error\('当前没有进行中的迎新批次，无法生成批次台账'/)
  assert.match(api, /body: \{ purpose, batchId, reportType \}/)
})

test('O1 import template exposes the full code-based authority contract', () => {
  for (const key of [
    'batchNo', 'admissionNo', 'candidateNo', 'name', 'gender', 'idCard', 'phone',
    'collegeCode', 'majorCode', 'classCode', 'grade', 'origin', 'admissionType'
  ]) {
    assert.ok(meta.includes(`key: '${key}'`), `${key} must remain visible in the UI template contract`)
  }
  assert.match(backendTemplate, /"迎新批次编号", "录取编号", "候选人编号", "姓名"/)
  assert.match(backendImport, /classes\[\(int\(row\.major_id\), str\(row\.class_code\)\.strip\(\)\)\]/)
  assert.doesNotMatch(backendImport, /class_name\s*==|major_name\s*==|college_name\s*==/)
})

test('O1 migration and export keep one batch-scoped stable authority', () => {
  assert.match(migration, /down_revision = "20260831_iam_alias_backfill"/)
  assert.match(migration, /new_column_name="class_ref_legacy"/)
  assert.match(migration, /CLASS_CODE_AMBIGUOUS/)
  assert.match(migration, /identity_status/)
  assert.match(backendExport, /batch_id=orientation_batch_id/)
  assert.match(backendExport, /迎新导出必须指定 batchId，禁止跨批次导出全历史/)
})
