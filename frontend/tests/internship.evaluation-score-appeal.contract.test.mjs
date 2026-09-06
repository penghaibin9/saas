import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8')

test('Staff score workbench exposes five truthful queues and a two-step review/publish flow', () => {
  const view = read('frontend/src/modules/internship/views/ScoreView.vue')
  for (const label of ['缺项', '待核算', '待复核', '待发布', '申诉']) assert.match(view, new RegExp(label))
  assert.match(view, /review: 'PENDING_REVIEW'/)
  assert.match(view, /publish: 'PENDING_PUBLISH'/)
  assert.match(view, /scoreApi\.review\(p\.id, ver\)/)
  assert.match(view, /scoreApi\.publish\(p\.id, ver\)/)
  assert.ok(view.indexOf("p.kind === 'review'") < view.indexOf("p.kind === 'publish'"))
  assert.doesNotMatch(view, /scoreApi\.archive/)
  assert.doesNotMatch(view, /confirmAct\(row, 'archive'\)/)
})

test('Staff compute submits only server-governed facts or evidence-bound deltas', () => {
  const view = read('frontend/src/modules/internship/views/ScoreView.vue')
  const api = read('frontend/src/modules/internship/api/score.api.js')
  assert.match(view, /body\.manualAdjustments/)
  assert.match(view, /body\.adjustmentReason/)
  assert.match(view, /body\.adjustmentEvidenceFileIds/)
  assert.match(view, /body\.expectedVersion = current\.version/)
  for (const field of ['checkinScore', 'weeklyScore', 'monthlyScore', 'enterpriseScore', 'schoolScore']) {
    assert.doesNotMatch(view, new RegExp(`body\\.${field}`))
  }
  assert.match(api, /INTERNSHIP_SCORE_ADJUSTMENT/)
  assert.match(view, /ActionReceipt/)
  assert.match(view, /sourceReadiness/)
})

test('Staff evaluation reviews preserve CAS and never silently replay a stale command', () => {
  const enterpriseApi = read('frontend/src/modules/internship/api/enterprise-eval.api.js')
  const enterpriseView = read('frontend/src/modules/internship/views/EnterpriseEvalView.vue')
  const studentView = read('frontend/src/modules/internship/views/StudentEvalView.vue')
  assert.match(enterpriseApi, /expectedVersion/)
  assert.doesNotMatch(enterpriseApi, /stale|latestVersion|retry/i)
  assert.match(enterpriseView, /expectedVersion/)
  assert.match(studentView, /expectedVersion/)
  assert.match(enterpriseView, /ActionReceipt/)
  assert.match(studentView, /ActionReceipt/)
})

test('Appeal decisions name the frozen score and leave a durable next-step receipt', () => {
  const view = read('frontend/src/modules/internship/views/ScoreView.vue')
  assert.match(view, /expectedVersion: item\.version/)
  assert.match(view, /冻结成绩/)
  assert.match(view, /res\.data\.scoreId/)
  assert.match(view, /res\.data\.scoreVersion/)
  assert.match(view, /重新核算、独立复核并发布/)
})
