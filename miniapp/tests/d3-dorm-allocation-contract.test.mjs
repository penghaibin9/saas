import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const api = read('../src/services/realApi.js')
const student = read('../src/pages/student/affairs/dorm.vue')
const teacher = read('../src/pages/teacher/dorm-review/index.vue')

test('D3 miniapp selects only from server-provided batch resources', () => {
  assert.match(api, /\/mobile\/affairs\/dorm\/select-options/)
  assert.match(api, /\/mobile\/affairs\/dorm\/beds\/\$\{bedId\}\/self-select/)
  assert.match(student, /确认后床位将为你预留，变更须走正式调宿/)
  assert.match(student, /正式调宿须审批/)
  assert.doesNotMatch(student, /入住成功|已正式入住/)
})

test('D3 teacher miniapp consumes the scoped allocation summary', () => {
  for (const field of ['activeBatchCount', 'pendingSelectionCount', 'reservedCount', 'conflictCount']) {
    assert.match(teacher, new RegExp(`allocationSummary\\.${field}`))
  }
  assert.match(teacher, /getAffairsDormPending/)
})
