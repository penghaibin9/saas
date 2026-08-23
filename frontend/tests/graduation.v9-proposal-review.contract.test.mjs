import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const viewPath = path.resolve(here, '../src/modules/graduation/views/ProposalListView.vue')
const cardPath = path.resolve(here, '../src/modules/graduation/views/_shared/ProposalReviewCard.vue')
const source = fs.readFileSync(viewPath, 'utf8')
const card = fs.readFileSync(cardPath, 'utf8')

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

test('U2 proposal reads are latest-wins and canonical mutations own one task context until completion', () => {
  assert.match(card, /emits: \['reviewed', 'conflict', 'submitting-change'\]/)
  assert.match(card, /loadToken: 0/)
  assert.match(card, /const proposalId = this\.proposalId[\s\S]*const token = \+\+this\.loadToken/)
  assert.match(card, /token !== this\.loadToken \|\| String\(proposalId\) !== String\(this\.proposalId\)/)
  assert.match(card, /async loadVersionHistory\(recordId, token\)/)
  assert.match(card, /sameTask\(proposalId, detailId\)/)
  assert.match(card, /setSubmitting\(value\)[\s\S]*this\.\$emit\('submitting-change', this\.submitting\)/)
  assert.match(card, /finally \{[\s\S]*this\.setSubmitting\(false\)/)

  assert.match(source, /reviewSubmitting: false/)
  assert.match(source, /loadToken: 0/)
  assert.match(source, /statsToken: 0/)
  assert.match(source, /@submitting-change="onReviewSubmittingChange"/)
  assert.match(source, /:disabled="reviewSubmitting \|\| selIndex <= 0"/)
  assert.match(source, /:disabled="reviewSubmitting \|\| !hasNext"/)
  assert.match(source, /if \(this\.isNarrow \|\| this\.reviewSubmitting\) return/)
  assert.match(source, /if \(this\.reviewSubmitting && !force\) return/)
  assert.match(source, /token !== this\.loadToken \|\| String\(batchId\) !== String\(this\.batchStore\.selectedBatchId\)/)
  assert.match(source, /token !== this\.statsToken \|\| String\(batchId\) !== String\(this\.batchStore\.selectedBatchId\)/)
})
