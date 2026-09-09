import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import {
  count, finite, formatCount, formatRate, escapeHtml, metricOf, METRIC_LABELS,
  can, routeFor, workRoute, unwrap, project, readSnapshot, createCoordinator,
  REQUIRED_PERMISSIONS, FLOW
} from '../src/modules/internship/components/command-screen/screen-core.mjs'

const context = (extra = {}) => ({ batchId: '81', batchName: 'test-only', accessHealthy: true,
  grants: Object.fromEntries(REQUIRED_PERMISSIONS.map(key => [key, true])), ...extra })
const rate = (extra = {}) => ({ key: 'agreementSignRate', numerator: 8, denominator: 10, rate: 80, warn: true, ...extra })
const data = () => ({ batchId: '81', metricVersion: 'internship-stats-v1', generatedAt: '2026-09-06T00:00:00',
  counters: [{ key: 'totalStudents', value: 10 }, { key: 'onboardStudents', value: 8 }, { key: 'riskStudents', value: 1 }],
  metrics: [rate()], scoreDistribution: [{ bucket: '优', count: 2 }], partial: [], appliedFilters: { batchId: '81' } })
const dashboard = () => ({ batchId: '81', flow: [{ label: '在岗中', value: 8 }, { label: '准备中', value: 2 }], workItems: [], workItemTotal: 0 })
const trends = () => ({ batchId: '81', series: [{ key: 'reports', label: '报告提交', points: [{ month: '2026-09', value: 2 }] }] })
const ok = data => ({ code: 0, data })
const loaders = (override = {}) => ({ overview: async () => ok(data()), dashboard: async () => ok(dashboard()), trends: async () => ok(trends()), ...override })
const clone = value => structuredClone(value)

