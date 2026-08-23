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
  assert.match(workspace, /grid-template-columns:272px minmax\(0,1fr\) 340px/)
  assert.match(workspace, /grid-template-columns:220px minmax\(0,1fr\) 290px/)
  assert.match(workspace, /gd-review-workspace\.is-narrow\{grid-template-columns:1fr\}/)
})
