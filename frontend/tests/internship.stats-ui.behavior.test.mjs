import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'

const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/StatsView.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content.replace(/^import[^\n]+\r?\n/gm, '').replace(/^ {2}components:.*\r?\n/m, '').replace('export default', 'return')
const result = data => ({ code: 0, data })
const overview = () => result({ counters: [{ key: 'total', value: 3 }], metrics: [{ key: 'placementRate', label: '实习落实率', numerator: 1, denominator: 3, rate: 33.3, threshold: 95, warn: true }], generatedAt: '2026-09-07T10:00:00' })
function setup(api = {}, permission = () => true) {
  const def = new Function('statsApi', 'canCode', 'buildBarChartSpec', script)(api, permission, value => value)
  const targets = [], vm = { ...def.data(), ctx: {}, batchStore: { selectedBatchId: '9007199254740999', withBatchQuery: q => ({ ...q, batchId: vm.batchStore.selectedBatchId }) }, $route: { query: {} }, $router: { push: target => targets.push(target), replace: target => targets.push(target) } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(def.computed)) if (key !== 'batchStore') Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, def, targets }
}

test('statistics template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'StatsView.vue', id: 'stats' }).errors, [])
})

test('filter deep link, metric detail and return preserve batch and attention selection', () => {
  const { vm, targets } = setup()
  vm.$route.query = { college: '学院甲', major: '专业乙', className: '班级丙', attention: '1', metric: 'placementRate' }
  vm.restoreQuery(); assert.equal(vm.filterLabel, '学院甲 / 专业乙 / 班级丙'); assert.equal(vm.onlyAttention, true)
  vm.closeMetric(); assert.equal(targets[0].query.metric, undefined); assert.equal(targets[0].query.major, '专业乙'); assert.equal(targets[0].query.attention, '1'); assert.equal(targets[0].query.batchId, '9007199254740999')
  vm.openMetric({ key: 'arrivalRate' }); assert.equal(targets[1].query.metric, 'arrivalRate'); assert.equal(targets[1].query.className, '班级丙')
})

test('a single dimension can be cleared without clearing other selected dimensions', () => {
  const { vm, targets } = setup(); vm.$route.query = { college: '学院甲', major: '专业乙', className: '班级丙', metric: 'placementRate' }; vm.restoreQuery()
  vm.dim.major = ''; vm.applyFilters(); assert.equal(targets[0].query.college, '学院甲'); assert.equal(targets[0].query.major, ''); assert.equal(targets[0].query.className, '班级丙'); assert.equal(targets[0].query.metric, undefined)
  vm.clearDim(); assert.deepEqual(vm.dim, { college: '', major: '', className: '' })
})

test('URL detail and attention navigation does not refetch an unchanged dataset', () => {
  const { vm, def } = setup(); vm.restoreQuery(); vm.requestKey = vm.contextKey; vm.load = () => assert.fail('detail navigation should reuse overview')
  vm.$route.query = { metric: 'placementRate', attention: '1' }; def.watch['$route.query'].call(vm); assert.equal(vm.selectedKey, 'placementRate')
})

test('refresh reads the same scoped filters for overview and six-month trends', async () => {
  const calls = [], { vm } = setup({ getOverview: async q => { calls.push(q); return overview() }, getTrends: async q => { calls.push(q); return result({ series: [] }) } })
  vm.dim = { college: '学院甲', major: '', className: '班级丙' }; await vm.load()
  assert.deepEqual(calls, [{ college: '学院甲', major: undefined, className: '班级丙', batchId: '9007199254740999' }, { college: '学院甲', major: undefined, className: '班级丙', batchId: '9007199254740999', months: 6 }]); assert.equal(vm.loaded, true)
})

test('a failed trend clears old chart data while keeping the successful overview', async () => {
  const { vm } = setup({ getOverview: async () => overview(), getTrends: async () => ({ code: 1, message: '趋势服务暂不可用' }) })
  vm.trendSeries = [{ label: '旧数据', points: [{ month: '2025-01', value: 99 }] }]; await vm.load()
  assert.equal(vm.loaded, true); assert.equal(vm.counters[0].value, 3); assert.deepEqual(vm.trendSeries, []); assert.equal(vm.trendError, '趋势服务暂不可用'); assert.equal(vm.error, '')
})

test('rejected overview is an error and cannot leave old totals or timestamps visible', async () => {
  const { vm } = setup({ getOverview: async () => { throw new Error('统计网络失败') }, getTrends: async () => result({ series: [] }) })
  vm.generatedAt = 'old'; vm.counters = [{ value: 99 }]; await vm.load()
  assert.equal(vm.error, '统计网络失败'); assert.equal(vm.generatedAt, ''); assert.deepEqual(vm.counters, []); assert.equal(vm.loaded, false); assert.equal(vm.loading, false)
})

