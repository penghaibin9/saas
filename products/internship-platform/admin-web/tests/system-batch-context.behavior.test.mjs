import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

function harness(handler, saved='') {
  let generation=1
  const source=fs.readFileSync(new URL('../src/stores/internshipBatch.js',import.meta.url),'utf8')
    .replace(/^import[^\n]*\n/gm,'').replace('export const useInternshipBatchStore =','return')
  const values=new Map(saved?[['internship.selectedBatchId',saved]]:[]),calls=[]
  const api={getBatchOptions:async params=>{calls.push(params);return handler(params)},getBatches:()=>{throw new Error('不应读取批次管理列表')}}
  const definition=new Function('defineStore','internshipApi','currentSessionGeneration','window',source)(
    (_name,options)=>options,api,()=>generation,{localStorage:{getItem:key=>values.get(key),setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)}})
  const vm=definition.state()
  for(const [name,fn] of Object.entries(definition.actions)) vm[name]=(...args)=>fn.apply(vm,args)
  return {vm,calls,changeIdentity:()=>generation++,values}
}
const row=(id,status='RUNNING')=>({id,batchName:'本院办理批次',batchNo:'B001',status,startDate:'2026-09-01',endDate:'2026-12-31'})
const result=(list,selected=null)=>({code:0,data:{list,selected}})

test('批次上下文使用受限目录，并回填列表页以外的已授权大编号',async()=>{
  const id='9007199254740993',other='9007199254740995'
  const p=harness(async()=>result([row(other)],row(id)))
  await p.vm.ensureLoaded({batchIdFromUrl:id})
  assert.equal(p.calls[0].selectedId,id)
  assert.equal(p.vm.selectedBatchId,id)
  assert.deepEqual(p.vm.availableBatches.map(item=>item.id),[other,id])
  assert.equal(p.vm.initialized,true)
})

test('服务端未授权的深链不能直接选中，也不能偷偷改选其他批次',async()=>{
  const p=harness(async()=>result([row('11')]))
  await p.vm.ensureLoaded({batchIdFromUrl:'12'})
  assert.equal(p.vm.batchLoadStatus,'INVALID_URL')
  assert.equal(p.vm.selectedBatchId,'')
  assert.equal(p.vm.invalidUrlBatch,true)
})

test('范围收回后清除原批次，权限拒绝显示拒绝状态而非无数据',async()=>{
  let response=result([row('11')])
  const p=harness(async()=>response)
  await p.vm.ensureLoaded()
  assert.equal(p.vm.selectedBatchId,'11')
  response=result([])
  await p.vm.ensureLoaded({force:true})
  assert.equal(p.vm.selectedBatchId,'')
  assert.deepEqual(p.vm.availableBatches,[])
  response=result([row('11')]);await p.vm.ensureLoaded({force:true})
  response={code:1,message:'当前身份没有实习业务办理权限'}
  await p.vm.ensureLoaded({force:true})
  assert.equal(p.vm.batchLoadStatus,'NO_PERMISSION')
  assert.equal(p.vm.selectedBatchId,'')
  assert.deepEqual(p.vm.availableBatches,[])
})

test('切换身份及并发重读时，迟到目录不能覆盖当前批次或结束新请求',async()=>{
  const pending=[]
  const p=harness(()=>new Promise(resolve=>pending.push(resolve)))
  const old=p.vm.ensureLoaded({force:true})
  p.changeIdentity()
  const current=p.vm.ensureLoaded({force:true})
  pending[0](result([row('old')]));await old
  assert.equal(p.vm.selectedBatchId,'')
  assert.equal(p.vm.batchLoading,true)
  pending[1](result([row('new')]));await current
  assert.equal(p.vm.selectedBatchId,'new')
  const first=p.vm.ensureLoaded({force:true}),last=p.vm.ensureLoaded({force:true})
  pending[3](result([row('last')]));await last
  pending[2](result([row('late')]));await first
  assert.equal(p.vm.selectedBatchId,'last')
})
