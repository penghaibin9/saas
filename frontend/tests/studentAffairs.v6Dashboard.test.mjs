import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { setImmediate } from 'node:timers'

// Execute the actual page logic; replace only IO and component/permission collaborators.
const source = fs.readFileSync(new URL('../src/modules/studentAffairs/views/StudentAffairsDashboardView.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]*\n/gm, '').replace('export default', 'globalThis.pageOptions =')
const keys = ['studentTotal', 'classTotal', 'pendingTodo', 'pendingLeave', 'overdueLeave', 'pendingAid', 'pendingFunding', 'pendingDiscipline', 'riskStudents']
const readyData = (values = {}) => ({ view: 'COUNSELOR', viewLabel: '辅导员', scopeMode: 'SCOPED', scopeType: 'CLASS', scopeLabel: '负责班级',
  summaryCards: keys.map((key) => ({ key, value: values[key] ?? 0 })), riskSummary: { highCount: 0, criticalCount: 0, topRiskLevel: 'NONE' } })
const tick = () => new Promise((resolve) => setImmediate(resolve))
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
function createPage(overrides = {}, context = { permissionPatterns: ['*'], rbacOk: true, ctxKey: 'tenant-a:teacher-a' }) {
  const calls = { dashboard: 0, audit: 0, routes: [], exports: [] }
  const api = {
    getDashboard: async () => { calls.dashboard++; return { code: 0, data: readyData() } },
    getAuditLogs: async () => { calls.audit++; return { code: 0, data: [] } },
    exportProfileLedger: (options) => { calls.exports.push(options); return Promise.resolve('xlsx') }, ...overrides
  }
  const env = { studentAffairsApi: api, canCode: (ctx, code) => ctx.permissionPatterns.includes('*') || ctx.permissionPatterns.includes(code) }
  for (const name of ['AppAuditTrail', 'AppDateDisplay', 'AppExportButton', 'AppGlobalState', 'AppPageShell', 'AppPermissionButton', 'AppRiskTag', 'AppSectionCard', 'AppStatusTag']) env[name] = {}
  vm.runInNewContext(script, env, { filename: 'StudentAffairsDashboardView.vue', timeout: 1000 })
  const options = env.pageOptions
  const page = { ...options.data(), ctx: context, $router: { push: (path) => calls.routes.push(path) } }
  for (const [name, method] of Object.entries(options.methods)) page[name] = method.bind(page)
  for (const [name, getter] of Object.entries(options.computed)) Object.defineProperty(page, name, { get: () => getter.call(page) })
  return { page, calls, options }
}
function setReady(page, data = readyData()) { page.dashboard = data; page.loading = false; page.loadedContext = page.contextKey }

test('unknown and malformed counts are not zero', () => {
  const { page } = createPage()
  for (const value of [undefined, null, '', ' ', false, true, [], {}, NaN, Infinity, -1, 1.5, '1x', '1e3', '-1', Number.MAX_SAFE_INTEGER + 1]) {
    assert.equal(page.toCount(value), null, String(value)); assert.equal(page.formatCount(value), '—', String(value))
  }
  for (const [value, expected] of [[0, 0], ['0', 0], [42, 42], ['123456', 123456]]) assert.equal(page.toCount(value), expected)
  assert.equal(page.formatCount(123456), '123,456')
})
test('missing metric has no green zero state', () => {
  const { page } = createPage(); const data = readyData(); data.summaryCards = data.summaryCards.filter((card) => card.key !== 'pendingLeave'); setReady(page, data)
  const row = page.businessQueues.find((item) => item.key === 'pendingLeave')
  assert.equal(row.count, null); assert.equal(row.statusLabel, '汇总未取得'); assert.notEqual(row.statusType, 'success')
  assert.equal(page.hasMissingMetrics, true); assert.match(page.heroConclusion, /暂未取得/)
})
test('known zero and positive counts have distinct states', () => {
  const { page } = createPage(); setReady(page, readyData({ pendingLeave: 9 }))
  assert.equal(page.businessQueues.length, 7); assert.equal(page.businessQueues.find((row) => row.key === 'pendingLeave').count, 9)
  assert.equal(page.businessQueues.find((row) => row.key === 'pendingTodo').statusLabel, '当前无事项'); assert.equal(page.hasMissingMetrics, false)
})
test('missing risk summary never becomes LOW or known zero', () => {
  const { page } = createPage(); const data = readyData({ riskStudents: 3 }); delete data.riskSummary; setReady(page, data)
  assert.equal(page.highRiskCount, null); assert.equal(page.criticalRiskCount, null); assert.equal(page.riskLevel, '')
  assert.equal(page.hasMissingMetrics, true); assert.doesNotMatch(page.heroConclusion, /暂无|清零/)
})
test('critical risk takes precedence without summing unique students', () => {
  const { page } = createPage(); const data = readyData({ riskStudents: 3, overdueLeave: 2 }); data.riskSummary = { criticalCount: 2, highCount: 3, topRiskLevel: 'CRITICAL' }; setReady(page, data)
  assert.equal(page.criticalRiskCount, 2); assert.equal(page.highRiskCount, 3); assert.equal(page.cardValue('riskStudents'), 3)
  assert.match(page.heroConclusion, /2 名危急风险学生/); assert.equal(page.riskLevel, 'CRITICAL')
})
test('missing or failed permission context fails closed before fetching', async () => {
  for (const ctx of [null, {}, { permissionPatterns: [] }, { permissionPatterns: ['*'], rbacOk: false }]) {
    const { page, calls } = createPage({}, ctx); await page.load()
    assert.equal(page.pageState, 'forbidden'); assert.equal(calls.dashboard, 0); assert.equal(calls.audit, 0)
  }
})
test('all real no-scope shapes disable navigation and audit', async () => {
  for (const field of [{ scopeMode: 'NONE' }, { scopeType: 'NONE' }, { scopeLabel: '无数据范围' }]) {
    const { page, calls } = createPage({ getDashboard: async () => ({ code: 0, data: { ...readyData(), ...field } }) }); await page.load()
    assert.equal(page.pageState, 'empty'); assert.match(page.stateTitle, /数据范围/); assert.equal(page.cardPath('riskStudents'), '')
    assert.equal(calls.audit, 0); assert.equal(page.highFrequencyEntries.length, 0)
  }
})
test('slow audit does not hold the dashboard in loading', async () => {
  const audit = deferred(); const { page } = createPage({ getAuditLogs: () => audit.promise }); await page.load()
  assert.equal(page.pageState, 'ready'); assert.equal(page.auditLoading, true)
  audit.resolve({ code: 0, data: [{ id: 'event' }] }); await tick(); assert.equal(page.auditLoading, false); assert.equal(page.auditLogs[0].id, 'event')
})
test('audit failure is local and cannot masquerade as successful emptiness', async () => {
  const { page } = createPage({ getAuditLogs: async () => { throw new Error('unavailable') } }); await page.load(); await tick()
  assert.equal(page.pageState, 'ready'); assert.equal(page.auditUnavailable, true); assert.equal(page.auditLoading, false); assert.match(source, /<AppAuditTrail v-else/)
})
test('malformed audit response is an explicit failure', async () => {
  const { page } = createPage({ getAuditLogs: async () => ({ code: 0, data: null }) }); await page.load(); await tick()
  assert.equal(page.auditUnavailable, true); assert.equal(page.pageState, 'ready')
})
test('malformed dashboard clears previous results', async () => {
  for (const result of [null, { code: 0, data: null }, { code: 0, data: {} }, { code: 0, data: { summaryCards: [null] } }, { code: 0, data: { summaryCards: 'bad' } }]) {
    const { page } = createPage({ getDashboard: async () => result }); setReady(page, readyData({ pendingTodo: 987 })); await page.load()
    assert.equal(page.pageState, 'error'); assert.equal(page.cardValue('pendingTodo'), null); assert.equal(page.dashboard.summaryCards.length, 0); assert.notEqual(page.stateTitle, '')
  }
})
test('valid empty array is distinct from invalid response', async () => {
  const { page } = createPage({ getDashboard: async () => ({ code: 0, data: { summaryCards: [] } }) }); await page.load()
  assert.equal(page.pageState, 'empty'); assert.equal(page.errorMessage, '')
})
test('403 is forbidden and 503 is error without stale content', async () => {
  for (const code of [403, 403001, 503]) {
    const { page } = createPage({ getDashboard: async () => { throw Object.assign(new Error('failure'), { code }) } }); setReady(page, readyData({ pendingTodo: 19 })); await page.load()
    assert.equal(page.pageState, code === 503 ? 'error' : 'forbidden'); assert.equal(page.cardValue('pendingTodo'), null)
  }
})
test('refresh clears content synchronously and remounts retained shared state', async () => {
  const pending = deferred(); const { page } = createPage({ getDashboard: () => pending.promise }); setReady(page, readyData({ pendingTodo: 19 })); const id = page.requestId; const loading = page.load()
  assert.equal(page.pageState, 'loading'); assert.equal(page.cardValue('pendingTodo'), null); assert.ok(page.requestId > id)
  assert.match(source, /:key="requestId"/); assert.match(source, /v-if="pageState === 'ready'"/)
  pending.resolve({ code: 0, data: readyData() }); await loading
})
test('only newest overlapping dashboard response applies', async () => {
  const first = deferred(), second = deferred(); let count = 0; const { page } = createPage({ getDashboard: () => ++count === 1 ? first.promise : second.promise })
  const a = page.load(), b = page.load(); second.resolve({ code: 0, data: readyData({ pendingTodo: 2 }) }); await b
  first.resolve({ code: 0, data: readyData({ pendingTodo: 99 }) }); await a; assert.equal(page.cardValue('pendingTodo'), 2); assert.equal(page.pageState, 'ready')
})
test('old failure cannot destroy newer ready result', async () => {
  const first = deferred(), second = deferred(); let count = 0; const { page } = createPage({ getDashboard: () => ++count === 1 ? first.promise : second.promise })
  const a = page.load(), b = page.load(); second.resolve({ code: 0, data: readyData() }); await b; first.reject(new Error('old')); await a
  assert.equal(page.pageState, 'ready'); assert.equal(page.errorMessage, '')
})
test('identity change rejects old response and clears data synchronously', async () => {
  const old = deferred(); const { page, options } = createPage({ getDashboard: () => old.promise }); const loading = page.load()
  page.ctx = { permissionPatterns: [], rbacOk: true, ctxKey: 'tenant-b:other' }; await options.watch.contextKey.handler.call(page)
  old.resolve({ code: 0, data: readyData({ pendingTodo: 777 }) }); await loading
  assert.equal(page.pageState, 'forbidden'); assert.equal(page.cardValue('pendingTodo'), null); assert.equal(options.watch.contextKey.flush, 'sync')
})
test('scope change invalidates loaded content even before watcher fires', () => {
  const { page } = createPage(); setReady(page); page.ctx.dataScope = { scopeType: 'CLASS', classIds: ['different'] }
  assert.equal(page.pageState, 'loading'); assert.equal(page.cardPath('pendingTodo'), '')
})
test('unmount invalidates outstanding response', async () => {
  const pending = deferred(); const { page, options } = createPage({ getDashboard: () => pending.promise }); const task = page.load(); options.beforeUnmount.call(page)
  pending.resolve({ code: 0, data: readyData({ pendingTodo: 3 }) }); await task; assert.equal(page.cardValue('pendingTodo'), null)
})
test('late audit from previous identity cannot replace current audit', async () => {
  const first = deferred(), second = deferred(); let count = 0; const { page } = createPage({ getAuditLogs: () => ++count === 1 ? first.promise : second.promise })
  await page.load(); page.ctx.ctxKey = 'tenant-b:teacher-b'; await page.load()
  second.resolve({ code: 0, data: [{ id: 'new' }] }); await tick(); first.resolve({ code: 0, data: [{ id: 'old' }] }); await tick()
  assert.equal(page.auditLogs.length, 1); assert.equal(page.auditLogs[0].id, 'new')
})
test('drill preserves server query but rejects external and mismatched paths', () => {
  const { page } = createPage(); const fallback = '/admin/student-affairs/risk?status=OPEN'
  assert.equal(page.safeDrill('/admin/student-affairs/risk?status=OPEN&studentId=22#record', fallback), '/admin/student-affairs/risk?status=OPEN&studentId=22#record')
  for (const path of ['https://example.com', '//example.com', '/admin/student/list', '/admin/student-affairs/risk\\evil', '/admin/student-affairs/risk\n']) assert.equal(page.safeDrill(path, fallback), '')
})
test('missing drill uses original fallback; explicit invalid drill stays disabled', () => {
  const { page } = createPage(); const data = readyData(); setReady(page, data)
  assert.equal(page.cardPath('overdueLeave'), '/admin/student-affairs/leave/ledger?status=OVERDUE')
  data.summaryCards.find((card) => card.key === 'overdueLeave').drillPath = '//example.com'; assert.equal(page.cardPath('overdueLeave'), '')
})
test('student permissionAny works without granting unrelated queues', () => {
  const { page } = createPage({}, { permissionPatterns: ['studentAffairs.dashboard.view', 'student.profile.view'], rbacOk: true }); setReady(page)
  assert.equal(page.cardPath('studentTotal'), '/admin/student/list'); assert.equal(page.cardPath('riskStudents'), ''); assert.equal(page.highFrequencyEntries.length, 1)
})
test('navigation checks readiness and authorization again', () => {
  const { page, calls } = createPage(); setReady(page); page.go('/admin/student-affairs/risk?status=OPEN'); assert.equal(calls.routes.length, 1)
  page.go('https://example.com'); assert.equal(calls.routes.length, 1)
  page.ctx.permissionPatterns = ['studentAffairs.dashboard.view']; page.go('/admin/student-affairs/risk?status=OPEN'); assert.equal(calls.routes.length, 1)
})
test('export preserves original purpose and cannot use stale context', async () => {
  const { page, calls } = createPage(); await assert.rejects(page.exportLedger()); setReady(page); await page.exportLedger()
  assert.equal(calls.exports[0].purpose, '学工看板范围学生台账导出'); page.ctx.permissionPatterns = []; await assert.rejects(page.exportLedger()); assert.equal(calls.exports.length, 1)
})
test('role projection uses server view without fabricated aggregates', () => {
  const { page } = createPage()
  for (const [view, text] of [['COUNSELOR', '本人'], ['COLLEGE_SA', '本院'], ['SA_ADMIN', '全校']]) { setReady(page, { ...readyData(), view }); assert.ok(page.heroGuidance.includes(text)) }
  assert.doesNotMatch(source, /priorityStudents|recommendedAction|dormExceptionCount/)
})
test('visual correction is A1-only, preserves SLA and readable text', () => {
  assert.match(source, /:global\(\.student-affairs-ui-scope:has\(> \.sa-v6-page-shell\) > \.sa-context-stack\)/); assert.match(source, /order: 2/)
  assert.doesNotMatch(source, /\.sa-context-stack[^}]*display:\s*none/); assert.doesNotMatch(source, /font-size:\s*(?:[0-9]|1[01])px/)
  assert.match(source, /<ul class="sa-v6-queue"/); assert.match(source, /:focus-visible/)
})
