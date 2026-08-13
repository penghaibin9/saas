import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const viewPath = path.resolve(here, '../src/modules/graduation/views/FinalSubmissionListView.vue')
const source = fs.readFileSync(viewPath, 'utf8')

test('U3 keeps the final review split workspace, keyboard navigation, and responsive fallback', () => {
  assert.match(source, /class="fr-split"/)
  assert.match(source, /class="fr-list"/)
  assert.match(source, /class="fr-pane"/)
  assert.match(source, /event\.key === 'ArrowDown'/)
  assert.match(source, /event\.key === 'ArrowUp'/)
  assert.match(source, /处理后自动进入下一条待审/)
})

test('U3 pending review reloads the same server page before selecting the next final', () => {
  assert.match(source, /const pendingQueue = this\.filters\.status === 'PENDING_REVIEW'/)
  assert.match(source, /this\._selectIndexAfterLoad = reviewedIndex/)
  assert.match(source, /await this\.load\(\)/)
  assert.match(source, /if \(!this\.rows\.length && this\.page > 1\)/)
  assert.match(source, /this\.page -= 1/)
  assert.match(source, /Number\.isInteger\(this\._selectIndexAfterLoad\)/)
})

test('U3 preserves the secure FileVersion review gate', () => {
  assert.match(source, /finalDetail\?\.reviewReady/)
  assert.match(source, /expectedVersion: this\.finalDetail\.materialVersion/)
  assert.match(source, /fileVersionId: this\.finalDetail\.fileVersionId/)
  assert.match(source, /SHA-256/)
})
