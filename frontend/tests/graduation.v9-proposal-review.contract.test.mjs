import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const viewPath = path.resolve(here, '../src/modules/graduation/views/ProposalListView.vue')
const source = fs.readFileSync(viewPath, 'utf8')

test('U2 keeps the split review workspace and responsive/keyboard contracts', () => {
  assert.match(source, /class="pr-split"/)
  assert.match(source, /class="pr-list"/)
  assert.match(source, /class="pr-pane"/)
  assert.match(source, /e\.key === 'ArrowDown'/)
  assert.match(source, /e\.key === 'ArrowUp'/)
  assert.match(source, /批阅后自动进入下一条待审/)
  assert.match(source, /max-width: 1100px/)
})

test('U2 pending auto-next reloads the same server page before selecting the next student', () => {
  assert.match(source, /const pendingQueue = this\.filters\.status === 'PENDING_REVIEW'/)
  assert.match(source, /this\._selectIndexAfterLoad = reviewedIndex/)
  assert.match(source, /await this\.load\(\)/)
  assert.match(source, /if \(!this\.rows\.length && this\.page > 1\)/)
  assert.match(source, /this\.page -= 1/)
  assert.match(source, /Number\.isInteger\(this\._selectIndexAfterLoad\)/)
})
