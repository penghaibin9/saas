import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/modules/studentAffairs/views/funding/StudentLoanView.vue', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/modules/studentAffairs/api/studentAffairs.api.js', import.meta.url), 'utf8')

test('teacher PC loan workspace leads with the task ledger and semantic actions', () => {
  assert.match(source, /class="ln-statusbar"/)
  assert.match(source, /贷款办理台账/)
  for (const action of ['SUBMIT_RECEIPT', 'VERIFY', 'RETURN', 'CONFIRM']) assert.match(source, new RegExp(`allows\\(row, '${action}'\\)`))
  assert.match(api, /actionLoan\(loanId, body\)/)
  assert.doesNotMatch(source, /summary-card|metric-card|advanceLoan\(/)
})
