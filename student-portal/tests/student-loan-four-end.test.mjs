import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')

test('registered and returned original loans both expose the correction button', () => {
  const source = read('../src/views/affairs/LoanStudentView.vue')
  const expression = source.match(/v-if="([^"]+)"[^>]*@click="openEdit\(item\)"/)[1]
  const shown = new Function('item', 'allows', `return ${expression}`)
  const allows = (item, action) => item.allowedActions.includes(action)
  assert.equal(shown({ allowedActions: ['SUBMIT_RECEIPT'] }, allows), true)
  assert.equal(shown({ allowedActions: ['RESUBMIT'] }, allows), true)
  assert.equal(shown({ allowedActions: [] }, allows), false)
})

test('student PC exposes the canonical loan receipt workflow', () => {
  const host = read('../src/views/affairs/AffairsFourEndView.vue')
  const loan = read('../src/views/affairs/LoanStudentView.vue')
  const api = read('../src/services/portalApi.js')
  const nav = read('../src/platform/workspaceNavigation.js')
  assert.match(host, /tab === 'loan'/)
  assert.match(nav, /campus-service\?tab=loan/)
  assert.match(api, /affairsLoanSubmit/)
  assert.match(api, /affairsLoanResubmit/)
  assert.match(api, /affairsLoanWithdraw/)
  assert.match(loan, /allows\(item, 'RESUBMIT'\)/)
  assert.match(loan, /allows\(item, 'WITHDRAW'\)/)
  assert.doesNotMatch(loan, /status === 'RETURNED'.*修改后重提.*button/s)
})
