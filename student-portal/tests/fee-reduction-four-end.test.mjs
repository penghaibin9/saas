import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = process.cwd()
const view = fs.readFileSync(path.join(root, 'src/views/affairs/ReductionStudentView.vue'), 'utf8')
const shell = fs.readFileSync(path.join(root, 'src/views/affairs/AffairsFourEndView.vue'), 'utf8')
const api = fs.readFileSync(path.join(root, 'src/services/portalApi.js'), 'utf8')

test('student PC exposes reduction as a first-class same-shell workflow', () => {
  assert.match(shell, /ReductionStudentView/)
  assert.match(shell, /key: 'reduction', label: '减免与临补'/)
  assert.match(view, /FundingAttachments/)
  assert.match(view, /biz-type="REDUCTION"/)
})

test('student PC consumes server actions for submit, correction and withdrawal', () => {
  assert.match(view, /allows\(item, 'RESUBMIT'\)/)
  assert.match(view, /allows\(item, 'WITHDRAW'\)/)
  assert.match(api, /affairsFeeReductionSubmit/)
  assert.match(api, /affairsFeeReductionResubmit/)
  assert.match(api, /affairsFeeReductionWithdraw/)
})
