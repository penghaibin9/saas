import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const source = fs.readFileSync(new URL('../src/modules/studentAffairs/views/funding/FundingDisbursementView.vue', import.meta.url), 'utf8')
const raw = source.match(/<script>([\s\S]*?)<\/script>/)[1]
const bindings = [...raw.matchAll(/import\s*\{([^}]+)\}\s*from/g)].flatMap(m => m[1].split(',').map(x => x.trim()).filter(Boolean))
const script = raw.replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm, '').replace('export default', 'return')
function make(api = {}, exportApi = {}) {
  const values = Object.fromEntries(bindings.map(k => [k, {}]))
  Object.assign(values, { studentAffairsApi: api, fundingExportApi: exportApi, toast: { success() {}, error() {} }, canCode: () => true })
  const c = new Function(...Object.keys(values), script)(...Object.values(values))
  const vm = { ...c.data(), ...c.methods, $route: { query: {} } }
  vm.watchQuery = c.watch['$route.query']
  for (const [k, fn] of Object.entries(c.computed)) Object.defineProperty(vm, k, { get: () => fn.call(vm) })
  return vm
}
test('disbursement page uses only authorized server actions', () => {
  const vm = make()
  assert.equal(vm.allows({ bankStatus: 'PENDING' }, 'ISSUE'), false)
  assert.equal(vm.allows({ bankStatus: 'PENDING', allowedActions: [] }, 'ISSUE'), false)
  assert.equal(vm.allows({ bankStatus: 'FAILED', allowedActions: ['ISSUE'] }, 'ISSUE'), true)
})
test('older records and statistics cannot overwrite a newly selected batch', async () => {
  const records = [], stats = [], vm = make({
    getFundingDisbursements: p => new Promise(resolve => records.push({ p, resolve })),
    getDisbursementStats: id => new Promise(resolve => stats.push({ id, resolve }))
  })
  vm.genBatchId = '1'; const first = vm.loadRecords(), firstStats = vm.loadStats()
  vm.genBatchId = '2'; const next = vm.loadRecords(), nextStats = vm.loadStats()
  records[1].resolve({ code: 0, data: { items: [{ batchId: '2' }], total: 50 } }); stats[1].resolve({ code: 0, data: { total: 50 } })
  await Promise.all([next, nextStats])
  records[0].resolve({ code: 0, data: { items: [], total: 0 } }); stats[0].resolve({ code: 0, data: { total: 0 } })
  await Promise.all([first, firstStats]); assert.equal(vm.items[0].batchId, '2'); assert.equal(vm.stats.total, 50)
  assert.deepEqual(stats.map(x => x.id), ['1', '2'])
})
test('an older valid batch beyond the first 200 remains selectable without fallback', async () => {
  const pages = [], vm = make({ getFundingBatches: async p => { pages.push(p.page); return { code: 0, data: { total: 201, items: p.page === 1 ? Array.from({ length: 200 }, (_, i) => ({ batchId: String(i + 2), projectId: '9' })) : [{ batchId: '1', projectId: '9', projectName: '国家奖学金' }] } } } })
  vm.genBatchId = '1'; vm.routeProjectId = '9'; await vm.loadBatches()
  assert.deepEqual(pages, [1, 2]); assert.equal(vm.batches.length, 201); assert.equal(vm.genBatchId, '1'); assert.equal(vm.batchError, '')
  assert.match(vm.batchOptions.at(-1).label, /国家奖学金/)
})
test('generation and export submit the batch reviewed in their own dialogs', async () => {
  const generated = [], exported = [], vm = make({ generateDisbursements: async id => { generated.push(id); return { code: 0, data: { generated: 1 } } } }, { create: async body => { exported.push(body); return { code: 0, data: { jobId: 'j2' } } } })
  vm.genBatchId = '1'; vm.openGenerate(); vm.openExport(); vm.genBatchId = '2'; vm.activeStatus = 'FAILED'
  vm.loadRecords = async () => {}; vm.loadStats = async () => {}; vm.startExportPolling = () => {}
  vm.exportDlg.purpose = '学工财务核对归档'; await vm.generate(); await vm.createExport()
  assert.deepEqual(generated, ['1']); assert.equal(exported[0].batchId, '1'); assert.equal(exported[0].bankStatus, undefined)
})
test('failed issue keeps inspected version and input while rapid clicks submit once', async () => {
  let resolve; const calls = [], vm = make({ issueDisbursement: (id, body) => { calls.push([id, body]); return new Promise(r => { resolve = r }) } })
  vm.issue({ disbursementId: '7', applicationId: '90', amount: 3000, batchId: '1', version: 5, allowedActions: ['ISSUE'] })
  vm.issDlg.disburseNo = 'BANK-2026-01'; vm.issDlg.bankLast4 = '1234'
  const first = vm.submitIssue(); await vm.submitIssue(); assert.equal(calls.length, 1); assert.equal(calls[0][1].version, 5)
  resolve({ code: 409, message: '版本已变化' }); await first
  assert.equal(vm.issDlg.visible, true); assert.equal(vm.issDlg.disburseNo, 'BANK-2026-01'); assert.match(vm.issDlg.error, /版本/)
})
test('a stale export polling response cannot replace a newer export', async () => {
  let resolve; const vm = make({}, { job: () => new Promise(r => { resolve = r }) })
  vm.exportJob = { jobId: 'old' }; const pending = vm.refreshExportJob(); vm.exportJob = { jobId: 'new' }
  resolve({ code: 0, data: { status: 'FAILED' } }); await pending
  assert.equal(vm.exportJob.jobId, 'new')
})

test('a changed project in a direct link revalidates the batch even when batch ID stays the same', () => {
  const vm = make()
  vm.batches = [{ batchId: '25', projectId: '3' }]
  vm.$route.query = { batchId: '25', projectId: '4' }
  vm.loadRecords = () => {}; vm.loadStats = () => {}
  vm.watchQuery(vm.$route.query, { batchId: '25', projectId: '3' })
  assert.equal(vm.routeProjectId, '4')
  assert.ok(vm.batchError)
})

test('failure registration freezes the inspected application, amount and version', async () => {
  const calls = [], vm = make({ failDisbursement: async (...args) => { calls.push(args); return { code: 409, message: '版本已变化' } } })
  const row = { disbursementId: '7', applicationId: '90', batchId: '25', amount: '3000.00', version: 5, allowedActions: ['FAIL'] }
  vm.fail(row); row.applicationId = '91'; row.amount = '5000.00'
  vm.genBatchId = '26'; await vm.submitFail({ reason: '银行回执信息需要核对' })
  assert.equal(vm.failDlg.applicationId, '90'); assert.equal(vm.failDlg.batchId, '25')
  assert.equal(vm.failDlg.amount, '3000.00'); assert.equal(vm.failDlg.visible, true)
  assert.deepEqual(calls, [['7', '银行回执信息需要核对', 5]])
})
