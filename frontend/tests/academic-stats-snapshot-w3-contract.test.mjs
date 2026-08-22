import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const api = readFileSync(
  new URL('../src/modules/academicAffairs/api/academic-stats-snapshot.api.js', import.meta.url),
  'utf8'
)
const workspace = readFileSync(
  new URL('../src/modules/academicAffairs/components/AaStatsSnapshotWorkspace.vue', import.meta.url),
  'utf8'
)
const host = readFileSync(
  new URL('../src/modules/academicAffairs/views/AaStatsOverviewView.vue', import.meta.url),
  'utf8'
)

test('W3 semantic client owns create list detail verify without browser hash authority', () => {
  for (const token of ['create(body', 'list(params', 'detail(snapshotId', 'verify(snapshotId', '/verify']) {
    assert.match(api, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.doesNotMatch(api, /crypto|subtle|sha256|createHash/i)
})

test('stats host mounts snapshot as a tab and does not create a second route/menu', () => {
  assert.match(host, /{ key: 'snapshot', label: '统计快照' }/)
  assert.match(host, /<AaStatsSnapshotWorkspace :context-filters="filters" \/>/)
  assert.match(host, /tab !== 'snapshot'/)
})

test('snapshot workspace exposes freeze history, detail and server verify semantics', () => {
  for (const text of [
    '冻结当前统计', '后续实时源数据变化不会回写已冻结快照', 'payloadHash',
    '冻结原因', '冻结 payload', '重新校验完整性', '服务端校验通过'
  ]) assert.match(workspace, new RegExp(text))
  assert.match(workspace, /academicAffairs\.stats\.snapshot\.view/)
  assert.match(workspace, /academicAffairs\.stats\.snapshot\.create/)
  assert.match(workspace, /academicAffairs\.stats\.snapshot\.manage/)
  assert.match(workspace, /academicStatsSnapshotApi\.verify/)
  assert.doesNotMatch(workspace, /crypto|subtle|sha256|createHash/i)
})

test('freeze form inherits current stats filter context and requires a reason', () => {
  assert.match(workspace, /contextFilters\?\.termId/)
  assert.match(workspace, /contextFilters\?\.collegeId/)
  assert.match(workspace, /contextFilters\?\.majorId/)
  assert.match(workspace, /createForm\.reason\.length < 5/)
  assert.match(workspace, /确认冻结统计快照/)
})
