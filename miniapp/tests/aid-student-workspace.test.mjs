import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

const source = fs.readFileSync(new URL('../src/pages/student/affairs/aid.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
function make(api = {}, returned = {}, uni = {}) {
  const component = new Function('studentApi', 'affairsReturnedApi', 'normalizeError', 'toast', 'uni', script)(api, returned, e => ({ text: e.message }), () => {}, uni)
  const vm = { ...component.data(), ...component.methods, $nextTick: () => {} }
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: () => getter.call(vm) })
  return vm
}
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }

test('batch search and pagination preserve the selected application target and typed input', async () => {
  const calls = []
  const vm = make({ getAidBatches: async p => {
    calls.push(p)
    return { items: [{batchId: p.page === 2 ? 'old' : (p.keyword ? 'match' : 'new')}], total:2 }
  } })
  await vm.loadBatches(); assert.equal(vm.selectedBatch, null)
  await vm.loadBatches(true); vm.onBatch({detail:{value:1}})
  vm.form.reason = '已经填写的困难情况'
  vm.batchQuery = '历史'; await vm.loadBatches()
  assert.equal(vm.selectedBatch.batchId, 'old')
  assert.equal(vm.batchOptions[vm.batchIndex].batchId, 'old')
  assert.equal(vm.form.reason, '已经填写的困难情况')
  vm.batchQuery = '尚未搜索的新词'; await vm.loadBatches(true)
  assert.deepEqual(calls.at(-1), {page:2,pageSize:20,keyword:'历史'})
})

test('late batch results and failed searches cannot replace a newer query or selected batch', async () => {
  const a = deferred(), b = deferred(); let calls = 0
  const vm = make({getAidBatches: () => ++calls === 1 ? a.promise : b.promise})
  vm.selectedBatch = {batchId:'selected', label:'已选择'}
  const first = vm.loadBatches(), latest = vm.loadBatches()
  b.resolve({items:[{batchId:'latest'}],total:1}); await latest
  a.resolve({items:[{batchId:'stale'}],total:1}); await first
  assert.equal(vm.batches[0].batchId,'latest')
  assert.equal(vm.selectedBatch.batchId,'selected')
  const failed = make({getAidBatches:async()=>{throw Error('offline')}})
  failed.selectedBatch = vm.selectedBatch; await failed.loadBatches()
  assert.equal(failed.selectedBatch.batchId,'selected'); assert.match(failed.batchError,/已保留/)
})

test('refresh preserves selected batch and input; failure keeps the previous records visible', async () => {
  let fail = false
  const vm = make({ getMyAid: async () => { if (fail) throw Error('offline'); return { items: [{ applyId: '1' }] } }, getAidBatches: async () => ({ items: [{ batchId: 'a' }, { batchId: 'b' }] }) })
  await vm.load(); vm.onBatch({ detail: { value: 1 } }); vm.form.reason = '尚未提交的家庭情况'
  await vm.load()
  assert.equal(vm.batchIndex, 1); assert.equal(vm.form.reason, '尚未提交的家庭情况')
  fail = true; await vm.load()
  assert.equal(vm.state, 'ready'); assert.equal(vm.d.items[0].applyId, '1')
  assert.match(vm.loadError, /仍保留/); assert.equal(vm.refreshing, false)
})

test('closed or superseded detail requests never reveal stale family data', async () => {
  const a = deferred(), b = deferred()
  const vm = make({}, { getAidDetail: id => id === '1' ? a.promise : b.promise })
  const first = vm.openDetail({ applyId: '1' }), second = vm.openDetail({ applyId: '2' })
  a.resolve({ applyId: '1', annualIncome: 'private' }); await first
  assert.equal(vm.detail, null)
  vm.closeDetail(); b.resolve({ applyId: '2' }); await second
  assert.equal(vm.detail, null); assert.equal(vm.detailVisible, false)
})

test('detail updates list progress without copying private family fields into the list', async () => {
  const vm = make({}, { getAidDetail: async () => ({ applyId: '1', status: 'DRAFT', allowedActions: ['EDIT_RETURNED'], annualIncome: '24000', statement: '本人家庭情况' }) })
  vm.d = { items: [{ applyId: '1', status: 'CLASS_REVIEW' }] }
  await vm.openDetail({ applyId: '1' })
  assert.equal(vm.d.items[0].status, 'DRAFT')
  assert.equal(vm.d.items[0].annualIncome, undefined)
  assert.equal(vm.d.items[0].statement, undefined)
  vm.closeDetail(); assert.equal(vm.detail, null)
})

test('old list response cannot replace the latest refresh', async () => {
  const a = deferred(), b = deferred(); let calls = 0
  const vm = make({ getMyAid: () => ++calls === 1 ? a.promise : b.promise, getAidBatches: async () => ({ items: [] }) })
  const first = vm.load(), second = vm.load()
  b.resolve({ items: [{ applyId: 'new' }] }); await second
  a.resolve({ items: [{ applyId: 'old' }] }); await first
  assert.equal(vm.d.items[0].applyId, 'new')
})

test('failed resubmit keeps the saved version and editable input for a safe retry', async () => {
  const calls = []
  const vm = make({}, {
    updateAid: async (id, body) => { calls.push(body.version); return { applyId: id, version: 8 } },
    resubmitAid: async (id, version) => { assert.equal(version, 8); throw Error('offline') }
  })
  vm.editVisible = true; vm.editTarget = { applyId: '1', version: 7 }
  vm.editForm = { memberCount: '3', income: '0', debt: '', specialTags: '', reason: '补充后的家庭经济困难具体情况说明' }
  await vm.saveAndResubmit()
  assert.deepEqual(calls, [7]); assert.equal(vm.editTarget.version, 8)
  assert.equal(vm.editVisible, true); assert.match(vm.editNotice, /修改已保存/)
  assert.equal(vm.editForm.income, '0'); assert.equal(vm.busy, false)
})

test('navigation keeps unsubmitted input when leaving is cancelled', async () => {
  const vm = make({}, {}, { showModal: options => options.success({ confirm: false }) })
  vm.form.reason = '还没填完'
  assert.equal(await vm.beforeBack(), false)
  assert.equal(vm.form.reason, '还没填完')
})

test('detail refresh uses the authoritative current level rather than the historical application', async () => {
  const vm = make({ getMyAid: async () => ({ currentLevel:'SPECIAL', items:[{applyId:'2',finalLevel:'SPECIAL'}] }), getAidBatches:async()=>({items:[]}) },
    { getAidDetail:async()=>({applyId:'1',status:'APPROVED',finalLevel:'GENERAL'}) })
  vm.d = { currentLevel:'GENERAL', items:[{applyId:'1'}] }
  await vm.openDetail({applyId:'1'})
  assert.equal(vm.detail.finalLevel,'GENERAL')
  assert.equal(vm.d.currentLevel,'SPECIAL')
  assert.equal(vm.d.items[0].applyId,'2')
})
