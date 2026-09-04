import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const read = (rel) => fs.readFileSync(path.resolve(here, rel), 'utf8')
const source = read('../src/modules/graduation/views/FinalSubmissionListView.vue')
const workspace = read('../src/modules/graduation/components/GraduationDocumentReviewWorkspace.vue')
const evidence = read('../src/modules/graduation/components/FileEvidencePanel.vue')

test('U3 keeps the final review split workspace, keyboard navigation, and responsive fallback', () => {
  assert.match(source, /GraduationDocumentReviewWorkspace/)
  assert.match(workspace, /gd-review-workspace__queue/)
  assert.match(workspace, /gd-review-workspace__document/)
  assert.match(workspace, /gd-review-workspace__review/)
  assert.match(source, /event\.key === 'ArrowDown'/)
  assert.match(source, /event\.key === 'ArrowUp'/)
  assert.match(workspace, /批阅成功后自动下一条/)
  assert.match(workspace, /@media\(max-width:1599px\)/)
  assert.match(workspace, /@media\(max-width:1279px\)/)
})

test('U3 pending review reloads the same server page before selecting the next final', () => {
  assert.match(source, /const pendingQueue = this\.filters\.status === 'PENDING_REVIEW'/)
  assert.match(source, /this\._selectIndexAfterLoad = reviewedIndex/)
  assert.match(source, /await this\.load\(\)/)
  assert.match(source, /if \(!this\.rows\.length && this\.page > 1\)/)
  assert.match(source, /this\.page -= 1/)
  assert.match(source, /Number\.isInteger\(this\._selectIndexAfterLoad\)/)
})

test('U3 preserves the secure canonical FileVersion review gate', () => {
  assert.match(source, /finalDetail\?\.reviewReady/)
  assert.match(source, /expectedVersion \+ fileVersionId/)
  assert.match(source, /canonicalFileVersionId/)
  assert.match(source, /versionConflict/)
  assert.match(workspace, /FileEvidencePanel/)
  assert.match(evidence, /canonical/i)
})

test('U3 keeps the five-second decision surface in the shared Reader workspace', () => {
  assert.match(source, /class="mp-stack fr-workbench-stack"/)
  assert.match(source, /size="compact"/)
  assert.match(workspace, /gd-review-workspace__summary/)
  assert.match(workspace, /gd-review-workspace__business-bar/)
  assert.match(workspace, /gd-review-workspace__conflict/)
  assert.match(workspace, /FileEvidencePanel/)
  assert.match(workspace, /grid-template-columns:250px minmax\(0,1fr\) 318px/)
  assert.match(workspace, /grid-template-columns:205px minmax\(0,1fr\) 280px/)
  assert.match(workspace, /gd-review-workspace\.is-narrow\{grid-template-columns:1fr\}/)
})

test('U3 makes record, expectedVersion, canonical FileVersion and safety gate visible before the command', () => {
  assert.match(source, /class="fr-selected-summary"/)
  assert.match(source, /提交中，已锁定对象与版本/)
  assert.match(workspace, /data-testid="review-command-contract"/)
  assert.match(workspace, />提交版本</)
  assert.match(workspace, />文件版本</)
  assert.match(workspace, />文件状态</)
  assert.match(workspace, /expectedVersion \?\? '—'/)
  assert.match(workspace, /canonicalFileVersionId \?\? '—'/)
  assert.match(workspace, /reviewReady && !versionConflict/)
})

test('U3 locks every context-changing interaction while a canonical command is submitting', () => {
  assert.match(source, /:disabled="submitting"[\s\S]*@click="switchTab/)
  assert.match(source, /AppSearchBox[\s\S]*:disabled="submitting"/)
  assert.match(source, /if \(this\.isNarrow \|\| this\.submitting\) return/)
  assert.match(source, /switchTab\(value\) \{[\s\S]*if \(this\.submitting\) return/)
  assert.match(source, /turnPage\(page\) \{[\s\S]*if \(this\.submitting\) return/)
  assert.match(source, /select\(row, \{ force = false \} = \{\}\) \{[\s\S]*if \(!row \|\| \(this\.submitting && !force\)\) return/)
  assert.match(source, /selectPreviewFile\(item\) \{[\s\S]*if \(!item \|\| this\.submitting\) return/)
  assert.match(source, /step\(delta\) \{[\s\S]*if \(this\.submitting\) return/)
  assert.match(source, /submitReview\(action\) \{[\s\S]*if \(this\.submitting \|\| !this\.canReview/)
  assert.match(source, /finally \{[\s\S]*this\.submitting = false/)
  assert.match(workspace, /function emitUnlocked\(event, payload\)[\s\S]*if \(props\.submitting\) return/)
  assert.match(workspace, /allowDownload && !submitting/)
  assert.match(workspace, /is-command-locked/)
  assert.match(workspace, /is-submitting \.gd-review-workspace__queue\{pointer-events:none\}/)
})

test('U3 list, stats and detail reads are latest-wins and URL state is reloadable', () => {
  assert.match(source, /loadToken: 0/)
  assert.match(source, /statsToken: 0/)
  assert.match(source, /detailToken: 0/)
  assert.match(source, /const token = \+\+this\.loadToken/)
  assert.match(source, /token !== this\.loadToken \|\| String\(batchId\) !== String\(this\.batchStore\.selectedBatchId\)/)
  assert.match(source, /const token = \+\+this\.statsToken/)
  assert.match(source, /const requestKey = `\$\{\+\+this\.detailToken\}:\$\{row\.id\}:\$\{batchId\}`/)
  assert.match(source, /this\.detailRequestKey !== requestKey \|\| this\.rowKey\(row\) !== this\.selKey/)
  assert.match(source, /applyInitialRouteState\(this\.\$route\.query\)/)
  assert.match(source, /this\.filters\.keyword = this\.routeText\(query\.keyword\)/)
  assert.match(source, /this\.page = this\.normalizePage\(query\.page\)/)
  assert.match(source, /page: String\(this\.page\)/)
  assert.match(source, /sel: this\.selKey \|\| undefined/)
})
