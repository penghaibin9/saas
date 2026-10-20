import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/affairs/AffairsFourEndView.vue', import.meta.url), 'utf8')
const code = source.slice(source.indexOf('const aidBatchQuery ='), source.indexOf('const fundingLabel ='))
function make(api) {
  const ref = value => ({value}), computed = get => ({get value() {return get()}})
  const aidBatches = ref([]), aidForm = {batchId:'',statement:'未提交内容'}
  return new Function('ref','computed','portalApi','aidBatches','aidForm','viewActive', code + ';return {aidBatches,aidForm,aidBatchQuery,aidBatchLoading,aidBatchError,aidBatchOptions,loadAidBatches,selectAidBatch}')(ref, computed, api, aidBatches, aidForm, true)
}
test('PC batch selection survives filtered search and pagination without changing form target', async () => {
  const calls = []
  const vm = make({affairsAidBatches:async p=>{
    calls.push(p); return {items:[{batchId:p.page===2?'old':(p.keyword?'match':'new')}],total:2}
  }})
  await vm.loadAidBatches(); assert.equal(vm.aidForm.batchId,'')
  await vm.loadAidBatches(true)
  vm.aidForm.batchId='old'; vm.selectAidBatch()
  vm.aidBatchQuery.value='历史'; await vm.loadAidBatches()
  assert.equal(vm.aidForm.batchId,'old'); assert.equal(vm.aidBatchOptions.value[0].batchId,'old')
  assert.equal(vm.aidForm.statement,'未提交内容')
  vm.aidBatchQuery.value='未执行搜索'; await vm.loadAidBatches(true)
  assert.deepEqual(calls.at(-1),{page:2,pageSize:20,keyword:'历史'})
})
test('PC old search response and failure preserve latest results and selected application', async () => {
  let a, b, calls=0
  const vm = make({affairsAidBatches:()=>new Promise(resolve=>{if(++calls===1)a=resolve;else b=resolve})})
  const first=vm.loadAidBatches(), latest=vm.loadAidBatches()
  b({items:[{batchId:'latest'}],total:1});await latest
  a({items:[{batchId:'stale'}],total:1});await first
  assert.equal(vm.aidBatches.value[0].batchId,'latest')
  const failed=make({affairsAidBatches:async()=>{throw Error('offline')}})
  failed.aidForm.batchId='selected';await failed.loadAidBatches()
  assert.equal(failed.aidForm.batchId,'selected');assert.match(failed.aidBatchError.value,/已保留/)
  assert.equal(failed.aidBatchLoading.value,false)
})
