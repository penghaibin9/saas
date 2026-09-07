import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/GuidancePlanView.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[^\n]+\},/, '').replace('export default', 'return')
function setup(api) {
  const def = new Function('guidanceVisitApi', script)(api)
  const targets = []
  const vm = { ...def.data(), batchStore: { selectedBatchId: '9', withBatchQuery: q => ({ ...q, batchId: '9' }) },
    $route: { query: {} }, $router: { replace: t => targets.push(t), push: t => targets.push(t) } }
  for (const [name, fn] of Object.entries(def.methods)) vm[name] = fn.bind(vm)
  return { vm, targets }
}
test('plan template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'GuidancePlanView.vue', id: 'plan-ui' }).errors, [])
})
test('list, statistics, export and record navigation carry the selected batch', async () => {
  const calls = []
  const { vm, targets } = setup({ getGuidancePlans: async p => { calls.push(p); return { code: 0, data: { list: [], total: 0 } } },
    getGuidanceStats: async (_n, p) => { calls.push(p); return { code: 0, data: {} } },
    exportGuidancePlans: p => { calls.push(p); return { code: 0 } } })
  await vm.load(); await vm.loadStats(); vm.exportFn(); vm.goGuidance({ studentName: '测试学生' })
  assert.ok(calls.every(p => p.batchId === '9')); assert.equal(targets[0].query.batchId, '9')
})
test('old batch responses do not overwrite current rows or failed statistics', async () => {
  let finishList, finishStats
  const { vm } = setup({ getGuidancePlans: p => p.batchId === '9' ? new Promise(r => { finishList = r }) : Promise.resolve({ code: 0, data: { list: [{ internId: 'new' }], total: 1 } }),
    getGuidanceStats: (_n, p) => p.batchId === '9' ? new Promise(r => { finishStats = r }) : Promise.resolve({ code: 1, message: '统计失败' }) })
  const old = vm.load(), stats = vm.loadStats(); vm.batchStore.selectedBatchId = '10'
  await vm.load(); await vm.loadStats()
  finishList({ code: 0, data: { list: [{ internId: 'old' }], total: 99 } }); finishStats({ code: 0, data: { studentCount: 99 } })
  await old; await stats
  assert.equal(vm.rows[0].internId, 'new'); assert.equal(vm.stats, null); assert.equal(vm.statsError, '统计失败')
})
test('route restores pagination and filters, and clearing query clears stale filters', () => {
  const { vm, targets } = setup({})
  vm.$route.query = { batchId: '9', page: '3', insufficient: '1', keyword: '测试' }; vm.applyRouteQuery()
  assert.equal(vm.page, 3); assert.equal(vm.insufficientOnly, true); assert.equal(vm.keyword, '测试')
  vm.onStatusFilterChange('OK')
  assert.equal(targets[0].query.page, '1'); assert.equal(targets[0].query.planStatus, 'OK'); assert.equal(targets[0].query.insufficient, undefined)
  vm.$route.query = {}; vm.applyRouteQuery()
  assert.equal(vm.keyword, ''); assert.equal(vm.statusFilter, ''); assert.equal(vm.page, 1)
})
