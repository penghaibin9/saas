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
  assert.match(workspace, /原事实与新事实对比/)
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

test('review UI consumes server facts and requires formal high-risk confirmation', () => {
  assert.match(workspace, /detail\.originalOfficialFact/)
  assert.match(workspace, /detail\.proposedOfficialFact/)
  assert.match(workspace, /detail\.resultingOfficialFact/)
  assert.match(workspace, /新正式事实/)
  assert.match(workspace, /detail\.rejectReason/)
  assert.match(workspace, /detail\.rejectedBy/)
  assert.match(workspace, /title="确认驳回归档后纠错"/)
  assert.match(workspace, /confirm-text="确认驳回"/)
  assert.match(workspace, /:require-reason="true"/)
  assert.match(workspace, /reason-label="驳回原因"/)
  assert.match(workspace, /未生成正式事实，也未生成新 Manifest/)
  assert.match(workspace, /app-confirm-dialog__mask/)
  assert.match(workspace, /z-index: calc\(var\(--z-modal\) \+ 1\)/)
})
