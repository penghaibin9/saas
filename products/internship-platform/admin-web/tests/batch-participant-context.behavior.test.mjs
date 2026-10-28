import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const source=fs.readFileSync(new URL('../src/modules/internship/views/BatchDetailView.vue',import.meta.url),'utf8')
function page(api,raw=source){
  const body=raw.match(/<script>([\s\S]*?)<\/script>/)[1]
  const names=[...body.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"];?\s*/gm)].flatMap(([,v])=>v.replace(/[{}]/g,'').split(',').map(x=>x.trim()))
  const store={availableBatches:[{id:'9007199254741001'}],selectedBatchId:'9007199254741002',applyBatch(row){this.selectedBatchId=String(row.id)}}
  const deps=Object.fromEntries(names.map(k=>[k,{}]));Object.assign(deps,{internshipApi:api,useInternshipBatchStore:()=>store,toast:{success(){},error(){}}})
  const component=new Function(...names,body.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return'))(...names.map(k=>deps[k]))
  const navigations=[],vm={...component.data(),$route:{path:'/admin/internship/batches/9007199254741001',params:{id:'9007199254741001'},query:{setup:'participants',batchId:'9007199254741002'}},$router:{replace:dest=>navigations.push(dest)}}
  return{component,vm,store,navigations,load:()=>component.methods.load.call(vm)}
}
test('批次详情深链读取成功后，顶部批次恢复为当前对象，保留大编号精度',async()=>{
  const p=page({getBatchDetail:async()=>({code:0,data:{id:'9007199254741001',status:'RUNNING',batchName:'本次批次'}})})
  await p.load();assert.equal(p.store.selectedBatchId,'9007199254741001');assert.equal(p.vm.detail.id,p.store.selectedBatchId)
  assert.deepEqual(p.navigations,[{path:'/admin/internship/batches/9007199254741001',query:{setup:'participants',batchId:'9007199254741001'}}])
})
test('切换顶部批次进入对应详情，沿用参与名单分区并关闭旧确认',()=>{
  const p=page({});Object.assign(p.vm,{loading:false,detail:{id:'9007199254741001'},confirmVisible:true})
  p.component.watch['$route.query.batchId'].call(p.vm,'9007199254741002')
  assert.deepEqual(p.navigations,[{path:'/admin/internship/batches/9007199254741002',query:{setup:'participants',batchId:'9007199254741002'}}]);assert.equal(p.vm.confirmVisible,false)
  for(const invalid of ['bad','9007199254741001',['1','2']])p.component.watch['$route.query.batchId'].call(p.vm,invalid)
  assert.equal(p.navigations.length,1)
})
test('失权和迟到详情不回填旧批次到顶部或继续办理',async()=>{
  const denied=page({getBatchDetail:async()=>({code:403,message:'无权查看该批次'})});await denied.load();assert.equal(denied.vm.detail,null);assert.match(denied.vm.error,/无权/)
  let resolve;const p=page({getBatchDetail:()=>new Promise(r=>resolve=r)}),pending=p.load();p.vm.$route.params.id='new'
  resolve({code:0,data:{id:'9007199254741001'}});await pending;assert.equal(p.vm.detail,null);assert.equal(p.store.selectedBatchId,'9007199254741002')
})
const child=fs.readFileSync(new URL('../src/modules/internship/views/components/BatchParticipantScope.vue',import.meta.url),'utf8')
test('补录和移出提交成功后通知父页回读实际人数，失败仍保留原输入',async()=>{
  for(const failed of [false,true]){
    const p=page({addBatchParticipants:async()=>({code:failed?403:0,data:{added:1}})},child),events=[]
    Object.assign(p.vm,{batchId:'18',canAdjustRoster:true,manualStudentIds:['19'],manualAddReason:'补录说明',load:async()=>{},$emit:name=>events.push(name)})
    await p.component.methods.addManualParticipants.call(p.vm)
    assert.deepEqual(events,failed?[]:['changed']);assert.deepEqual(p.vm.manualStudentIds,failed?['19']:[])
  }
  const p=page({removeBatchParticipant:async()=>({code:0})},child),events=[]
  Object.assign(p.vm,{batchId:'18',canAdjustRoster:true,removeVisible:true,removeRow:{id:'member',version:2},load:async()=>{},$emit:name=>events.push(name)})
  await p.component.methods.confirmRemove.call(p.vm,{reason:'合成名单调整'});assert.deepEqual(events,['changed']);assert.equal(p.vm.removeVisible,false)
})
test('补录期间切批次，旧回包不能清空新输入或刷新新批次计数',async()=>{
  let resolve;const p=page({addBatchParticipants:()=>new Promise(r=>resolve=r)},child),events=[]
  Object.assign(p.vm,{batchId:'18',canAdjustRoster:true,manualStudentIds:['19'],manualAddReason:'原输入',load:async()=>{},$emit:name=>events.push(name)})
  const work=p.component.methods.addManualParticipants.call(p.vm);p.vm.batchId='20';p.vm.manualStudentIds=['21'];resolve({code:0,data:{added:1}});await work
  assert.deepEqual(events,[]);assert.deepEqual(p.vm.manualStudentIds,['21'])
})
