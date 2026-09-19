import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { STATS_TOPICS, statsTopic } from '../src/modules/academicAffairs/config/academicNavigation.js'
import { matchPermission } from '../src/config/navPlan.js'
import { academicIdentity } from '../src/modules/academicAffairs/academicFlowContext.js'

function page(api = {}, query = {}) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaStatsOverviewView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const messages = [], destinations = []
  const sandbox = { dependencies: { STATS_TOPICS, statsTopic, matchPermission, academicIdentity, currentUserFromToken: () => ({ tenantId: 'test-school', userId: 'test-user', currentRoleCode: 'ACADEMIC_ADMIN' }), academicAffairsApi: api, toast: { error: message => messages.push(message), success() {} } } }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const state = { ctx: { ctxKey: 'school-a', permissionPatterns: ['*'] }, $route: { path: '/admin/academic-affairs/stats', query }, $router: { push: to => destinations.push(to) } }
  Object.assign(state, component.data.call(state), component.methods)
  for (const [key, getter] of Object.entries(component.computed)) Object.defineProperty(state, key, { get: () => getter.call(state) })
  return { state, component, destinations, messages }
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('all 15 existing statistics dimensions belong to exactly one of seven topics', () => {
  const { state } = page()
  assert.equal(STATS_TOPICS.length, 7)
  assert.deepEqual(new Set(STATS_TOPICS.flatMap(topic => topic.tabs)), new Set(state.TABS.map(tab => tab.key)))
  assert.equal(STATS_TOPICS.flatMap(topic => topic.tabs).length, state.TABS.length)
})

test('switching dimensions preserves scope and string IDs in a refreshable URL', () => {
  const { state, destinations } = page({}, { scope: 'roster', _workspace: 'old-menu' })
  state.filters.termId = '9007199254740993123'
  state.switchTab('grade')
  assert.equal(destinations[0].query.tab, 'grade')
  assert.equal(destinations[0].query.scope, 'roster')
  assert.equal(destinations[0].query.termId, '9007199254740993123')
  assert.equal(destinations[0].query._workspace, undefined)
  state.switchTab('unknown')
  assert.equal(destinations.length, 1)
})

test('refresh and browser history restore the selected dimension and filters', () => {
  const { state, component } = page({}, { tab: 'courseSelection', termId: '123', collegeId: '456' })
  let loads = 0
  state.loadTab = () => loads++
  state.restoreRoute()
  assert.equal(state.tab, 'courseSelection')
  assert.equal(state.currentTopic.key, 'teaching')
  assert.equal(state.filters.termId, '123')
  state.$route.query = { tab: 'registration' }
  component.watch['$route.query'].handler.call(state)
  assert.equal(state.tab, 'registration')
  assert.equal(state.filters.termId, '')
  assert.equal(loads, 2)
})

test('late results from a previous topic cannot replace current statistics', async () => {
  const old = deferred()
  const { state } = page({ getStatsOverview: () => old.promise, getStatsWorkload: async () => ({ code: 0, data: { ranking: [{ teacherKey: 'new' }] } }) })
  const pending = state.loadTab()
  state.tab = 'workload'
  await state.loadTab()
  old.resolve({ code: 0, data: { indicators: [{ key: 'stale' }] } })
  await pending
  assert.equal(state.indicators.length, 0)
  assert.equal(state.sSummary.ranking[0].teacherKey, 'new')
  assert.equal(state.loading, false)
})

test('request failure clears old facts and remains an error, not a zero result', async () => {
  const { state } = page({ getStatsOverview: async () => { throw new Error('网络中断') } })
  state.indicators = [{ key: 'registration', rate: 99 }]
  await state.loadTab()
  assert.equal(state.error, '网络中断')
  assert.equal(state.indicators.length, 0)
  assert.equal(state.loading, false)
  assert.equal(state.updatedAt, '')
})

test('scope denial is retained and a legitimate zero denominator remains null', async () => {
  const { state } = page({ getStatsOverview: async () => ({ code: 0, data: { indicators: [{ key: 'registration', rate: null, denominator: 0 }], scope: { blocked: true } } }) })
  await state.loadTab()
  assert.equal(state.scopeBlocked, true)
  assert.equal(state.indicators[0].rate, null)
})

test('overview sections preserve every received metric including future additions', () => {
  const { state } = page()
  state.indicators = [{ key: 'registration' }, { key: 'exam' }, { key: 'graduation' }, { key: 'futureMetric' }]
  const displayed = state.overviewSections.flatMap(group => group.items)
  assert.equal(displayed.length, 4)
  assert.deepEqual(new Set(displayed.map(item => item.key)), new Set(state.indicators.map(item => item.key)))
})

test('workload drilldown keeps teacher and filters when paging and exposes request failure', async () => {
  const calls = []
  const { state } = page({ getStatsWorkloadDetail: async params => { calls.push(params); return params.page === 2 ? { code: 500, message: '明细服务不可用' } : { code: 0, data: { list: [{ taskId: 't1' }], total: 24 } } } })
  state.tab = 'workload'; state.appliedFilters.termId = 'term-a'
  state.$route.query = { tab: 'workload', termId: 'term-a', teacherKey: 'teacher-a' }
  state.restoreDetailRoute()
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.equal(state.detail.rows.length, 1)
  state.detail.pagination.page = 2
  await state.loadDetail()
  assert.equal(calls[1].teacherKey, 'teacher-a')
  assert.equal(calls[1].termId, 'term-a')
  assert.equal(calls[1].page, 2)
  assert.equal(state.detail.error, '明细服务不可用')
  assert.equal(state.detail.rows.length, 0)
})

