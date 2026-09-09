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
test('late dashboard response cannot replace a newer batch',async()=>{
 let resolveOld
 const vm=setup({getOrientationContext:async()=>({code:0,data:{}}),getOrientationDashboard:p=>p.batchId==='1'?new Promise(r=>{resolveOld=r}):Promise.resolve({code:0,data:{batchId:'2'}})})
 vm.batchesLoaded=true;vm.selectedBatch='1';const old=vm.load()
 vm.selectedBatch='2';await vm.load()
 resolveOld({code:0,data:{batchId:'1'}});await old
 assert.equal(vm.board.batchId,'2');assert.equal(vm.loading,false)
})
