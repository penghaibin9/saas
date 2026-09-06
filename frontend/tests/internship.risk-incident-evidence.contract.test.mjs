import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8')

test('Staff risk card shows canonical source, latest event, current action and durable receipt', () => {
  const view = read('frontend/src/modules/internship/views/RiskDisposalView.vue')
  for (const token of ['ActionReceipt', 'sourceType', 'sourceId', 'latestEvent', 'currentAction', 'closeBlockers']) {
    assert.match(view, new RegExp(token))
  }
  assert.match(view, /expectedVersion: d\.version/)
  assert.match(view, /业务事实与审计 outbox 已在同一事务提交/)
})

test('Staff incident workbench explains close blockers and leads to regulatory evidence package', () => {
  const view = read('frontend/src/modules/internship/views/InternshipComplianceView.vue')
  assert.match(view, /编号 \/ 风险源/)
  assert.match(view, /row\.latestEvent/)
  assert.match(view, /row\.currentAction/)
  assert.match(view, /row\.closeBlockers/)
  assert.match(view, /target === 'CLOSED' && !row\.closeAllowed/)
  assert.match(view, /generateIncidentEvidence/)
  assert.match(view, /fileIds: dialog\.fileIds/)
  assert.match(view, /incidentRows/)
  assert.match(view, /ActionReceipt/)
})

test('Teacher Mini uses server versions, source facts, conflict draft and receipt', () => {
  const view = read('miniapp/src/pages/teacher/internship-risk/index.vue')
  assert.match(view, /sourceText\(r\)/)
  assert.match(view, /r\.latestEvent/)
  assert.match(view, /r\.currentAction/)
  assert.match(view, /r\.closeAllowed !== false/)
  assert.ok((view.match(/expectedVersion: r\.version/g) || []).length >= 3)
  assert.match(view, /this\.drafts\[r\.id\]/)
  assert.match(view, /lastReceipt/)
})

test('Complaint writes carry expectedVersion and expose explicit follow-up', () => {
  const api = read('frontend/src/modules/internship/api/leave-risk.api.js')
  const view = read('frontend/src/modules/internship/views/RiskDisposalView.vue')
  assert.match(api, /toRisk\(id, expectedVersion\)/)
  assert.match(api, /followup\(id, result, expectedVersion\)/)
  assert.match(view, /openComplaintAction\('FOLLOWUP'\)/)
  assert.match(view, /complaintApi\.followup\(p\.id, reason, p\.expectedVersion\)/)
})
