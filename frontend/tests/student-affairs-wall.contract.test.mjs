import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { WALL_METRICS, WALL_ROUTES } from '../src/modules/studentAffairs/config/studentAffairsWall.contract.js'
import { projectStudentAffairsWall, wallPacket } from '../src/modules/studentAffairs/composables/studentAffairsWallProjection.js'

const dashboard = {
  status: 'OK',
  data: {
    scopeMode: 'SCOPED', scopeLabel: '本人负责范围', updatedAt: '2026-09-07T10:00:00Z',
    summaryCards: [
      { key: 'studentTotal', value: 20 }, { key: 'classTotal', value: 3 },
      { key: 'pendingLeave', value: 0 }, { key: 'overdueLeave', value: 2 },
      { key: 'pendingAid', value: 4 }, { key: 'pendingFunding', value: 5 },
      { key: 'pendingDiscipline', value: 1 }
    ],
    riskSummary: { openStudentCount: 6 }
  }
}
const domains = [
  { key: 'risk', status: 'OK', metrics: { total: 12, open: 7, highCritical: 3, overdue: 2, unassigned: 1 } },
  { key: 'dorm', status: 'OK', metrics: { totalBeds: 10, occupiedBeds: 8, vacantBeds: 1, lockedBeds: 1 } },
  { key: 'aid', status: 'OK', metrics: { total: 9, approved: 5 } },
  { key: 'funding', status: 'OK', metrics: { total: 11, granted: 7 } },
  { key: 'workStudy', status: 'OK', metrics: { pending: 2, onboard: 4 } },
  { key: 'activity', status: 'OK', metrics: { totalActivities: 3, creditStudents: 8 } },
  { key: 'talk', status: 'OK', metrics: { total: 6, completed: 5 } },
  { key: 'family', status: 'OK', metrics: { total: 4, pendingReceipt: 1 } },
  { key: 'archive', status: 'OK', metrics: { total: 18, pending: 2 } },
  { key: 'leave', status: 'OK', metrics: { pendingReview: 0, waitCancel: 2, overdue: 2, closed: 5 } }
]

test('wall projection keeps zero, record semantics and safe derived values', () => {
  const result = projectStudentAffairsWall({ dashboard, cockpit: { status: 'OK', data: { domains, updatedAt: '2026-09-07T10:01:00Z' } }, leaveTypes: { status: 'OK', data: { groupBy: 'TYPE', breakdown: [{ label: '事假', count: 2 }] } } })
  assert.equal(result.metrics.pendingLeave.value, 0)
  assert.equal(result.metrics.riskStudents.value, 6)
  assert.equal(result.metrics.riskTotal.value, 12)
  assert.equal(result.metrics.riskClosed.value, 5)
  assert.equal(result.metrics.occupancy.value, 80)
  assert.equal(result.breakdown[0].value, 2)
})

test('wall projection fails closed for no scope, restricted packets and domain errors', () => {
  const noScope = projectStudentAffairsWall({ dashboard: { ...dashboard, data: { ...dashboard.data, scopeMode: 'NONE' } }, cockpit: { status: 'OK', data: { domains } } })
  assert.equal(noScope.metrics.students.status, 'NO_SCOPE')
  assert.equal(noScope.metrics.students.value, null)
  const restricted = projectStudentAffairsWall({ dashboard: { status: 'RESTRICTED' }, cockpit: { status: 'OK', data: { domains: [{ key: 'dorm', status: 'ERROR', metrics: {} }] } } })
  assert.equal(restricted.metrics.students.status, 'RESTRICTED')
  assert.equal(restricted.metrics.occupied.status, 'ERROR')
  assert.equal(restricted.metrics.occupancy.value, null)
  assert.equal(wallPacket({ code: 403001 }).status, 'RESTRICTED')
  assert.equal(wallPacket({ code: 403002 }).status, 'NO_SCOPE')
})

test('wall contract keeps canonical routes and never exposes psychological detail metrics', () => {
  for (const definition of WALL_METRICS) {
    assert.ok(WALL_ROUTES[definition.route], `${definition.id} must have a real drilldown target`)
    assert.ok(definition.note, `${definition.id} must explain its counting scope`)
  }
  assert.equal(WALL_ROUTES.student.path, '/admin/student/list')
  assert.equal(WALL_ROUTES.riskOpen.path, '/admin/student-affairs/risk?status=OPEN')
  assert.equal(WALL_ROUTES.aidReview.permission, 'studentAffairs.aid.view')
  assert.ok(WALL_METRICS.some(item => item.id === 'occupied' && /不是实时在寝/.test(item.note)))
  assert.ok(!WALL_METRICS.some(item => item.id.toLowerCase().includes('mental')))
})

test('explicit no-scope context overrides a dashboard scope label and domain denials stay distinct', () => {
  const result = projectStudentAffairsWall({ dashboard, context: { dataScope: { scopeType: 'NONE' } }, cockpit: { status: 'OK', data: { domains } } })
  assert.equal(result.metrics.students.status, 'NO_SCOPE')
  assert.equal(result.metrics.occupied.value, null)
  const denied = projectStudentAffairsWall({ cockpit: { status: 'OK', data: { domains: [{ key: 'dorm', status: 'RESTRICTED' }] } } })
  assert.equal(denied.metrics.occupied.status, 'RESTRICTED')
  const duplicate = projectStudentAffairsWall({ cockpit: { status: 'OK', data: { domains: [...domains, domains[1]], domainsByKey: { dorm: domains[1] } } } })
  assert.equal(duplicate.metrics.occupied.status, 'INVALID')
})

test('both wall routes use the existing statistics permission and one shared data layer', () => {
  const routes = fs.readFileSync(new URL('../src/modules/studentAffairs/studentAffairs.routes.js', import.meta.url), 'utf8')
  const nav = fs.readFileSync(new URL('../src/config/navPlan.js', import.meta.url), 'utf8')
  const runtime = fs.readFileSync(new URL('../src/modules/studentAffairs/views/StudentAffairsWallView.vue', import.meta.url), 'utf8')
  const leader = fs.readFileSync(new URL('../src/modules/studentAffairs/views/StudentAffairsLeaderWallView.vue', import.meta.url), 'utf8')
  for (const path of ['stats/wall', 'stats/leader']) assert.match(routes, new RegExp(`path: '${path}'[\\s\\S]{0,280}permissionKey: 'studentAffairs\\.stats\\.view'`))
  assert.match(nav, /学工运行大屏.*\/admin\/student-affairs\/stats\/wall/)
  assert.match(nav, /学工领导大屏.*\/admin\/student-affairs\/stats\/leader/)
  assert.match(runtime, /useStudentAffairsWallData/)
  assert.match(leader, /useStudentAffairsWallData/)
})