test('late statistics cannot replace a newer filtered result', async () => {
  const requests = [], { vm } = setup({ getOverview: () => new Promise(resolve => requests.push(resolve)), getTrends: async () => result({ series: [] }) })
  const old = vm.load(); vm.dim.college = '新学院'; const current = vm.load()
  requests[1](overview()); await current; requests[0](result({ counters: [{ value: 999 }] })); await old
  assert.equal(vm.counters[0].value, 3); assert.equal(vm.loaded, true)
})

test('switching batch clears old filters and metric while dropping late responses', async () => {
  let finish
  const { vm, def, targets } = setup({ getOverview: () => new Promise(resolve => { finish = resolve }), getTrends: async () => result({ series: [] }) })
  vm.dim.college = '旧学院'; vm.$route.query = { college: '旧学院', metric: 'placementRate' }; const old = vm.load()
  vm.batchStore.selectedBatchId = '2'; vm.loadDims = () => {}; vm.load = () => { vm.clearData() }
  def.watch['batchStore.selectedBatchId'].call(vm, '2', '9007199254740999'); finish(overview()); await old
  assert.equal(vm.dim.college, ''); assert.equal(targets[0].query.metric, undefined); assert.equal(targets[0].query.college, undefined); assert.equal(targets[0].query.batchId, '2'); assert.deepEqual(vm.counters, [])
})

test('dimension failure replaces old school options and supports retry', async () => {
  let fail = true
  const { vm } = setup({ getDimensions: async () => fail ? { code: 1, message: '选项加载失败' } : result({ colleges: ['新学院'], majors: [], classes: [] }) })
  vm.dims.colleges = ['旧学院']; await vm.loadDims(); assert.deepEqual(vm.dims.colleges, []); assert.equal(vm.dimsError, '选项加载失败'); assert.equal(vm.dimsLoading, false)
  fail = false; await vm.loadDims(); assert.deepEqual(vm.dims.colleges, ['新学院']); assert.equal(vm.dimsError, '')
})

test('an old dimension request cannot restore options after identity change or unmount', async () => {
  let finish
  const { vm, def } = setup({ getDimensions: () => new Promise(resolve => { finish = resolve }) })
  const old = vm.loadDims(); vm.contextEpoch++; finish(result({ colleges: ['旧学院'] })); await old; assert.deepEqual(vm.dims.colleges, [])
  const next = vm.loadDims(); def.beforeUnmount.call(vm); finish(result({ colleges: ['旧学院'] })); await next; assert.deepEqual(vm.dims.colleges, [])
})

test('zero, empty denominator and abnormal metrics are not presented as the same status', () => {
  const { vm } = setup()
  assert.equal(vm.metricValue({ rate: 0, warn: true }), '0%'); assert.equal(vm.metricStatus({ rate: 0, warn: true }), '低于阈值')
  assert.equal(vm.metricStatus({ rate: null, warn: false }), '暂无数据'); assert.equal(vm.metricType({ rate: null }), 'default')
  assert.equal(vm.metricStatus({ rate: null, anomaly: true }), '口径异常'); assert.equal(vm.metricType({ rate: null, anomaly: true }), 'warning')
  vm.metrics = [{ key: 'empty', rate: null }, { key: 'warning', warn: true }, { key: 'anomaly', anomaly: true }]; vm.onlyAttention = true
  assert.equal(vm.attentionCount, 2); assert.deepEqual(vm.visibleMetrics.map(m => m.key), ['warning', 'anomaly'])
})

test('no batch or no view permission means no statistics request', async () => {
  const api = { getOverview: () => assert.fail('no overview request'), getTrends: () => assert.fail('no trends request'), getDimensions: () => assert.fail('no dimension request') }
  const { vm } = setup(api, () => false); await vm.load(); await vm.loadDims(); assert.match(vm.error, /权限/)
  vm.batchStore.selectedBatchId = ''; await vm.load(); assert.match(vm.error, /选择实习批次/)
})

test('export uses visible organization filters, refuses missing permission, and drops old-scope files', async () => {
  const calls = [], { vm } = setup({ exportStats: async q => { calls.push(q); return result({ filename: '统计.xlsx' }) } })
  vm.dim = { college: '学院甲', major: '', className: '班级丙' }; await vm.exportFn(); assert.deepEqual(calls, [{ ...vm.dim, batchId: '9007199254740999' }])
  vm.canBtn = () => false; assert.match((await vm.exportFn()).message, /权限/); assert.equal(calls.length, 1)
  let finish; const { vm: stale } = setup({ exportStats: () => new Promise(resolve => { finish = resolve }) }); const old = stale.exportFn(); stale.contextEpoch++
  finish(result({ filename: '旧学校统计.xlsx' })); const res = await old; assert.notEqual(res.code, 0); assert.equal(res.data, undefined)
})
