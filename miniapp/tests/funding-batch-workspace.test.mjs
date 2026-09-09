import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

const source = fs.readFileSync(new URL('../src/pages/student/affairs/funding.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm,'').replace('export default','return')
function make(api = {}) {
  const component = new Function('studentApi','normalizeError','toast',script)(api,e=>({text:e.message}),()=>{})
  const vm = {...component.data(),...component.methods,applyFocus:()=>{}}
  for (const [name,getter] of Object.entries(component.computed)) Object.defineProperty(vm,name,{get:()=>getter.call(vm)})
  return vm
}

test('mini funding keeps selected ID across paging, searches, refreshes and failures', async () => {
  const calls=[]; let fail=false
  const vm=make({getMyFunding:async()=>{if(fail)throw Error('offline'); return {items:[]}},getFundingBatches:async p=>{
    if(fail)throw Error('offline'); calls.push(p); return {items:[{batchId:p.keyword?'match':'chosen'}],total:40}
  }})
  await vm.load(); assert.equal(vm.selectedBatch,null)
  vm.onBatch({detail:{value:0}}); vm.form.reason='已经填写的申请理由'; vm.form.commit=true
  vm.batchQuery='历史'; await vm.loadBatches()
  assert.equal(vm.selectedBatch.batchId,'chosen'); assert.equal(vm.batchOptions[vm.batchIndex].batchId,'chosen')
  vm.batchQuery='尚未搜索'; await vm.loadBatches(true)
  assert.deepEqual(calls.at(-1),{page:2,pageSize:20,keyword:'历史',projectType:'SCHOLARSHIP'})
  fail=true; await vm.load()
  assert.equal(vm.state,'ready'); assert.equal(vm.selectedBatch.batchId,'chosen')
  assert.equal(vm.form.reason,'已经填写的申请理由'); assert.equal(vm.form.commit,true)
  assert.match(vm.batchError,/已保留/); assert.match(vm.loadError,/仍保留/)
})

test('type change clears old target and confirmation before new results, ignores stale requests', async () => {
  let resolveOld
  const vm=make({getFundingBatches:p=>p.projectType==='SCHOLARSHIP'?new Promise(r=>{resolveOld=r}):Promise.resolve({items:[{batchId:'grant'}],total:1})})
  const old=vm.loadBatches(); vm.selectedBatch={batchId:'old'}; vm.form.commit=true
  vm.form.reason='保留说明'; await vm.changeType('GRANT')
  resolveOld({items:[{batchId:'stale'}],total:1}); await old
  assert.equal(vm.allBatches[0].batchId,'grant'); assert.equal(vm.selectedBatch,null)
  assert.equal(vm.form.commit,false); assert.equal(vm.form.reason,'保留说明')
})

test('submit uses explicit ID, accepts 1000 characters and blocks duplicates or target changes while busy', async () => {
  let finish; const calls=[]
  const vm=make({applyFunding:body=>{calls.push(body);return new Promise(r=>{finish=r})}})
  vm.load=()=>{}; vm.selectedBatch={batchId:'chosen'}; vm.allBatches=[{batchId:'other'}]
  vm.form={reason:'理'.repeat(1001),commit:true}; await vm.submitApply(); assert.equal(calls.length,0)
  vm.form.reason='理'.repeat(1000)
  const submit=vm.submitApply(); await vm.submitApply(); vm.changeType('GRANT'); vm.onBatch({detail:{value:1}})
  assert.equal(calls.length,1); assert.equal(calls[0].batchId,'chosen')
  assert.equal(vm.fundType,'SCHOLARSHIP'); assert.equal(vm.selectedBatch.batchId,'chosen')
  finish({}); await submit; assert.equal(vm.form.reason,''); assert.equal(vm.form.commit,false)
})

test('rejected new application preserves statement, files and selected batch', async () => {
  const vm=make({applyFunding:async()=>{throw Error('该批次申请已截止')}})
  vm.selectedBatch={batchId:'expired'}; vm.form={reason:'写好的申请说明',commit:true}; vm.fileIds=['123']
  await vm.submitApply()
  assert.equal(vm.form.reason,'写好的申请说明'); assert.deepEqual(vm.fileIds,['123'])
  assert.equal(vm.selectedBatch.batchId,'expired'); assert.equal(vm.busy,false)
})

test('funding progress separates award eligibility from payment and ends rejected applications', () => {
  const vm = make()
  assert.match(source, /<MobileStatusTag :status="x.status" :label="x.statusLabel"/)
  assert.match(vm.workflowHint({status:'GRANTED', statusLabel:'已获资助'}), /实际发放情况以学校发放记录为准/)
  assert.match(vm.workflowHint({status:'REJECTED', statusLabel:'已驳回'}), /流程已结束/)
  assert.match(vm.workflowHint({status:'COUNSELOR_REVIEW', statusLabel:'辅导员初审'}), /负责本次评审的老师/)
  assert.match(vm.workflowHint({status:'RETURNED', statusLabel:'已退回', allowedActions:['EDIT_RETURNED']}), /修改后重新提交/)
  assert.match(vm.workflowHint({status:'PUBLICITY', statusLabel:'公示中', hasPendingAppeal:true}), /等待复核/)
})
