import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const read = (path) => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

test('teacher mini discipline REVISED sends complete authoritative facts', () => {
  const view = read('miniapp/src/pages/teacher/affairs-review/index.vue')

  assert.match(view, /visibleAppealActions\(x\)\.length/)
  assert.match(view, /v-for="a in visibleAppealActions\(x\)"/)
  assert.match(view, /HIGH_RISK_KINDS/)
  assert.match(view, /if \(HIGH_RISK_KINDS\.has\(this\.kind\)\) return \[\]/)
  assert.match(view, /if \(!Array\.isArray\(x && x\.allowedActions\)\) return \[\]/)
  assert.match(view, /x\.allowedActions\.includes\('REVIEW'\)/)
  assert.match(view, /!this\.visibleAppealActions\(x\)\.some/)

  assert.match(view, /reviewAppeal\(x, action, previous = '', revisedDiscType = '', revisedReason = '', revisedDocNo = null\)/)
  assert.match(view, /title: '变更后的处分事实'/)
  assert.match(view, /变更后的处分事实至少5字/)
  assert.match(view, /title: '变更后的文号'/)
  assert.match(view, /revisedDiscType, revisedReason, revisedDocNo: revisedDocNo \|\| ''/)
  assert.match(view, /this\.reviewAppeal\(x, action, opinion, revisedDiscType, revisedReason, revisedDocNo\)/)
})

test('mobile discipline REVISED raw payload reaches the canonical integrity service', () => {
  const fourEnd = read('backend/app/services/affairs_four_end_contract.py')
  const guard = read('backend/app/services/affairs_discipline_integrity_guard.py')

  assert.match(fourEnd, /_REQUEST_BODY: ContextVar\[dict\]/)
  assert.match(fourEnd, /path\.startswith\("\/api\/v1\/mobile\/teacher\/affairs"\)/)
  assert.match(fourEnd, /_REQUEST_BODY\.set\(body\)/)

  assert.match(guard, /raw_body = contract\._REQUEST_BODY\.get\(\{\}\) or \{\}/)
  assert.match(guard, /raw_body\.get\("revisedReason"\)/)
  assert.match(guard, /raw_body\.get\("revisedDocNo"\)/)
  assert.match(guard, /if len\(revised_reason\) < 5:/)
  assert.match(guard, /kind="REVISED"/)
  assert.match(guard, /projection\.reason = revised_reason/)
  assert.match(guard, /to_stage="DISCIPLINE_REVISED"/)
})
