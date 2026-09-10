import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { createRouter, createMemoryHistory } from 'vue-router'
import { DASHBOARD_PANELS, dashboardPanel, dashboardTodoRows } from '../src/modules/academicAffairs/config/dashboardPanels.js'
import academicRoutes from '../src/modules/academicAffairs/routes/academic.routes.js'
import { NAV_PLAN } from '../src/config/navPlan.js'
import { academicIdentity } from '../src/modules/academicAffairs/academicFlowContext.js'
import { routeTarget } from '../src/modules/academicAffairs/components/leadershipWall/aa-wall-data.mjs'

function workspace(api, panel = 'todos', gate = () => true) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/components/AaDashboardPanelWorkspace.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { academicAffairsApi: api, DASHBOARD_PANELS, dashboardTodoRows, canEnterRoute: gate, academicStatusLabel: value => value, academicIdentity, routeTarget, currentUserFromToken: () => ({ tenantId: 'test-school', userId: 'test-user', currentRoleCode: 'ACADEMIC_ADMIN' }) } }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component, destinations = []
  const state = { panel, ctx: { ctxKey: 'school-a' }, $route: { path: '/admin/academic-affairs', query: { panel } }, $router: { push: target => destinations.push(target), resolve: () => ({ matched: [{ meta: { permissionKey: 'target-permission' } }], meta: { permissionKey: 'target-permission' } }) } }
  Object.assign(state, component.data.call(state), component.methods)
  for (const [key, getter] of Object.entries(component.computed)) Object.defineProperty(state, key, { get: () => getter.call(state) })
  return { state, component, destinations }
}

test('every dashboard menu panel resolves to a named workspace, and the root legacy address is retired', () => {
  const module = NAV_PLAN.flatMap(center => center.children || []).find(row => row.key === 'aa-dashboard')
  const paths = module.children.map(row => row.path)
  for (const path of paths) {
    const panel = new URL(path, 'https://local.test').searchParams.get('panel')
    if (panel) assert.equal(dashboardPanel(panel), panel)
  }
  assert.ok(paths.includes('/admin/academic-affairs?panel=academicProgress'))
  assert.ok(!paths.includes('/admin/academic'))
  assert.equal(dashboardPanel('unknown'), '')
  assert.equal(dashboardPanel(['todos']), '')
  const router = createRouter({ history: createMemoryHistory(), routes: academicRoutes })
  assert.ok(!router.getRoutes().some(row => row.path === '/admin/academic'))
  assert.ok(router.getRoutes().some(row => row.path === '/admin/academic/warnings'))
})

test('todo categories retain every returned task, exact IDs and destination, beyond the old 15 item cap', () => {
  const groups = [{ key: 'gradeReview', label: '审核', count: 21, items: Array.from({ length: 21 }, (_, i) => ({ businessId: `9007199254740993${i}`, exactRoute: `/review?taskId=9007199254740993${i}` })) }, { key: 'warningHandle', label: '预警', items: [{ businessId: 'w1' }] }]
  assert.equal(dashboardTodoRows(groups).length, 22)
  const filtered = dashboardTodoRows(groups, 'gradeReview')
  assert.equal(filtered.length, 21)
  assert.equal(filtered[20].exactRoute, groups[0].items[20].exactRoute)
  assert.equal(groups[0].items[0].categoryKey, undefined)
})

test('switching panels and categories creates distinct refreshable URLs', () => {
  const { state, destinations } = workspace({})
  state.selectCategory('warningHandle')
  assert.equal(destinations[0].query.category, 'warningHandle')
  state.switchPanel('todayTeaching')
  assert.equal(destinations[1].query.panel, 'todayTeaching')
  assert.equal(destinations[1].query.category, undefined)
  state.panel = 'academicProgress'
  assert.equal(state.definition.title, '学业过程')
})

