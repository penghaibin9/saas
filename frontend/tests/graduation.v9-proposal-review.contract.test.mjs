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

test('U2 URL contract restores queue state and narrow detail keeps a whitelisted return context', () => {
  assert.match(source, /applyInitialRouteState\(this\.\$route\.query\)/)
  assert.match(source, /this\.filters\.status = this\.normalizeTab\(query\.tab\)/)
  assert.match(source, /this\.filters\.keyword = this\.routeText\(query\.keyword\)/)
  assert.match(source, /this\.page = this\.normalizePage\(query\.page\)/)
  assert.match(source, /this\.selKey = this\.routeText\(query\.sel\)/)
  assert.match(source, /'\$route\.query': \{[\s\S]*onRouteQueryChanged\(query\)/)
  assert.match(source, /buildListQuery\(overrides = \{\}\)/)
  assert.match(source, /tab: this\.filters\.status \|\| undefined/)
  assert.match(source, /page: String\(this\.page\)/)
  assert.match(source, /keyword: keyword \|\| undefined/)
  assert.match(source, /sel: this\.selKey \|\| undefined/)
  assert.match(source, /returnTo: this\.listReturnTo\(row\)/)
})

test('U2 makes the selected review subject and submit lock visible above the canonical review card', () => {
  assert.match(source, /class="pr-subject"/)
  assert.match(source, /:data-selected-record="rowKey\(selectedRow\)"/)
  assert.match(source, /当前批阅对象/)
  assert.match(source, /正在提交，禁止切换对象/)
  assert.match(source, /class="pr-lock" role="status"/)
})

test('U2 compact card removes duplicate queue, subject summary and auto-next chrome', () => {
  assert.match(card, /class="prc" :class="\{ 'is-compact': compact \}"/)
  for (const selector of [
    'gd-review-workspace__queue',
    'gd-review-workspace__business-bar',
    'gd-review-workspace__auto',
    'gd-review-workspace__summary',
    'gd-review-workspace__dossier'
  ]) {
    assert.match(card, new RegExp(`prc\\.is-compact[\\s\\S]*${selector}`))
  }
  assert.match(card, /gd-review-workspace\.is-narrow\)\{grid-template-columns:minmax\(0,1fr\) 300px!important/)
  assert.match(card, /max-width:1180px/)
  assert.match(card, /gd-review-workspace__review\)\{position:sticky/)
})
