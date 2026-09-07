import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import test from 'node:test'

const root = process.cwd()
const view = fs.readFileSync(path.join(root, 'src/modules/studentAffairs/views/funding/FeeReductionView.vue'), 'utf8')
const api = fs.readFileSync(path.join(root, 'src/modules/studentAffairs/api/studentAffairs.api.js'), 'utf8')

test('teacher fee workspace opens on the actionable queue without duplicate overview cards', () => {
  assert.match(view, /status: 'SUBMITTED'/)
  assert.match(view, /title="申请办理台账" compact/)
  assert.match(view, /title: '下一步'/)
  assert.doesNotMatch(view, /sa-summary-strip|sa-workflow-strip|AppMetricCard/)
})

test('teacher actions use semantic server actions and item-specific completion labels', () => {
  assert.match(view, /APPROVE.*RETURN.*REJECT.*FULFILL/s)
  assert.match(view, /确认减免/)
  assert.match(view, /登记发放/)
  assert.match(api, /actionFeeReduction\(feeId, body\)/)
  assert.match(api, /fee-reductions\/\$\{feeId\}\/action/)
})
