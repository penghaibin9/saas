import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8')

test('archive workbench runs server preflight and shows durable receipts before writes', () => {
  const view = read('src/modules/internship/views/ArchiveView.vue')
  const api = read('src/modules/internship/api/archive.api.js')
  assert.match(view, /ActionReceipt/)
  assert.match(view, /archiveApi\.preflight\(id\)/)
  assert.ok(view.indexOf('archiveApi.preflight(id)') < view.indexOf('archiveApi.archive(p.id'))
  assert.match(view, /missingActions/)
  assert.match(view, /goFix\(m\)/)
  assert.match(view, /force: false/)
  assert.doesNotMatch(view, /force:\s*!p\.complete/)
  assert.match(api, /\/preflight/)
})

test('archive recovery uses the scoped package endpoint and never blindly replays unknown writes', () => {
  const view = read('src/modules/internship/views/ArchiveView.vue')
  const api = read('src/modules/internship/api/archive.api.js')
  assert.match(api, /archive-packages\/\$\{packageId\}\/restore-check/)
  assert.match(api, /archive-packages\/\$\{encodeURIComponent\(packageId\)\}\/download/)
  assert.match(view, /archiveApi\.verifyRestore/)
  assert.match(view, /行数与哈希一致/)
  assert.match(view, /请勿盲目重复提交/)
  assert.match(view, /await this\.openDetailById\(p\.id\)/)
  assert.doesNotMatch(view, /downloadAttachment\(fileId/)
})

test('technical FileVersion and Manifest evidence is collapsed by default', () => {
  const view = read('src/modules/internship/views/InternshipMaterialCenterView.vue')
  assert.match(view, /<details class="technical-evidence">/)
  assert.match(view, /展开 FileVersion \/ Manifest 技术证据/)
  assert.match(view, /当前安全版本/)
  assert.doesNotMatch(view, /当前 v\{\{ activePreviewFile\.versionNo \}\} · FileVersion/)
})

test('employment handoff is exact and names the published-result authority', () => {
  const archive = read('src/modules/internship/views/ArchiveView.vue')
  const api = read('src/modules/internship/api/archive.api.js')
  const employment = read('src/views/admin/employment/EmploymentStudentListView.vue')
  const nav = read('src/config/navPlan.js')
  assert.match(archive, /archiveApi\.employmentTransition\(id\)/)
  assert.match(api, /employment-transition/)
  assert.match(employment, /只认归档中冻结的已发布正式成绩/)
  assert.match(nav, /\/admin\/employment\/students\?source=internship/)
  assert.doesNotMatch(nav, /就业衔接', '\/admin\/employment\?panel=follow-up/)
})

test('batch archive packages are bounded, scoped, downloadable and recovery checked', () => {
  const view = read('src/modules/internship/views/ArchiveView.vue')
  const api = read('src/modules/internship/api/archive.api.js')
  assert.match(view, /每片最多 20 人/)
  assert.match(view, /archiveApi\.buildBatchPackage\(batchId, \{ afterId, limit: 20 \}\)/)
  assert.match(view, /生成下一分片/)
  assert.match(view, /archiveApi\.verifyRestore\(pkg\.packageId\)/)
  assert.match(api, /archive-batches\/\$\{batchId\}\/packages/)
  assert.match(api, /archive-batch-packages\/\$\{encodeURIComponent\(packageId\)\}\/download/)
})
