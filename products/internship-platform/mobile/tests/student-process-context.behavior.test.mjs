import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { normalizeError } from './request-module.mjs'

const source=fs.readFileSync(new URL('../src/pages/student-internship/process-facts/index.vue',import.meta.url),'utf8')
function page(overrides={}) {
  let generation=1
  const calls=[]
  const deps={studentApi:{getInternship:async batch=>{calls.push(['dashboard',batch]);return {hasBatch:true,batchId:batch||'18',recordId:'18'}}},studentInternshipRotations:async(...args)=>{calls.push(['rotations',...args]);return []},studentInternshipPayroll:async(...args)=>{calls.push(['payroll',...args]);return []},studentInternshipRotationSelfEvaluation:async()=>calls.push(['write']),studentInternshipPayrollSubmit:async()=>calls.push(['write']),openBusinessFile(){},uploadBusinessFile(){},toast(){},go:()=>calls.push(['home']),normalizeError,currentSessionGeneration:()=>generation,...overrides}
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...component.data()}
  for(const[key,fn]of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  return {vm,calls,component,setGeneration:value=>{generation=value}}
}
test('轮岗工资沿显式批次读取本人记录；单记录保留，零金额和零分不变为空',async()=>{
  const p=page();p.vm.requestedBatchId='18';await p.vm.load()
  assert.deepEqual(p.calls,[['dashboard','18'],['rotations','18','18'],['payroll','18','18']]);assert.equal(p.vm.state,'ready')
  p.vm.openPayroll({id:'1',payMonth:'2026-10',current:{actualAmount:0}});assert.equal(p.vm.payrollForm.actualAmount,'0');p.vm.closePayroll();assert.equal(p.vm.payrollForm.visible,false)
  assert.equal(p.vm.scoreText(0),'0.0');assert.equal(p.vm.scoreText(null),'—');assert.match(p.vm.money(0),/0.00/);assert.equal(p.vm.money(null),'未填写')
  const single=page();await single.vm.load();assert.equal(single.vm.context.internshipId,'18')
})
test('缺少实习记录显示原因和返回入口；错误、无权及异常数据不能伪装空白成功',async()=>{
  for(const dashboard of [{hasBatch:false,needSelect:true,message:'请选择实习批次'},{hasBatch:false,message:'当前暂无实习安排'},{hasBatch:true,batchId:'18'}]){
    const p=page({studentApi:{getInternship:async()=>dashboard}});await p.vm.load();assert.notEqual(p.vm.state,'ready');assert.ok(p.vm.error);assert.equal(p.calls.length,0);p.vm.returnHome();assert.deepEqual(p.calls,[['home']]);p.vm.openPayroll();assert.equal(p.vm.payrollForm.visible,false)
  }
  for(const [error,state]of [[{httpStatus:403,bizCode:'NO_PERMISSION'},'forbidden'],[{httpStatus:503},'error']]){
    const p=page({studentApi:{getInternship:async()=>{throw error}}});await p.vm.load();assert.equal(p.vm.state,state);assert.ok(p.vm.error)
  }
  const malformed=page({studentInternshipRotations:async()=>({items:[]})});await malformed.vm.load();assert.equal(malformed.vm.state,'error')
})
test('迟到读取不能跨批次、离页或账号回填；同原单重读保留草稿',async()=>{
  let resolve
  const p=page({studentApi:{getInternship:()=>new Promise(r=>resolve=r)}});p.vm.requestedBatchId='18';const pending=p.vm.load();p.component.onHide.call(p.vm);resolve({hasBatch:true,batchId:'18',recordId:'18'});await pending;assert.equal(p.calls.length,0);assert.equal(p.vm.context.internshipId,'')
  const account=page({studentInternshipRotations:()=>new Promise(r=>resolve=r)});const late=account.vm.load();await new Promise(r=>setImmediate(r));account.setGeneration(2);resolve([{id:'wrong'}]);await late;assert.deepEqual(account.vm.rotations,[])
  const switched=page({studentApi:{getInternship:async()=>({hasBatch:true,batchId:'19',recordId:'19'})}});switched.vm.requestedBatchId='18';await switched.vm.load();assert.equal(switched.vm.state,'error');assert.equal(switched.calls.length,0)
  const same=page();await same.vm.load();same.vm.selfDrafts={r:{text:'未提交的自评',rating:0}};same.vm.openPayroll();same.vm.payrollForm.actualAmount='0';same.vm.payrollForm.evidenceFileId='100000000000000001';await same.vm.load();assert.equal(same.vm.selfDrafts.r.text,'未提交的自评');assert.equal(same.vm.payrollForm.actualAmount,'0');assert.equal(same.vm.payrollForm.evidenceFileId,'100000000000000001')
})
