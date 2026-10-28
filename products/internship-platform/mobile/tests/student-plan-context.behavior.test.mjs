import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { normalizeError } from './request-module.mjs'
const source=fs.readFileSync(new URL('../src/pages/student-internship/plan/index.vue',import.meta.url),'utf8')
const context={batchId:'18',internshipId:'18'}
function page(overrides={}) {
  let generation=1
  const calls=[]
  const deps={studentApi:{getInternship:async batch=>{calls.push(['dashboard',batch]);return {hasBatch:true,...context,recordId:'18',schoolMentor:'本批次老师'}}},studentInternshipPlans:async(...args)=>{calls.push(['plans',...args]);return{context,items:[{planId:'61',isPrimary:true},{planId:'62'}]}},studentInternshipPlan:async(...args)=>{calls.push(['plan',...args]);return{context,id:args[0],planBatchId:'19',version:3,ackVersion:0,ackId:'70',ackStatus:'ACKNOWLEDGED'}},studentInternshipPlanTasks:async(...args)=>{calls.push(['tasks',...args]);return{context,planId:args[0],planVersion:3,ackVersion:0,ackId:'70',ackStatus:'ACKNOWLEDGED',minimumWords:10,tasks:[{sortOrder:1,progressId:args[0]+'1',progressVersion:0,progressStatus:'NOT_STARTED'}]}},studentInternshipPlanAcknowledge:async body=>calls.push(['ack',body]),studentInternshipPlanTaskSubmit:async(order,body)=>calls.push(['submit',order,body]),chooseSingleFile(){},uploadBusinessFile(){},toast(){},go(){},normalizeError,currentSessionGeneration:()=>generation,...overrides}
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...component.data()};for(const[key,fn]of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  return{vm,calls,component,setGeneration:value=>generation=value}
}
test('计划先读明确批次本人记录，再读同记录分配方案；提交携带同记录而非计划所属批次',async()=>{
  const p=page();p.vm.requestedBatchId='18';await p.vm.load();assert.deepEqual(p.calls.slice(0,4),[['dashboard','18'],['plans','18','18'],['plan','61','18','18'],['tasks','61','18','18']]);assert.equal(p.vm.context.advisorName,'本批次老师');assert.equal(p.vm.pageState,'ready')
  p.vm.tasks[0]._note='完成本次任务的过程与成果记录';await p.vm.submitTask(p.vm.tasks[0]);const write=p.calls.find(row=>row[0]==='submit');assert.equal(write[2].batchId,'18');assert.equal(write[2].internshipId,'18');assert.equal(write[2].expectedVersion,0)
})
test('计划缺记录、错误与迟到响应不变为假空或开放确认',async()=>{
  const missing=page({studentApi:{getInternship:async()=>({hasBatch:false,needSelect:true,message:'请选择批次'})}});await missing.vm.load();assert.equal(missing.calls.length,0);assert.equal(missing.vm.pageState,'empty');assert.match(missing.vm.error,/批次/)
  for(const [error,state]of [[{httpStatus:403},'forbidden'],[{httpStatus:503},'error']]){const p=page({studentInternshipPlans:async()=>{throw error}});await p.vm.load();assert.equal(p.vm.pageState,state);await p.vm.ack();assert.ok(!p.calls.some(row=>row[0]==='ack'))}
  let resolve;const late=page({studentInternshipPlans:()=>new Promise(r=>resolve=r)});const pending=late.vm.load();await new Promise(r=>setImmediate(r));late.component.onHide.call(late.vm);resolve({context,items:[{planId:'61'}]});await pending;assert.equal(late.vm.plan,null)
})
test('切换方案保留未提交说明、附件与原版本；回读变化要求明确核对',async()=>{
  const p=page();await p.vm.load();p.vm.tasks[0]._note='不能丢失的原方案完成说明';p.vm.tasks[0]._evidenceFileId='100000000000000001';await p.vm.load('62');await p.vm.load('61');assert.equal(p.vm.tasks[0]._note,'不能丢失的原方案完成说明');assert.equal(p.vm.tasks[0]._evidenceFileId,'100000000000000001');assert.equal(p.vm.tasks[0].progressVersion,0)
  let version=3;const changed=page({studentInternshipPlan:async()=>({context,id:'61',version,ackVersion:0,ackId:'70',ackStatus:'ACKNOWLEDGED'}),studentInternshipPlanTasks:async()=>({context,planId:'61',planVersion:version,ackVersion:0,ackId:'70',ackStatus:'ACKNOWLEDGED',tasks:[{sortOrder:1,progressId:'611',progressVersion:version-3,progressStatus:'NOT_STARTED'}]})});await changed.vm.load();changed.vm.tasks[0]._note='冲突前未提交的内容';version=4;await changed.vm.load();assert.equal(changed.vm.plan.version,3);assert.equal(changed.vm.tasks[0].progressVersion,0);assert.equal(changed.vm.tasks[0]._note,'冲突前未提交的内容');assert.ok(changed.vm.conflict)
})

test('移动计划真实请求适配携带明确本人上下文，大编号精度不变',async()=>{
  const source=fs.readFileSync(new URL('../src/services/internshipApi.js',import.meta.url),'utf8').replace(/^import[^\n]+/gm,'').replace(/export const /g,'const ')
  const urls=[],api=new Function('realRequest',source+';return {studentInternshipPlans,studentInternshipPlan,studentInternshipPlanTasks}')(url=>urls.push(url))
  const batch='9007199254741001',record='9007199254741002'
  await api.studentInternshipPlans(batch,record);await api.studentInternshipPlan('61',batch,record);await api.studentInternshipPlanTasks('61',batch,record)
  for(const url of urls){const params=new URL(url,'http://test').searchParams;assert.equal(params.get('batchId'),batch);assert.equal(params.get('internshipId'),record)}
  assert.equal(new URL(urls[2],'http://test').searchParams.get('planId'),'61')
})

test('任务凭证选择期间换账号不上传或回填旧任务，原说明保留',async()=>{
  let resolve,writes=0
  const p=page({chooseSingleFile:()=>new Promise(r=>resolve=r),uploadBusinessFile:async()=>{writes++;return{fileId:'old'}}});await p.vm.load();p.vm.tasks[0]._note='已有未提交任务草稿';const pending=p.vm.chooseEvidence(p.vm.tasks[0]);p.setGeneration(2);resolve({name:'proof.pdf',size:12});await pending;assert.equal(writes,0);assert.equal(p.vm.tasks[0]._evidenceFileId,'');assert.equal(p.vm.tasks[0]._note,'已有未提交任务草稿')
})
test('计划附件复用授权下载，切方案后文件工具停止打开旧文件',async()=>{
  let guard,id;const p=page({openBusinessFile:async(fileId,_name,options)=>{id=fileId;guard=options.isCurrent}})
  p.vm.planDetailScope='plan-61';await p.vm.openPlanFile({fileId:'789',fileName:'安排.xlsx'})
  assert.equal(id,'789');assert.equal(guard(),true);p.vm.planDetailScope='plan-62';assert.equal(guard(),false)
})
