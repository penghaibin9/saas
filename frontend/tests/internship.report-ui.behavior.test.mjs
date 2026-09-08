import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/WeeklyReportListView.vue', import.meta.url), 'utf8')).descriptor.script.content
  .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[\s\S]*?ActionReceipt \},/, '')
  .replace('export default', 'return')
test('report list rejects late results after filters have changed', async () => {
  let finish
  const api = { getWeeklyReports: params => params.status === 'PENDING_REVIEW' ? new Promise(resolve => { finish = resolve }) : Promise.resolve({ code: 0, data: { list: [{ id: 'new' }], total: 1 } }) }
  const def = new Function('internshipApi', script)(api)
  const vm = { ...def.data(), batchStore: { selectedBatchId: '1' }, isProcessReport: false }
  const load = def.methods.load.bind(vm)
  const old = load(); vm.filters.status = 'APPROVED'; await load()
  finish({ code: 0, data: { list: [{ id: 'old' }], total: 20 } }); await old
  assert.equal(vm.rows[0].id, 'new'); assert.equal(vm.pagination.total, 1)
})

test('report detail link and queue retain type, batch and current page', () => {
  let queue, target
  const def = new Function('saveReviewQueue', script)(value => { queue = value })
  const vm = { ...def.data(), batchStore: { selectedBatchId: '9' }, isProcessReport: true,
    typeConfig: { label: '月报' }, activeTabs: [{ value: 'PENDING_REVIEW', label: '待批阅' }],
    $route: { path: '/admin/internship/reports', query: { type: 'monthly', panel: 'review' } }, $router: { push: value => { target = value } } }
  vm.pagination.page = 3; vm.rows = [{ id: '9007199254740999' }]
  def.methods.goDetail.call(vm, vm.rows[0])
  assert.equal(target.path, '/admin/internship/process-reports/9007199254740999')
  assert.equal(target.query.type, 'monthly'); assert.equal(target.query.batchId, '9'); assert.equal(target.query.page, '3')
  assert.deepEqual(queue.listQuery, target.query)
})
