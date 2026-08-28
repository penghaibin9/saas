import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('discipline REVISED appeal collects and sends authoritative revised facts', () => {
  const view = read('src/modules/studentAffairs/views/discipline/DisciplineAppealView.vue')
  const api = read('src/modules/studentAffairs/api/disciplineIntegrity.api.js')
  const backend = read('../backend/app/api/v1/affairs_discipline_integrity_api.py')

  assert.match(view, /变更后的处分事实（5-1000字）/)
  assert.match(view, /v-model="revDlg\.revisedReason"/)
  assert.match(view, /v-model="revDlg\.revisedDocNo"/)
  assert.match(view, /变更后的处分事实需5-1000字/)
  assert.match(view, /revisedReason:\s*\(dialog\.revisedReason \|\| ''\)\.trim\(\)/)
  assert.match(view, /revisedDocNo:\s*\(dialog\.revisedDocNo \|\| ''\)\.trim\(\)/)

  assert.match(api, /revisedReason\s*=\s*''/)
  assert.match(api, /revisedDocNo\s*=\s*''/)
  assert.match(api, /body\.revisedReason\s*=\s*revisedReason/)
  assert.match(api, /body\.revisedDocNo\s*=\s*revisedDocNo/)
  assert.match(api, /\/discipline\/appeals\/\$\{appealId\}\/decision-review/)
  assert.doesNotMatch(api, /\/discipline\/appeals\/\$\{appealId\}\/review/)

  assert.match(backend, /class DisciplineDecisionReviewBody\(BaseModel\):/)
  assert.match(backend, /revisedDiscType: Optional\[str\]/)
  assert.match(backend, /revisedReason: Optional\[str\]/)
  assert.match(backend, /revisedDocNo: Optional\[str\]/)
  assert.match(backend, /@router\.post\("\/appeals\/\{appeal_id\}\/decision-review"/)
})