test('failed export preserves input, releases processing state and keeps large IDs exact', async () => {
  let sent
  const { state, messages } = page({ exportStats: async params => { sent = params; throw new Error('下载失败') } })
  state.exp.purpose = '教务处月度汇报'; state.exp.termId = '9007199254740993123'
  await state.doExport()
  assert.equal(sent.termId, '9007199254740993123')
  assert.equal(state.exp.purpose, '教务处月度汇报')
  assert.equal(state.exp.downloading, false)
  assert.equal(messages[0], '下载失败')
})

test('view-only users cannot expose report actions or call export; snapshot permission is separate', async () => {
  let writes = 0
  const { state } = page({ exportStats: async () => { writes++ } })
  state.ctx.permissionPatterns = ['academicAffairs.stats.view']
  assert.equal(state.canExport, false)
  assert.equal(state.canViewSnapshot, false)
  assert.equal(state.visibleTopics.some(topic => topic.key === 'reports'), false)
  state.exp.purpose = '教务处月度汇报'
  await state.doExport()
  assert.equal(writes, 0)
  state.tab = 'export'
  await state.loadTab()
  assert.equal(state.error, '当前账号没有报表导出权限')
  state.ctx.permissionPatterns.push('academicAffairs.stats.snapshot.view')
  assert.equal(state.canViewSnapshot, true)
  assert.equal(state.canExport, false)
})

test('editing a filter does not change the scope of already displayed statistics or their drilldown', async () => {
  let sent
  const { state } = page({ getStatsWorkloadDetail: async params => { sent = params; return { code: 0, data: { list: [], total: 0 } } } })
  state.tab = 'workload'; state.workloadTeacherKey = 'teacher-a'
  state.appliedFilters.termId = 'applied-term'; state.filters.termId = 'draft-term'
  await state.loadDetail()
  assert.equal(sent.termId, 'applied-term')
  assert.equal(state.filtersDirty, true)
})

test('teacher drilldown and page survive refresh without coercing the teacher key', async () => {
  const calls = []
  const { state } = page({
    getStatsWorkload: async () => ({ code: 0, data: { ranking: [] } }),
    getStatsWorkloadDetail: async params => { calls.push(params); return { code: 0, data: { list: [], total: 45 } } }
  }, { tab: 'workload', termId: 'term-a', teacherKey: '9007199254740993123', detailPage: '3' })
  state.restoreRoute()
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.equal(state.detail.open, true)
  assert.equal(calls[0].teacherKey, '9007199254740993123')
  assert.equal(calls[0].page, 3)
  assert.equal(calls[0].termId, 'term-a')
})

test('opening a teacher and changing pages keeps the original applied URL and return context', () => {
  const { state, destinations } = page({}, { tab: 'workload', termId: 'applied-term', returnToken: 'return-a' })
  state.tab = 'workload'; state.filters.termId = 'draft-term'
  state.viewWorkloadDetail({ teacherKey: 'teacher-a' })
  assert.equal(destinations[0].query.teacherKey, 'teacher-a')
  assert.equal(destinations[0].query.termId, 'applied-term')
  assert.equal(destinations[0].query.returnToken, 'return-a')
  state.workloadTeacherKey = 'teacher-a'; state.onDetailPage(2)
  assert.equal(destinations[1].query.detailPage, '2')
  assert.equal(destinations[1].query.termId, 'applied-term')
})

test('malformed detail pagination remains an error and clears the previous total', async () => {
  const { state } = page({ getStatsWorkloadDetail: async () => ({ code: 0, data: {} }) })
  state.tab = 'workload'; state.workloadTeacherKey = 'teacher-a'; state.detail.pagination.total = 99
  await state.loadDetail()
  assert.match(state.detail.error, /分页回执不完整/)
  assert.equal(state.detail.pagination.total, 0)
  assert.equal(state.detail.rows.length, 0)
})

test('overview analysis keeps legitimate zero groups and never invents a missing indicator value', () => {
  const { state } = page()
  state.indicators = [{ key: 'warning', label: '学业预警', value: 0, groups: [{ key: 'HIGH', count: 0 }] }, { key: 'future', label: '未返回值' }]
  assert.equal(state.overviewRows.length, 2)
  assert.equal(state.distributionOptions.length, 1)
  assert.equal(state.overviewDistributionSpec.data[0].value, 0)
  assert.equal(state.indicatorValue(state.indicators[0]), '0')
  assert.equal(state.indicatorValue(state.indicators[1]), '—')
  assert.equal(state.indicatorValue({ unit: '%', rate: null, denominator: 0 }), '—')
})

test('overview records the actual source time and rejects a missing indicator list', async () => {
  const { state } = page({ getStatsOverview: async () => ({ code: 0, data: { indicators: [], asOf: '2026-09-09T03:40:00' } }) })
  await state.loadTab()
  assert.equal(state.sourceAsOf, '2026-09-09 03:40:00 UTC')
  const invalid = page({ getStatsOverview: async () => ({ code: 0, data: {} }) }).state
  await invalid.loadTab()
  assert.match(invalid.error, /统计指标回执不完整/)
})