test('counts preserve valid zero but reject missing, blank, booleans and objects', () => {
  for (const value of [null, undefined, '', ' ', false, true, {}, [], -1, 1.3, Infinity, NaN]) assert.equal(count(value), null)
  assert.equal(count(0), 0); assert.equal(count('42'), 42); assert.equal(formatCount(null), '—'); assert.equal(formatCount(0), '0')
})
test('finite numeric validation and formatting reject invalid percentages', () => {
  assert.equal(finite('1.2'), 1.2); assert.equal(finite({ valueOf: () => 1 }), null)
  for (const value of [null, undefined, '', Infinity, -1, 101]) assert.equal(formatRate(value), '—')
  assert.equal(formatRate(0), '0.0%'); assert.equal(formatRate(100), '100.0%')
})
test('dynamic strings are escaped before DOM insertion', () => assert.equal(escapeHtml('<script a="x">&\''), '&lt;script a=&quot;x&quot;&gt;&amp;&#39;'))
test('metrics are keyed, not coupled to backend array order', () => {
  const list = [{ ...rate(), key: 'placementRate', numerator: 9, rate: 90 }, rate()]
  assert.equal(metricOf(list, 'agreementSignRate').rate, 80)
  assert.equal(Object.keys(METRIC_LABELS).length, 17); assert.equal(FLOW.length, 9)
})
test('missing metric is not fabricated as zero', () => {
  assert.equal(metricOf([], 'agreementSignRate').state, 'missing'); assert.equal(metricOf([], 'agreementSignRate').rate, null)
})
test('empty denominator never becomes 0 percent or 100 percent', () => {
  const m = metricOf([rate({ numerator: 0, denominator: 0, rate: 0 })], 'agreementSignRate')
  assert.equal(m.state, 'empty'); assert.equal(m.rate, null)
})
test('a valid zero numerator retains a legitimate zero rate', () => assert.equal(metricOf([rate({ numerator: 0, rate: 0 })], 'agreementSignRate').rate, 0))
test('numerator above denominator is flagged, never clipped to 100', () => {
  const m = metricOf([rate({ numerator: 12, rate: 120 })], 'agreementSignRate')
  assert.equal(m.state, 'anomaly'); assert.equal(m.rate, null)
})
test('server anomaly and mathematically inconsistent percentages stay unavailable', () => {
  assert.equal(metricOf([rate({ anomaly: true })], 'agreementSignRate').state, 'anomaly')
  assert.equal(metricOf([rate({ rate: 79 })], 'agreementSignRate').state, 'anomaly')
})
test('no frontend substitution for the audited evaluation denominator mismatch', () => {
  const m = metricOf([rate({ key: 'enterpriseEvalRate' })], 'enterpriseEvalRate')
  assert.equal(m.denominator, 10); assert.equal(m.definitionIssue, true); assert.match(m.note, /A03/)
})
test('permission grants fail closed for missing, string true and unhealthy context', () => {
  assert.equal(can({}, 'x'), false); assert.equal(can({ grants: { x: 'true' } }, 'x'), false)
  assert.equal(can({ grants: { x: true }, accessHealthy: false }, 'x'), false)
})
test('routes are allowlisted and carry the current encoded batch', () => {
  assert.equal(routeFor('stats', context()), '/admin/internship/stats?batchId=81')
  assert.equal(routeFor('https://evil.test', context()), null)
  assert.match(routeFor('stats', context({ batchId: 'a&tenantId=other' })), /batchId=a%26tenantId%3Dother$/)
  assert.equal(routeFor('stats', context({ batchId: '' })), null)
})
test('work routes ignore untrusted backend routes and enforce numeric object IDs', () => {
  const w = { kind: 'WEEKLY_REPORT', objectId: '208', route: 'javascript:alert(1)' }
  assert.equal(workRoute(w, context()), '/admin/internship/reports/208?batchId=81')
  assert.equal(workRoute({ ...w, objectId: '../other' }, context()), null)
  assert.equal(workRoute({ ...w, kind: 'UNKNOWN' }, context()), null)
})
test('risk route is read-only navigation and preserves the existing ID query', () => assert.equal(workRoute({ kind: 'RISK', objectId: '9001' }, context()), '/admin/internship/risk-disposal?batchId=81&id=9001'))
test('destination permission is checked separately from dashboard permission', () => {
  const ctx = context(); ctx.grants['internship.risk.handle'] = false
  assert.equal(workRoute({ kind: 'RISK', objectId: '1' }, ctx), null)
})
test('batch receipt validation rejects missing IDs and all conflicting echoes', () => {
  assert.throws(() => unwrap(ok({}), '81', 'test'), e => e.code === 'BATCH_MISMATCH')
  assert.throws(() => unwrap(ok({ batchId: '81', appliedFilters: { batchId: '82' } }), '81', 'test'), e => e.code === 'BATCH_MISMATCH')
  assert.equal(unwrap(ok({ batchId: 81 }), '81', 'test').batchId, 81)
})
test('backend envelopes must actually report success', () => assert.throws(() => unwrap({ code: 503001, data: data() }, '81', 'test')))
test('projection removes student names, numbers and free-text summaries', () => {
  const d = dashboard(); d.workItems = [{ kind: 'RISK', objectId: '88', studentName: 'PRIVATE_NAME', studentNo: 'PRIVATE_NO', title: 'PRIVATE_TITLE', summary: 'PRIVATE_NOTE' }]
  const m = project(data(), d, trends(), context()); assert.doesNotMatch(JSON.stringify(m), /PRIVATE_/)
})
test('bounded work sample is not used as an all-school risk count', () => {
  const d = dashboard(); d.workItems = Array.from({ length: 30 }, (_, i) => ({ kind: 'RISK', objectId: String(i + 1) }))
  const m = project(data(), d, trends(), context()); assert.equal(m.work.length, 8); assert.equal(m.riskStudents, 1)
})
test('cross-endpoint state inconsistencies are shown explicitly', () => {
  const d = dashboard(); d.flow[0].value = 7
  const m = project(data(), d, trends(), context()); assert.equal(m.states.length, 0); assert.ok(m.stateIssue)
})
test('unverified risk, retention and live attendance trends are not accepted', () => {
  const t = trends(); t.series.push({ key: 'retention', points: [] }); assert.equal(project(data(), dashboard(), t, context()).series.length, 1)
})
test('malformed counters and optional partial lists do not become fake numbers', () => {
  const d = data(); d.counters = {}; d.partial = {}
  const m = project(d, null, null, context()); assert.equal(m.total, null); assert.deepEqual(m.issues, ['大屏聚合未返回；地图和排行不使用预览数字补齐'])
})
test('one refresh makes exactly three original API calls with the same batch', async () => {
  const calls = []
  const l = loaders(Object.fromEntries(['overview', 'dashboard', 'trends'].map(key => [key, async p => { calls.push([key, clone(p)]); return ok(({ overview: data, dashboard, trends })[key]()) }])))
  assert.equal((await readSnapshot(l, context())).status, 'ready'); assert.equal(calls.length, 3)
  for (const [key, params] of calls) { assert.equal(params.batchId, '81'); if (key === 'trends') assert.equal(params.months, 6) }
})
test('no selected batch means no network request', async () => {
  let n = 0; const l = loaders({ overview: () => { n++; throw Error() } })
  assert.equal((await readSnapshot(l, context({ batchId: '' }))).status, 'no-batch'); assert.equal(n, 0)
})
test('missing stats permission means no network request', async () => {
  let n = 0; const l = Object.fromEntries(['overview', 'dashboard', 'trends'].map(k => [k, () => { n++ }]))
  assert.equal((await readSnapshot(l, context({ grants: {} }))).status, 'denied'); assert.equal(n, 0)
})
test('main endpoint 503 is an error, not an empty successful page', async () => assert.equal((await readSnapshot(loaders({ overview: async () => ({ code: 503001, message: 'down' }) }), context())).status, 'error'))
test('optional trend failure creates partial visibility without synthetic history', async () => {
  const r = await readSnapshot(loaders({ trends: async () => { throw Error('down') } }), context())
  assert.equal(r.status, 'ready'); assert.equal(r.model.trendsAvailable, false); assert.deepEqual(r.model.series, []); assert.equal(r.model.issues.length, 2); assert.ok(r.model.issues.some(s=>s.includes('大屏聚合未返回')))
})
test('403 from any source blocks the entire result rather than keeping sensitive data', async () => {
  const r = await readSnapshot(loaders({ dashboard: async () => ({ code: 403001, message: 'denied' }) }), context())
  assert.equal(r.status, 'denied'); assert.equal(r.model, undefined)
})
test('dashboard request is omitted without its separate permission', async () => {
  let n = 0; const ctx = context(); ctx.grants['internship.dashboard.view'] = false
  const r = await readSnapshot(loaders({ dashboard: () => { n++; throw Error() } }), ctx)
  assert.equal(n, 0); assert.equal(r.status, 'ready'); assert.equal(r.model.dashboardAvailable, false)
})
test('a mismatched main batch response cannot be displayed', async () => {
  const wrong = data(); wrong.batchId = '99'
  assert.equal((await readSnapshot(loaders({ overview: async () => ok(wrong) }), context())).status, 'error')
})
test('coordinator ignores responses from a previously selected batch', async () => {
  const waiting = {}, committed = []
  const c = createCoordinator(ctx => new Promise(resolve => { waiting[ctx.batchId] = resolve }), (r, ctx) => committed.push(ctx.batchId))
  const first = c.run({ batchId: 'a' }); await Promise.resolve(); c.invalidate()
  const second = c.run({ batchId: 'b' }); await Promise.resolve()
  waiting.b({ status: 'ready' }); await second; waiting.a({ status: 'ready' }); await first
  assert.deepEqual(committed, ['b']); c.destroy()
})
test('coordinator deduplicates refreshes while a request is pending', async () => {
  let calls = 0, finish
  const c = createCoordinator(() => { calls++; return new Promise(resolve => { finish = resolve }) }, () => {})
  const a = c.run(context()), b = c.run(context()); await Promise.resolve(); assert.equal(calls, 1)
  finish({ status: 'ready' }); await Promise.all([a, b]); c.destroy()
})
test('unmount invalidates a pending result', async () => {
  let finish, committed = false
  const c = createCoordinator(() => new Promise(resolve => { finish = resolve }), () => { committed = true })
  const promise = c.run(context()); await Promise.resolve(); c.destroy(); finish({ status: 'ready' }); await promise
  assert.equal(committed, false)
})
test('production adapter reuses the actual repo APIs and never imports fixtures', async () => {
  const source = await readFile(new URL('../src/modules/internship/components/command-screen/InternshipCommandScreen.vue', import.meta.url), 'utf8')
  assert.match(source, /statsApi\.getOverview/); assert.match(source, /internshipApi\.getDashboardSummary/); assert.match(source, /getCommandScreenExtension/); assert.doesNotMatch(source, /statsApi\.getTrends/)
  assert.doesNotMatch(source, /fixtures|Math\.random|localStorage|fetch\(/); assert.match(source, /Array\.isArray\(ctx\.permissionPatterns\)/)
})
test('renderer does not replicate writes or infer historical trends from current values', async () => {
  const source = await readFile(new URL('../src/modules/internship/components/command-screen/screen-renderer.mjs', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /fetch\(|XMLHttpRequest|Math\.random|method:\s*['"](?:POST|PUT|PATCH|DELETE)/)
  assert.match(source, /300000/); assert.match(source, /let auto = false/)
})
