import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(new URL('..', import.meta.url).pathname)
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')
const finalSource = read('src/modules/graduation/views/FinalSubmissionListView.vue')
const proposalSource = read('src/modules/graduation/views/_shared/ProposalReviewCard.vue')
const materialCenterSource = read('src/modules/graduation/views/GraduationMaterialCenterView.vue')
const workspaceSource = read('src/modules/graduation/components/GraduationDocumentReviewWorkspace.vue')
const versionBarSource = read('src/components/file/viewer/AppDocumentVersionBar.vue')

test('W2 final Gold reuses mature business flow and locks canonical fileVersion', () => {
  for (const marker of ['load()', 'select(row)', 'step(delta)', 'turnPage(page)', 'submitReview(action)', 'remind(row)', 'exportFinalsFn()']) {
    assert.match(finalSource, new RegExp(marker.replace(/[()]/g, '\\$&')))
  }
  assert.match(finalSource, /GraduationDocumentReviewWorkspace/)
  assert.match(finalSource, /expectedVersion:\s*this\.finalDetail\.materialVersion/)
  assert.match(finalSource, /fileVersionId:\s*this\.finalDetail\.fileVersionId/)
  assert.match(finalSource, /activePreviewVersionId/)
  assert.match(finalSource, /canonicalFileVersionId/)
  assert.match(finalSource, /versionConflict/)
  assert.match(finalSource, /gd-final-review-draft:\$\{row\.id\}:\$\{fileVersionId\}/)
  assert.doesNotMatch(finalSource, /SecureFileList|previewVersion\(|window\.open\(/)
})

test('W2 final separates current attachments, true asset history and review draft identity', () => {
  assert.match(finalSource, /finalVersions\(recordId\)/)
  assert.match(finalSource, /versionHistory\.filter\(\(item\) => String\(item\.assetId/)
  assert.match(finalSource, /:files="secureVersionFiles"/)
  assert.match(finalSource, /:versions="activeVersionHistory"/)
  assert.match(finalSource, /:evidence-versions="secureVersionFiles"/)
  assert.match(finalSource, /draftKey\(row = this\.selectedRow, fileVersionId = this\.draftFileVersionId \?\? this\.canonicalFileVersionId\)/)
  assert.match(finalSource, /activePreviewFile\.isCurrent !== false/)
})

test('W2 final conflicts pin the old descriptor, fail closed and reload server truth before auto-next', () => {
  assert.match(finalSource, /oldCanonicalVersionId[\s\S]*versionConflict = \{ old: oldCanonicalVersionId, latest \}/)
  assert.match(finalSource, /draftFileVersionId = oldCanonicalVersionId/)
  assert.match(finalSource, /conflictPreviewFile = oldActiveFile/)
  assert.match(finalSource, /return this\.versionConflict \? null : \(this\.secureVersionFiles\[0\]/)
  assert.match(finalSource, /isGraduationConflictResponse\(res\)[\s\S]*refreshSelectedConflictTruth/)
  assert.match(finalSource, /this\._selectIndexAfterLoad = reviewedIndex[\s\S]*await this\.load\(\)/)
})

test('W2 proposal reuses the same workspace and preserves proposal, audit and defense authorities', () => {
  assert.match(proposalSource, /GraduationDocumentReviewWorkspace/)
  assert.match(proposalSource, /选题背景/)
  assert.match(proposalSource, /研究方案与进度/)
  assert.match(proposalSource, /预期成果/)
  assert.match(proposalSource, /AppAuditTrail/)
  assert.match(proposalSource, /holdProposalDefense/)
  assert.match(proposalSource, /reviewProposal/)
  assert.match(proposalSource, /expectedVersion:\s*this\.detail\.materialVersion/)
  assert.match(proposalSource, /fileVersionId:\s*this\.detail\.fileVersionId/)
  assert.match(proposalSource, /proposalVersions\(recordId\)/)
  assert.match(proposalSource, /gd-proposal-review-draft:\$\{this\.detail\.id\}:\$\{fileVersionId\}/)
  assert.match(proposalSource, /draftFileVersionId = oldCanonical/)
  assert.match(proposalSource, /conflictPreviewFile = oldActiveFile/)
  assert.doesNotMatch(proposalSource, /ProposalPdfViewer|SecureFileList|previewVersion\(/)
})

test('W2 material center stays a management table and opens exact versions in the same-page fullscreen Reader', () => {
  for (const marker of ['mc-summary', 'mc-tabs', 'mc-filters', 'mc-table-wrap', 'mc-pagebar', 'AppConfirmDialog', 'FileVersionTimeline']) {
    assert.match(materialCenterSource, new RegExp(marker))
  }
  assert.match(materialCenterSource, /AppDocumentViewer/)
  assert.match(materialCenterSource, /readerState = reactive\(\{ visible: false, row: null, file: null, versions: \[\], filterSnapshot: null, scrollSnapshot: null/)
  assert.match(materialCenterSource, /filterSnapshot: \{ tab: tab\.value, page: page\.value, filters: \{ \.\.\.filters \} \}/)
  assert.match(materialCenterSource, /tableTop: tableWrap\.value\?\.scrollTop/)
  assert.match(materialCenterSource, /tableLeft: tableWrap\.value\?\.scrollLeft/)
  assert.match(materialCenterSource, /Object\.assign\(filters, filterSnapshot\.filters\)/)
  assert.match(materialCenterSource, /tableWrap\.value\.scrollTop = scrollSnapshot\.tableTop/)
  assert.doesNotMatch(materialCenterSource, /api\.previewMaterial\(|window\.open\(/)
})

test('W2 material center historical timeline opens the exact selected FileVersion and never substitutes current', () => {
  assert.match(materialCenterSource, /historyItems\.value = versions\.map/)
  assert.match(materialCenterSource, /async function openHistoryVersion\(item\)/)
  assert.match(materialCenterSource, /await openReader\(row, file, historyVersions\.value\)/)
  assert.match(materialCenterSource, /const exactId = versionKey\(exactFile\)/)
  assert.match(materialCenterSource, /versions\.find\(item => String\(versionKey\(item\)\) === String\(exactId\)\)/)
  assert.match(materialCenterSource, /readerIsHistorical/)
  assert.match(materialCenterSource, /历史版本 v\{\{ readerState\.file\?\.versionNo/)
  assert.match(materialCenterSource, /readerState\.file\.isCurrent === false/)
})

test('W2 version bar labels history from server isCurrent rather than treating sibling attachments as history', () => {
  assert.match(versionBarSource, /item\.isCurrent === false/)
  assert.match(versionBarSource, /当前附件/)
  assert.match(versionBarSource, /本次审核/)
})

test('W2 workspace keeps transport and domain commands outside the public Viewer', () => {
  assert.match(workspaceSource, /grid-template-columns:272px minmax\(680px,1fr\) 340px/)
  assert.match(workspaceSource, /AppDocumentViewer/)
  assert.match(workspaceSource, /FileEvidencePanel/)
  assert.match(workspaceSource, /evidenceVersions/)
  assert.doesNotMatch(workspaceSource, /issueMaterialTicket|fileSdk|reviewFinal|reviewProposal|submitReview|material-center\/files/)
})
