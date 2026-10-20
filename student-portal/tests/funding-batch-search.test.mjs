import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/affairs/AffairsFourEndView.vue', import.meta.url), 'utf8')
const code = source.slice(source.indexOf('const fundingBatchQuery ='), source.indexOf('const TAB_LOADERS ='))
function make(api) {
  const ref = value => ({ value }), computed = get => ({ get value() { return get() } })
  const fundingBatches = ref([]), fundForm = { batchId:'', projectType:'SCHOLARSHIP', statement:'已填写的申请', confirm:false }
  return new Function('ref','computed','portalApi','fundingBatches','fundForm','viewActive', code + ';return {fundingBatches,fundForm,fundingBatchQuery,fundingBatchOptions,fundingBatchError,loadFundingBatches,selectFundingBatch,changeFundingType}')(ref, computed, api, fundingBatches, fundForm, true)
}

test('funding searches and pagination never silently change the application batch', async () => {
  const calls = []
  const vm = make({affairsFundingBatches:async p => { calls.push(p); return {items:[{batchId:p.keyword?'match':'chosen'}],total:40} }})
  await vm.loadFundingBatches(); assert.equal(vm.fundForm.batchId, '')
  vm.fundForm.batchId='chosen'; vm.selectFundingBatch(); vm.fundForm.confirm=true
  vm.fundingBatchQuery.value='历史'; await vm.loadFundingBatches()
  assert.equal(vm.fundForm.batchId,'chosen'); assert.equal(vm.fundingBatchOptions.value[0].batchId,'chosen')
  assert.equal(vm.fundForm.statement,'已填写的申请'); assert.equal(vm.fundForm.confirm,true)
  vm.fundingBatchQuery.value='尚未搜索'; await vm.loadFundingBatches(true)
  assert.deepEqual(calls.at(-1),{page:2,pageSize:20,keyword:'历史',projectType:'SCHOLARSHIP'})
})

test('changing project type invalidates selection and confirmation, and rejects stale responses', async () => {
  let resolveOld
  const vm = make({affairsFundingBatches:p => p.projectType==='SCHOLARSHIP' ? new Promise(r=>{resolveOld=r}) : Promise.resolve({items:[{batchId:'grant'}],total:1})})
  const old = vm.loadFundingBatches()
  vm.fundForm.batchId='scholarship'; vm.fundForm.confirm=true; vm.fundForm.projectType='GRANT'
  await vm.changeFundingType()
  resolveOld({items:[{batchId:'stale'}],total:1}); await old
  assert.equal(vm.fundingBatches.value[0].batchId,'grant'); assert.equal(vm.fundForm.batchId,'')
  assert.equal(vm.fundForm.confirm,false); assert.equal(vm.fundForm.statement,'已填写的申请')
})

test('funding query failure retains existing selection and rows for recovery', async () => {
  const vm = make({affairsFundingBatches:async()=>{throw Error('offline')}})
  vm.fundingBatches.value=[{batchId:'chosen'}]; vm.fundForm.batchId='chosen'; vm.selectFundingBatch()
  await vm.loadFundingBatches()
  assert.equal(vm.fundForm.batchId,'chosen'); assert.equal(vm.fundingBatches.value.length,1)
  assert.match(vm.fundingBatchError.value,/已保留/)
})

test('batch searches are not unsaved work; submitted forms clear while outstanding appeals remain protected', () => {
  const guard = source.slice(source.indexOf('function fundingHasEdits()'), source.indexOf('watch(tab, (key) =>'))
  const busy={value:false}, form={statement:'',confirm:false,batchId:'chosen'}, appeals={}, modal={type:''}
  const attachments={busy:false,hasDraft:false}
  const check=new Function('busy','fundForm','fundAppeals','modal','fundingAttachments',guard+'; return fundingHasEdits')(busy,form,appeals,modal,attachments)
  assert.equal(check(),false)
  form.statement='尚未提交'; assert.equal(check(),true)
  form.statement=''; busy.value=true; assert.equal(check(),true)
  busy.value=false; assert.equal(check(),false)
  appeals['1']='另一条未提交的申诉'; assert.equal(check(),true)
  delete appeals['1']; modal.type='funding'; assert.equal(check(),true)
  modal.type=''; attachments.hasDraft=true; assert.equal(check(),true)
})
