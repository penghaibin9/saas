import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/modules/studentAffairs/views/dorm/DormBatchCheckinWorkspace.vue', import.meta.url), 'utf8')
const script = source.split('<script>')[1].split('</script>')[0].replace(/^import .*$/gm, '').replace('export default', 'return')
function setup(api) {
  const component = new Function('api', 'AppConfirmDialog', 'AppDormBuildingPicker', 'AppGlobalState', 'AppInlineAlert', 'AppPermissionButton', 'DataTable', script)(api)
  const vm = { ...component.data(), $route: { query: {} }, $router: { async replace() {} } }
  for (const [key, method] of Object.entries(component.methods)) vm[key] = method.bind(vm)
  return { vm, component }
}

test('lost create response retains the same request ID and does not execute unseen job', async () => {
  const ids = []
  const { vm } = setup({ async createDormCheckinBatch(body) { ids.push(body.clientRequestId); throw Error('断网') } })
  vm.selection = [{ stayId: '9007199254740999', version: 3 }]
  vm.arrivalConfirmed = true
  await vm.create(); await vm.create()
  assert.equal(ids.length, 2)
  assert.equal(ids[0], ids[1])
  assert.equal(vm.selection[0].stayId, '9007199254740999')
  assert.equal(vm.busy, false)
})

test('a late query cannot replace a newer building result', async () => {
  const pending = []
  const { vm } = setup({ listDormStays() { return new Promise(resolve => pending.push(resolve)) } })
  const old = vm.load(); const latest = vm.load()
  pending[1]({ data: { items: [{ stayId: 'new' }], total: 1 } }); await latest
  pending[0]({ data: { items: [{ stayId: 'old' }], total: 1 } }); await old
  assert.equal(vm.rows[0].stayId, 'new')
})

test('a lost continuation response reads receipts without replaying the write', async () => {
  let writes = 0
  const { vm } = setup({
    async continueDormCheckinBatch() { writes++; throw Error('断网') },
    async getDormCheckinBatch() { return { data: { jobId: '5', success: 20, failed: 0, pending: 3, total: 23 } } },
    async listDormStays() { return { data: { items: [], total: 3 } } }
  })
  vm.job = { jobId: '5', pending: 23 }
  await vm.continueJob()
  assert.equal(writes, 1)
  assert.equal(vm.job.pending, 3)
  assert.equal(vm.job.success, 20)
  assert.equal(vm.busy, false)
})

test('batch and class IDs stay strings from filter to selected roster',async()=>{
 const calls=[];const {vm}=setup({async listDormStays(q){calls.push(q);return {data:{items:[{stayId:'8',version:2}],total:1}}}})
 vm.orientationBatchId='9007199254740993';vm.classId='9007199254740995';await vm.load()
 assert.equal(calls[0].orientationBatchId,vm.orientationBatchId);assert.equal(calls[0].classId,vm.classId)
 await vm.selectAll();assert.equal(vm.selection[0].stayId,'8');assert.equal(vm.selection[0].version,2)
})

test('selecting all loads bounded pages without rendering the whole roster',async()=>{
 const calls=[];const {vm}=setup({async listDormStays(q){calls.push(q);return {data:{items:q.pageSize===50?[]:Array.from({length:q.page===1?200:1},(_,i)=>({stayId:String((q.page-1)*200+i+1),version:1})),total:201}}}})
 await vm.selectAll();assert.equal(vm.selection.length,201);assert.deepEqual(calls.slice(0,2).map(q=>[q.page,q.pageSize]),[[1,200],[2,200]])
 assert.equal(vm.rows.length,0);assert.equal(vm.selecting,false)
})

test('a changing roster never silently creates a partial selection',async()=>{
 const {vm}=setup({async listDormStays(q){return {data:{items:[{stayId:String(q.page),version:1}],total:q.page===1?2:1}}}})
 await vm.selectAll();assert.deepEqual(vm.selection,[]);assert.match(vm.error,/名单发生变化/)
})

test('cancelling roster read discards late selection',async()=>{
 let finish;const {vm}=setup({listDormStays(){return new Promise(resolve=>finish=resolve)}})
 const reading=vm.selectAll();vm.cancelSelection();finish({data:{items:[{stayId:'late',version:1}],total:1}});await reading
 assert.equal(vm.selecting,false);assert.deepEqual(vm.selection,[])
})
