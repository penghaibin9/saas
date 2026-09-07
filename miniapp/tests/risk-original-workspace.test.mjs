import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const source=fs.readFileSync(new URL('../src/pages/teacher/risk-students/index.vue',import.meta.url),'utf8')
const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','return')
function mount(request,api={}){
 const c=new Function('ensureTeacherPerformanceApi','realRequest','affairsContractApi',script)(()=>{},request,api)
 return {...c.data(),...c.methods,_pageActive:true,recordId:'9007199254740993'}
}
test('risk focus reads exact business record and uses server actions',async()=>{
 let url
 const vm=mount(async path=>{url=path;return {riskId:'9007199254740993',version:4,allowedActions:['PROCESS'],handles:[]}})
 await vm.loadRisk();assert.equal(url,'/mobile/teacher/affairs/risk/9007199254740993');assert.equal(vm.can('PROCESS'),true);assert.equal(vm.can('CLOSE'),false)
})
test('failed risk action preserves notes and never auto-fetches a newer version',async()=>{
 let calls=0
 const vm=mount(()=>assert.fail('must not silently refresh'),{processRisk:async(id,note,version)=>{calls++;assert.equal(version,2);throw new Error('版本冲突')}})
 vm.risk={version:2,allowedActions:['PROCESS']};vm.note='处置过程已记录'
 await vm.saveRisk('PROCESS');assert.equal(vm.note,'处置过程已记录');assert.equal(vm.loadError,'版本冲突');assert.equal(calls,1)
 await vm.saveRisk('CLOSE');assert.equal(calls,1)
})
test('successful close reads back authority state and original handle history',async()=>{
 const vm=mount(async()=>({riskId:'9007199254740993',status:'CLOSED',allowedActions:[],handles:[{action:'CLOSE'}]}),{closeRisk:async(id,note,v)=>assert.equal(v,3)})
 vm.risk={version:3,allowedActions:['CLOSE']};vm.note='风险处置已经完成'
 await vm.saveRisk('CLOSE');assert.equal(vm.risk.status,'CLOSED');assert.equal(vm.risk.handles[0].action,'CLOSE');assert.equal(vm.note,'')
})
test('invalid deep link makes no request',async()=>{
 const vm=mount(()=>assert.fail('invalid request'));vm.recordId='x';await vm.loadRisk();assert.equal(vm.state,'error')
})
