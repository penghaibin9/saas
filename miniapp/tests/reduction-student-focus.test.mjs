import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
const source=fs.readFileSync(new URL('../src/pages/student/affairs/reduction.vue', import.meta.url),'utf8')
function mount(api){
 const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm,'').replace('export default','return')
 const c=new Function('studentApi','fileSdk','normalizeError','toast','uni',script)(api,{},e=>({text:e.message}),()=>{},{})
 const vm={...c.data(),...c.methods};for(const [key,get] of Object.entries(c.computed))Object.defineProperty(vm,key,{get:()=>get.call(vm)})
 return {vm,c}
}
test('student correction deep link selects the original application without ID precision loss',async()=>{
 const id='9007199254740993', row={feeId:id,status:'RETURNED',allowedActions:['RESUBMIT']}
 const {vm}=mount({getMyFeeReductions:async()=>({items:[{feeId:'1'},row]})})
 vm.recordId=id;await vm.load();assert.deepEqual(vm.visibleItems,[row]);assert.equal(vm.allows(row,'RESUBMIT'),true)
 vm.recordId='999';assert.deepEqual(vm.visibleItems,[])
})
test('correction failure retains original application, input and version for retry',async()=>{
 let request
 const {vm}=mount({resubmitFeeReduction:async(id,payload)=>{request={id,payload};throw new Error('版本冲突，请核对') }})
 vm.openEdit({feeId:'2',version:1,itemType:'TEMP_AID',yearCode:'2026-2027',reasonCategory:'FAMILY_CHANGE',amount:'1200',reason:'家庭收入中断需要补充办理材料'})
 vm.form.reason='家庭收入自九月一日中断，预计持续一个月';vm.form.confirm=true;await vm.submit()
 assert.equal(request.id,'2');assert.equal(request.payload.version,1);assert.equal(vm.formOpen,true);assert.equal(vm.editing.feeId,'2');assert.match(vm.formError,/版本冲突/);assert.equal(vm.busy,'')
})
