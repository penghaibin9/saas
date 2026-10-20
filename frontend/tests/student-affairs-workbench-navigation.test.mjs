import test from 'node:test'
import assert from 'node:assert/strict'
import { NAV_PLAN, getVisibleNavPlan, findActiveInPlan } from '../src/config/navPlan.js'
import { WORKBENCH_PAGE_TABS, workbenchSection } from '../src/modules/workbench/config/workbenchNavigation.js'
import { restoreWorkspace, workspacePages } from '../src/components/workspace/teacherWorkspace.js'
import { domainMetric, occupancyRate } from '../src/modules/studentAffairs/views/leadershipScreen.js'

test('workbench belongs to student affairs with both wall entries and no extra primary center', () => {
  assert.ok(!NAV_PLAN.some(group => group.key === 'workbench'))
  const group = getVisibleNavPlan({ permissionPatterns: ['*'] }).find(group => group.key === 'student-affairs')
  assert.equal(group.children[0].key, 'sa-workbench')
  assert.deepEqual(group.children[0].children.map(page => page.label), ['我的工作台', '我的待办', '审批中心', '消息中心', '学工运行大屏', '学工领导大屏', '最近访问', '帮助中心'])
  for (const route of ['/workbench', '/admin/approval/done', '/admin/messages/ops', '/admin/help', '/admin/student-affairs/stats/wall', '/admin/student-affairs/stats/leader']) {
    const match = findActiveInPlan(route)
    assert.equal(match.groupKey, 'student-affairs', route)
    assert.equal(match.modKey, 'sa-workbench', route)
  }
})
test('migrated navigation retains permission boundaries and the existing message/approval routes', () => {
  const group = getVisibleNavPlan({ permissionPatterns: ['workbench.home.view'] }).find(group => group.key === 'student-affairs')
  assert.deepEqual(group.children[0].children.map(page => page.label), ['我的工作台', '最近访问', '帮助中心'])
  for (const route of ['/admin/approval/templates', '/admin/approval/returned', '/admin/messages/compose', '/admin/messages/outbox', '/admin/messages/settings', '/admin/messages/ops']) {
    assert.ok(WORKBENCH_PAGE_TABS.some(page => page.path === route && page.permissionKey))
  }
  assert.equal(workbenchSection('/admin/messages/outbox/42'), 'messages')
  assert.equal(workbenchSection('/admin/approval/todos/10'), 'approval')
  assert.equal(workbenchSection('/admin/messages-unrelated'), '')
})
test('recent visits never restore removed permission routes or arbitrary sensitive queries', () => {
  const pages = workspacePages(getVisibleNavPlan({ permissionPatterns: ['workbench.home.view'] }).find(group => group.key === 'student-affairs').children)
  const prefs = restoreWorkspace({ recent: ['/workbench', '/admin/messages/ops', '/workbench?studentName=甲', '/workbench'] }, pages)
  assert.deepEqual(prefs.recent, ['/workbench'])
})
test('leadership metrics preserve actual zero and do not turn missing/error values into zero', () => {
  const domains = [{ key: 'risk', status: 'ERROR', total: 0 }, { key: 'student', status: 'OK', total: 0 }, { key: 'funding', status: 'OK', metrics: {} }]
  assert.equal(domainMetric(domains, 'risk'), null)
  assert.equal(domainMetric(domains, 'student'), 0)
  assert.equal(domainMetric(domains, 'funding', 'granted'), null)
  assert.equal(domainMetric(domains, 'missing'), null)
})
test('occupancy uses bed counts with a valid denominator, never student totals', () => {
  const domain = { key: 'dorm', status: 'OK', total: 80, metrics: { occupiedBeds: 60 } }
  assert.equal(occupancyRate([domain]), 75)
  assert.equal(occupancyRate([{ ...domain, total: 0 }]), null)
  assert.equal(occupancyRate([{ ...domain, total: 50 }]), null)
  assert.equal(occupancyRate([{ ...domain, status: 'DEGRADED' }]), null)
})
