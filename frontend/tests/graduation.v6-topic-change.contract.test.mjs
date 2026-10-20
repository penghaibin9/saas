import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const [page, service] = await Promise.all([
  readFile(new URL('../src/modules/graduation/views/TopicChangeRequestListView.vue', import.meta.url), 'utf8'),
  readFile(new URL('../../backend/app/modules/graduation/services/graduation_topic_change_consistency.py', import.meta.url), 'utf8')
])

test('V6 topic change list restores its batch status page and return context', () => {
  for (const key of ['batchId', 'status', 'page', 'returnTo']) {
    assert.ok(page.includes(key), `missing topic-change query key ${key}`)
  }
  assert.match(page, /buildRouteQuery\(overrides = \{\}\)/)
  assert.match(page, /currentReturnTo\(\)/)
  assert.match(page, /path: `\/admin\/graduation\/topic-changes\/\$\{row\.id\}`/)
})

test('V6 topic change reads are latest-wins and review commands freeze object and batch', () => {
  assert.match(page, /loadToken: 0/)
  assert.match(page, /const token = \+\+this\.loadToken/)
  assert.match(page, /token !== this\.loadToken/)
  assert.match(page, /commandSnapshot: null/)
  assert.match(page, /rowId: row\.id/)
  assert.match(page, /batchId: String\(this\.batchStore\.selectedBatchId/)
  assert.match(page, /routeQuery: this\.buildRouteQuery\(\)/)
  assert.match(page, /beforeRouteLeave\(to, from, next\)/)
  assert.match(page, /next\(false\)/)
})

test('V6 approve uses canonical server migration and rereads the processed request', () => {
  assert.match(service, /student\.topic_id = new_topic\.id/)
  assert.match(service, /student\.topic_title = new_topic\.title/)
  assert.match(service, /new_topic\.selected = int\(new_topic\.selected or 0\) \+ 1/)
  assert.match(service, /old_topic\.selected = int\(old_topic\.selected or 0\) - 1/)
  assert.match(page, /gdTopicChangeApi\.reviewChangeRequest\(snapshot\.rowId/)
  assert.match(page, /gdTopicChangeApi\.getChangeRequestDetail\(snapshot\.rowId\)/)
  assert.match(page, /await this\.load\(\)/)
})

test('V6 rejection keeps a mandatory reason in the frozen command snapshot', () => {
  assert.match(page, /requireReason: true/)
  assert.match(page, /reasonLabel: '驳回理由'/)
  assert.match(page, /reason: reason \|\| ''/)
  assert.match(page, /comment: snapshot\.reason/)
})
