import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const api = readFileSync(
  new URL('../src/modules/academicAffairs/api/academic-archive-correction.api.js', import.meta.url),
  'utf8'
)
const workspace = readFileSync(
  new URL('../src/modules/academicAffairs/components/AaArchiveCorrectionWorkspace.vue', import.meta.url),
  'utf8'
)
const consoleView = readFileSync(
  new URL('../src/modules/academicAffairs/views/AaArchiveConsoleView.vue', import.meta.url),
  'utf8'
)

test('W1 archive correction API exposes the formal server-authoritative loop', () => {
  assert.match(api, /\/batches\/\$\{batchId\}\/corrections/)
  assert.match(api, /\/corrections\/\$\{caseId\}`/)
  assert.match(api, /\/corrections\/\$\{caseId\}\/approve/)
  assert.match(api, /\/corrections\/\$\{caseId\}\/reject/)
  assert.match(api, /body: \{ reason \}/)
  assert.match(api, /\/batches\/\$\{batchId\}\/manifest\/verify/)
  assert.doesNotMatch(api, /unfreeze/i)
})

test('ARCHIVED batch stays inside the existing archive console with three W1 workspaces', () => {
  assert.match(consoleView, /current\.status === 'ARCHIVED'/)
  assert.match(consoleView, /AaArchiveCorrectionWorkspace/)
  assert.match(workspace, /归档事实/)
  assert.match(workspace, /归档后纠错/)
  assert.match(workspace, /Manifest版本链/)
  assert.match(workspace, /原事实与申请修正对比/)
  assert.match(workspace, /二审通过并生成新正式事实/)
  assert.match(workspace, /驳回/)
  assert.doesNotMatch(workspace, /解冻归档|恢复归档|reopen/i)
})

test('mutations always reread correction, manifest and parent batch state from server', () => {
  assert.match(workspace, /await this\.authoritativeRefresh\(caseId\)/)
  assert.match(workspace, /await this\.refreshAll\(\)/)
  assert.match(workspace, /this\.\$emit\('refresh-batch'\)/)
  assert.match(workspace, /api\.list\(this\.batchId/)
  assert.match(workspace, /api\.verifyManifest\(this\.batchId\)/)
  assert.match(workspace, /api\.detail\(caseId\)/)
  assert.match(consoleView, /@refresh-batch="refreshCurrentFromServer"/)
  assert.match(consoleView, /api\.getBatch\(batchId\)/)
})

test('review UI consumes server-provided original/proposed facts and rejection evidence', () => {
  assert.match(workspace, /detail\.originalOfficialFact/)
  assert.match(workspace, /detail\.proposedOfficialFact/)
  assert.match(workspace, /detail\.rejectReason/)
  assert.match(workspace, /detail\.rejectedBy/)
  assert.match(workspace, /未生成正式事实或新的 Manifest/)
})
