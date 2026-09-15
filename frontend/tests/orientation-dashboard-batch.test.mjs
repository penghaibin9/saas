import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const source=fs.readFileSync(new URL('../src/views/admin/orientation/OrientationDashboardView.vue',import.meta.url),'utf8')
const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','return')
function setup(api){
 const names=['BusinessMetrics','ModulePageShell','LoadingState','ErrorState','RiskTag','getOrientationContext','getOrientationDashboard','getOrientationBatches']
 const component=new Function(...names,script)(...names.map(k=>api[k]||{}))
 const vm={...component.data(),$router:{push(v){vm.destination=v}}}
 for(const [k,fn] of Object.entries(component.methods))vm[k]=fn.bind(vm)
 for(const [k,fn] of Object.entries(component.computed))Object.defineProperty(vm,k,{get:()=>fn.call(vm)})
 vm.$unmount=()=>component.beforeUnmount.call(vm)
 return vm
}
test('dashboard reads every batch page and carries the chosen batch to students',async()=>{
 const pages=[],queries=[]
 const vm=setup({getOrientationBatches:async p=>{pages.push(p.page);return {code:0,data:{list:[{id:p.page}],total:2}}},getOrientationContext:async()=>({code:0,data:{}}),getOrientationDashboard:async p=>{queries.push(p);return {code:0,data:{batchId:p.batchId}}}})
 vm.selectedBatch='2';await vm.load()
 assert.deepEqual(pages,[1,2]);assert.equal(vm.batches.length,2)
 assert.deepEqual(queries,[{batchId:'2'}])
 vm.go('/admin/orientation/students')
 assert.deepEqual(vm.destination,{path:'/admin/orientation/students',query:{batchId:'2'}})
})

test('primary action enters this exact batch roster and empty batch explains next step',()=>{
 const vm=setup({})
 vm.board={batchId:'1000000000000000999',kpis:[{key:'total',value:'0'}]}
 vm.openRoster()
 assert.deepEqual(vm.destination,{path:'/admin/orientation/batches',query:{batchId:'1000000000000000999',panel:'students'}})
 assert.match(vm.nextHint,/新增或导入/)
 vm.batches=[{id:vm.board.batchId,status:'CLOSED'}]
 assert.match(vm.nextHint,/已结束/)
})

test('server failure clears old counts and never masquerades as an empty success',async()=>{
 const vm=setup({getOrientationContext:async()=>({code:0,data:{}}),getOrientationDashboard:async()=>({code:1,message:'看板连接失败'})})
 vm.batchesLoaded=true;vm.board={batchId:'old'}
 await vm.load()
 assert.equal(vm.board,null);assert.equal(vm.error,'看板连接失败');assert.equal(vm.loading,false)
})

test('unloaded dashboard ignores a late response',async()=>{
 let finish
 const vm=setup({getOrientationContext:async()=>({code:0,data:{}}),getOrientationDashboard:()=>new Promise(resolve=>{finish=resolve})})
 vm.batchesLoaded=true
 const pending=vm.load();vm.$unmount();finish({code:0,data:{batchId:'old'}})
 await pending;assert.equal(vm.board,null)
})

test('scoped follow-up destinations preserve exact batch ID',()=>{
 const vm=setup({});vm.board={batchId:'1000000000000000999'}
 for(const path of ['verify','progress','no-show','statistics','exceptions']){
  vm.go('/admin/orientation/'+path)
  assert.deepEqual(vm.destination,{path:'/admin/orientation/'+path,query:{batchId:vm.board.batchId}})
 }
 vm.go('/admin/orientation/flow-config')
 assert.equal(vm.destination,'/admin/orientation/flow-config')
})
test('late dashboard response cannot replace a newer batch',async()=>{
 let resolveOld
 const vm=setup({getOrientationContext:async()=>({code:0,data:{}}),getOrientationDashboard:p=>p.batchId==='1'?new Promise(r=>{resolveOld=r}):Promise.resolve({code:0,data:{batchId:'2'}})})
 vm.batchesLoaded=true;vm.selectedBatch='1';const old=vm.load()
 vm.selectedBatch='2';await vm.load()
 resolveOld({code:0,data:{batchId:'1'}});await old
 assert.equal(vm.board.batchId,'2');assert.equal(vm.loading,false)
})

test('batch picker changes route without issuing an extra request before route remount',()=>{
 const vm=setup({});let calls=0,destination
 vm.load=()=>{calls++};vm.$route={query:{batchId:'old'}}
 vm.$router.replace=value=>{destination=value};vm.selectedBatch='17'
 vm.changeBatch()
 assert.equal(calls,0);assert.deepEqual(destination,{query:{batchId:'17'}})
})