test('real failures and restricted scopes are preserved instead of fake empty successes', async () => {
  const { state } = workspace({ getDashboardReminders: async () => ({ code: 403, message: '无权限' }) })
  state.data = { todayTeaching: { totalToday: 99 } }
  await state.load()
  assert.equal(state.error, '无权限')
  assert.equal(state.data.todayTeaching, undefined)
  const restricted = workspace({ getDashboardReminders: async () => ({ code: 0, data: { scopeRestricted: true, todos: [] } }) })
  await restricted.state.load()
  assert.equal(restricted.state.data.scopeRestricted, true)
})

test('a previous context response cannot overwrite the new context or unmounted workspace', async () => {
  const pending = []
  const { state, component } = workspace({ getDashboardReminders: () => new Promise(resolve => pending.push(resolve)) })
  const first = state.load(), second = state.load()
  pending[1]({ code: 0, data: { marker: 'current', scopeRestricted: false } }); await second
  pending[0]({ code: 0, data: { marker: 'stale', scopeRestricted: false } }); await first
  assert.equal(state.data.marker, 'current')
  const third = state.load(); component.beforeUnmount.call(state)
  pending[2]({ code: 0, data: { marker: 'unmounted' } }); await third
  assert.equal(state.data.marker, undefined)
})

test('grade progress separates saved records from completion and preserves exact task IDs', () => {
  const { state } = workspace({}, 'gradeProgress')
  state.data = { gradeProgress: { totalTasks: 9, counts: { INPUTTING: 4, SUBMITTED: 2, ACADEMIC_REVIEW: 1, PUBLISHED: 2 }, pendingTasks: [{ gradeTaskId: '9007199254740993123', enteredCount: 0, rosterCount: 36, status: 'INPUTTING' }] } }
  assert.equal(state.submittedTasks, 5)
  assert.equal(state.gradeRows[0].enteredCount, 0)
  assert.ok(state.gradeRows[0].target.endsWith('taskId=9007199254740993123'))
  assert.equal(state.gradeStages.find(item => item.key === 'RETURNED').count, 0)
  state.data.gradeProgress.counts = { SUBMITTED: 'unknown' }
  assert.equal(state.submittedTasks, null)
})

test('business reminders expose their own fields and a real all-zero trend remains chartable', () => {
  const { state } = workspace({}, 'warningReminders')
  state.data = { warningReminders: { items: [{ warningId: '1', studentName: '测试学生', level: 'HIGH', owner: '正式负责人', reason: '正式预警依据' }] } }
  assert.ok(state.businessColumns.some(item => item.key === 'owner'))
  assert.equal(state.detailRows[0].riskLabel, '高风险')
  assert.equal(state.detailRows[0].owner, '正式负责人')
  state.panel = 'resourceOccupancy'
  assert.ok(state.businessColumns.some(item => item.key === 'useCount'))
  state.panel = 'dataTrends'
  state.data.dataTrends = { series: [{ label: '学籍异动', points: [{ date: '2026-09-09', value: 0 }] }] }
  assert.equal(state.trendHasData, true)
})

test('zero denominator remains unknown and today uses the backend schedule state', () => {
  const { state } = workspace({}, 'todayTeaching')
  state.data = { todayTeaching: { totalToday: 0, inProgress: 0 }, todayCourses: { items: [{ itemId: '90071992547409939', slotNo: 2, runStatusLabel: '未开始', changed: true }] } }
  assert.equal(state.todayMetrics[0].value, 0)
  assert.equal(state.courseRows[0].itemId, '90071992547409939')
  assert.equal(state.courseRows[0].state, '未开始 · 已调课')
  state.panel = 'resourceOccupancy'
  assert.equal(state.summaryValue, '—')
})

test('drilldown uses the existing route permission gate and never bypasses a refusal', () => {
  let calls = 0
  const { state, destinations } = workspace({}, 'todos', meta => { calls++; assert.equal(meta.permissionKey, 'target-permission'); return false })
  state.go('/admin/academic-affairs/grade-entry?taskId=1')
  assert.equal(calls, 1)
  assert.equal(destinations.length, 0)
  state.$router.resolve = () => ({ matched: [] })
  assert.equal(state.canOpen('/missing'), false)
})
