import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/InternshipRiskView.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[\s\S]*?ModuleSummaryStrip \},/, '').replace('export default', 'return')
function setup(api = {}, risk = {}) {
  const def = new Function('internshipApi', 'riskApi', 'toast', script)(api, risk, { success() {}, error() {} })
  const targets = []
  const vm = { ...def.data(), canHandle: true, batchStore: { selectedBatchId: '1', withBatchQuery: q => ({ ...q, batchId: '1' }) },
    $route: { query: {}, path: '/admin/internship/risks' }, $router: { replace: t => targets.push(t), push: t => targets.push(t) } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  return { vm, targets }
}
test('risk template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'InternshipRiskView.vue', id: 'risk-ui' }).errors, [])
})
test('late risk list cannot overwrite the current filter result', async () => {
  let finish
  const { vm } = setup({ getRiskStudents: p => p.status === 'PROCESSING' ? Promise.resolve({ code: 0, data: { list: [{ id: 'current' }], total: 1 } }) : new Promise(r => { finish = r }) })
  const old = vm.load(); vm.filters.status = 'PROCESSING'; await vm.load()
  finish({ code: 0, data: { list: [{ id: 'old' }], total: 99 } }); await old
  assert.equal(vm.rows[0].id, 'current'); assert.equal(vm.pagination.total, 1)
})
test('risk filters and page survive address restoration and reset selects all risks', () => {
  const { vm, targets } = setup(); vm.load = () => {}
  vm.$route.query = { panel: 'no-checkin', page: '3', keyword: '测试', level: 'HIGH' }
  vm.applyPanel('no-checkin')
  assert.equal(vm.filters.riskCode, 'INT-R07'); assert.equal(vm.filters.keyword, '测试'); assert.equal(vm.pagination.page, 3)
  vm.reset()
  assert.equal(targets[0].query.panel, 'board'); assert.equal(targets[0].query.riskCode, ''); assert.equal(targets[0].query.batchId, '1')
})
test('reminder rejects duplicate clicks, closed records and denied permissions', async () => {
  let writes = 0, finish
  const { vm } = setup({}, { remind: () => { writes++; return new Promise(r => { finish = r }) } })
  const row = { id: '9007199254740999', status: 'PROCESSING' }
  const first = vm.remind(row); await vm.remind(row)
  assert.equal(writes, 1); assert.deepEqual(vm.remindingIds, [row.id])
  finish({ code: 0, data: { ownerName: '测试教师' } }); await first
  assert.deepEqual(vm.remindingIds, [])
  await vm.remind({ ...row, status: 'CLOSED' }); vm.canHandle = false; await vm.remind(row)
  assert.equal(writes, 1)
})
