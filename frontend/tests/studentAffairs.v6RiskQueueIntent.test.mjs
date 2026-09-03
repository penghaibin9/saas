import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { resolveRiskQueueIntent } from '../src/modules/studentAffairs/utils/riskRouteQueueIntent.js'

const navPlan = fs.readFileSync(new URL('../src/config/navPlan.js', import.meta.url), 'utf8')
const riskView = fs.readFileSync(new URL('../src/modules/studentAffairs/views/StudentAffairsRiskListView.vue', import.meta.url), 'utf8')

const cases = [
  ['/admin/student-affairs/risk?priority=HIGH_CRITICAL', { priority: 'HIGH_CRITICAL' }, 'HIGH'],
  ['/admin/student-affairs/risk?overdueOnly=true', { overdueOnly: 'true' }, 'OVERDUE'],
  ['/admin/student-affairs/risk?unassignedOnly=true', { unassignedOnly: 'true' }, 'UNASSIGNED'],
  ['/admin/student-affairs/risk?ownerId=me', { ownerId: 'me' }, 'MINE'],
  ['/admin/student-affairs/risk?status=FOLLOWING', { status: 'FOLLOWING' }, 'FOLLOWING']
]

test('V6 risk deep links map to the existing queue filters', () => {
  for (const [path, query, queue] of cases) {
    assert.ok(navPlan.includes(path), path)
    assert.equal(resolveRiskQueueIntent(query), queue)
  }
  assert.equal(resolveRiskQueueIntent({}), 'ALL')
})

test('risk page consumes the shared route-intent resolver', () => {
  assert.match(riskView, /resolveRiskQueueIntent/)
  assert.match(riskView, /this\.activeQueue = resolveRiskQueueIntent\(q\)/)
  assert.match(riskView, /case 'HIGH': return \{ priority: 'HIGH_CRITICAL' \}/)
  assert.match(riskView, /case 'OVERDUE': return \{ overdueOnly: true \}/)
  assert.match(riskView, /case 'UNASSIGNED': return \{ unassignedOnly: true \}/)
  assert.match(riskView, /case 'MINE': return \{ ownerId: 'me' \}/)
  assert.match(riskView, /case 'FOLLOWING': return \{ status: 'FOLLOWING' \}/)
})

test('queue intent precedence is deterministic', () => {
  assert.equal(resolveRiskQueueIntent({ priority: 'HIGH_CRITICAL', overdueOnly: 'true' }), 'HIGH')
  assert.equal(resolveRiskQueueIntent({ overdueOnly: 'TRUE', ownerId: 'me' }), 'OVERDUE')
  assert.equal(resolveRiskQueueIntent({ unassignedOnly: true, ownerId: 'me' }), 'UNASSIGNED')
  assert.equal(resolveRiskQueueIntent({ status: 'closed' }), 'ALL')
})
