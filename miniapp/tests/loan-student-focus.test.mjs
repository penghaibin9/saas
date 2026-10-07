import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
const source=fs.readFileSync(new URL('../src/pages/student/affairs/loan.vue', import.meta.url),'utf8')
function mount(api){
 const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm,'').replace('export default','return')
 const c=new Function('studentApi','fileSdk','normalizeError','toast','uni',script)(api,{},e=>({text:e.message}),()=>{},{})
 const vm={...c.data(),...c.methods};for(const [key,get] of Object.entries(c.computed))Object.defineProperty(vm,key,{get:()=>get.call(vm)})
 return {vm,c}
}
test('student correction deep link selects the original application without ID precision loss',async()=>{
 const id='9007199254740993', row={loanId:id,status:'RETURNED',allowedActions:['RESUBMIT']}
 const {vm}=mount({getMyLoans:async()=>({items:[{loanId:'1'},row]})})
 vm.recordId=id;await vm.load();assert.deepEqual(vm.visibleItems,[row]);assert.equal(vm.allows(row,'RESUBMIT'),true)
 vm.recordId='999';assert.deepEqual(vm.visibleItems,[])
})
