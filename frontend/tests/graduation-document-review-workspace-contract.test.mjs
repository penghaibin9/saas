import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { graduationTemplateCopy } from './graduation-template-copy.mjs'

const root = path.resolve(fileURLToPath(new URL('..', import.meta.url)))
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')
const finalSource = read('src/modules/graduation/views/FinalSubmissionListView.vue')
const proposalSource = read('src/modules/graduation/views/_shared/ProposalReviewCard.vue')
const materialCenterSource = read('src/modules/graduation/views/GraduationMaterialCenterView.vue')
const workspaceSource = read('src/modules/graduation/components/GraduationDocumentReviewWorkspace.vue')
const versionBarSource = read('src/components/file/viewer/AppDocumentVersionBar.vue')

test('W2 final Gold reuses mature business flow and locks canonical fileVersion', () => {
  for (const pattern of [
    /async load\(/, /select\(row, \{ force = false \} = \{\}\)/, /step\(delta\)/,
    /turnPage\(page\)/, /submitReview\(action\)/, /remind\(row\)/, /exportFinalsFn\(\)/
  ]) assert.match(finalSource, pattern)
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
  for (const pattern of [
    /GraduationDocumentReviewWorkspace/, /选题背景/, /研究方案与进度/, /预期成果/,
    /AppAuditTrail/, /holdProposalDefense/, /reviewProposal/,
    /expectedVersion:\s*this\.detail\.materialVersion/,
    /fileVersionId:\s*this\.detail\.fileVersionId/,
    /proposalVersions\(recordId\)/,
    /gd-proposal-review-draft:\$\{this\.detail\.id\}:\$\{fileVersionId\}/,
    /draftFileVersionId = oldCanonical/,
    /conflictPreviewFile = oldActiveFile/
  ]) assert.match(proposalSource, pattern)
  assert.doesNotMatch(proposalSource, /ProposalPdfViewer|SecureFileList|previewVersion\(/)
})

test('W2 proposal business-object switch never silently inherits the previous textarea draft', () => {
  assert.match(proposalSource, /handler\(nextId, previousId\)[\s\S]*resetForProposalChange\(\)/)
  assert.match(proposalSource, /resetForProposalChange\(\)[\s\S]*this\.saveDraft\(\)[\s\S]*this\.detail = null[\s\S]*this\.comment = ''/)
  assert.match(proposalSource, /this\.previewDraftKey = ''[\s\S]*this\.draftFileVersionId = null/)
})

test('W2 proposal stale-review conflict preserves the old draft but requires explicit carry into the new business version', () => {
  for (const pattern of [
    /gd-proposal-review-conflict-carry:v1/, /fromProposalId/, /fromFileVersionId/,
    /String\(this\.carriedDraft\.projectId\) === String\(this\.detail\.projectId\)/,
    /上一版本未提交草稿/, /不会自动成为当前版本的有效批阅意见/,
    /applyCarriedDraft\(\)/, /discardCarriedDraft\(\)/,
    /this\.stashConflictCarry\(draft\)[\s\S]*this\.\$emit\('conflict'/
  ]) assert.match(proposalSource, pattern)
})

test('W2 material center stays a management table and opens exact versions in the same-page fullscreen Reader', () => {
  for (const marker of ['mc-summary', 'mc-tabs', 'mc-filters', 'mc-table-wrap', 'mc-pagebar', 'AppConfirmDialog', 'FileVersionTimeline']) assert.match(materialCenterSource, new RegExp(marker))
  assert.match(materialCenterSource, /AppDocumentViewer/)
  assert.match(materialCenterSource, /const readerState = reactive\(\{[\s\S]*visible: false,[\s\S]*row: null,[\s\S]*file: null,[\s\S]*versions: \[\],[\s\S]*filterSnapshot: null,[\s\S]*scrollSnapshot: null/)
  assert.match(materialCenterSource, /filterSnapshot: \{[\s\S]*tab: tab\.value,[\s\S]*page: page\.value,[\s\S]*filters: \{ \.\.\.filters \},[\s\S]*routeQuery: buildRouteQuery\(\)/)
  assert.match(materialCenterSource, /tableTop: tableWrap\.value\?\.scrollTop/)
  assert.match(materialCenterSource, /tableLeft: tableWrap\.value\?\.scrollLeft/)
  assert.match(materialCenterSource, /Object\.assign\(filters, filterSnapshot\.filters\)/)
  assert.match(materialCenterSource, /tableWrap\.value\.scrollTop = scrollSnapshot\.tableTop/)
  assert.doesNotMatch(materialCenterSource, /api\.previewMaterial\(|window\.open\(/)
})

test('W2 material center historical timeline opens the exact selected FileVersion and never substitutes current', () => {
  assert.match(materialCenterSource, /historyItems\.value = versions\.map/)
  assert.match(materialCenterSource, /async function openHistoryVersion\(item\)/)
  assert.match(materialCenterSource, /await openReader\(row, file, versions\)/)
  assert.match(materialCenterSource, /const exactId = versionKey\(exactFile\)/)
  assert.match(materialCenterSource, /versions\.find\(\(item\) => String\(versionKey\(item\)\) === String\(exactId\)\)/)
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
  assert.match(workspaceSource, /grid-template-columns:250px minmax\(0,1fr\) 318px/)
  assert.match(workspaceSource, /grid-template-columns:205px minmax\(0,1fr\) 280px/)
  assert.match(workspaceSource, /@media\(max-width:1279px\)/)
  assert.match(workspaceSource, /max-width:100%/)
  assert.match(workspaceSource, /AppDocumentViewer/)
  assert.match(workspaceSource, /FileEvidencePanel/)
  assert.match(workspaceSource, /evidenceVersions/)
  assert.doesNotMatch(workspaceSource, /issueMaterialTicket|fileSdk|reviewFinal|reviewProposal|submitReview|material-center\/files/)
})

test('W2 workspace shows teacher decisions while keeping exact version identity in data attributes', () => {
  assert.match(workspaceSource, /data-testid="review-command-contract"/)
  assert.match(workspaceSource, /:data-material-version="expectedVersion \?\? ''"/)
  assert.match(workspaceSource, /:data-file-version-id="canonicalFileVersionId \?\? ''"/)
  assert.match(workspaceSource, /<span>提交版次<\/span>/)
  assert.match(workspaceSource, /<span>文件核对<\/span>/)
  assert.match(workspaceSource, /<span>批阅状态<\/span>/)
  assert.match(workspaceSource, /<details class="gd-review-workspace__evidence">/)
  assert.match(workspaceSource, /<summary>文件检查与历史版本<\/summary>/)
  assert.match(workspaceSource, /<details class="gd-review-workspace__subject">/)
  assert.match(workspaceSource, /<summary>当前学生与业务状态<\/summary>/)
  const evidence = workspaceSource.indexOf('<FileEvidencePanel')
  const review = workspaceSource.indexOf('<slot name="review" />')
  const summary = workspaceSource.indexOf('<div class="gd-review-workspace__summary">')
  assert.ok(evidence >= 0 && review > evidence && summary > review)
  assert.match(workspaceSource, /gd-business-view:has\(\.gd-review-workspace\)>\.gd-scope-alert\.app-inline-alert/)
  const copy = graduationTemplateCopy(workspaceSource)
  assert.doesNotMatch(copy.text, /canonical|FileVersion|业务版本与文件版本已锁定/)
  assert.doesNotMatch(copy.directOutputs.join(' '), /canonicalFileVersionId|fileVersionId/,
    'raw file identity must not be rendered as the primary teacher-facing value')
})

test('W2 workspace queue is keyboard and screen-reader explicit', () => {
  assert.match(workspaceSource, /queue\.length \? currentIndex \+ 1 : 0/)
  assert.match(workspaceSource, /:aria-current="index === currentIndex \? 'true' : undefined"/)
  assert.match(workspaceSource, /:aria-label="`\$\{item\.studentName/)
  assert.match(workspaceSource, /gd-review-workspace__queue>button:focus-visible/)
})
