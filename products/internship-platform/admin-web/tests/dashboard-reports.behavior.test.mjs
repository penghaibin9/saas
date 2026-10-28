import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { workRoute,REQUIRED_PERMISSIONS } from '../src/modules/internship/components/command-screen/screen-core.mjs'
import { safeLocalizedText } from '../src/utils/presentationSafety.js'

function component(relative,deps={}){
  const source=fs.readFileSync(new URL(relative,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*? from [^\n]+\n/gm,'').replace('export default','return')
  const imported=[...source.matchAll(/^import ([\s\S]*?) from [^\n]+$/gm)].flatMap(([,names])=>names.replace(/[{}]/g,'').split(',').map(name=>name.trim()))
  return new Function(...imported,script)(...imported.map(name=>deps[name] ?? {}))
}
test('三类过程报告待办按编号重建准确深链，拒绝无权限和不可信地址',()=>{
  const context={batchId:'9007199254741001',grants:{'internship.report.view':true}}
  for(const kind of ['DAILY_REPORT','MONTHLY_REPORT','SUMMARY_REPORT']){
    const item={kind,objectId:'9007199254741002',route:'https://invalid.example/private'}
    assert.equal(workRoute(item,context),'/admin/internship/process-reports/9007199254741002?batchId=9007199254741001')
    assert.equal(workRoute(item,{...context,grants:{}}),null)
    assert.equal(workRoute({...item,objectId:'../bad'},context),null)
  }
})
test('导师工作台三类报告的计数、筛选、原单入口和连续批阅队列一致',()=>{
  const routes=[],queues=[],store={selectedBatchId:'77',withBatchQuery:query=>({...query,batchId:'77'})}
  const c=component('../src/modules/internship/views/InternshipDashboardView.vue',{workRoute,REQUIRED_PERMISSIONS,useInternshipBatchStore:()=>store,matchPermission:(grants,code)=>grants.includes(code),withInternshipBatch:path=>path,saveReviewQueue:value=>queues.push(value)})
  const rows=['DAILY','MONTHLY','SUMMARY'].map((type,i)=>({kind:type+'_REPORT',objectId:String(91+i)}))
  const vm={...c.data(),loading:false,hero:{workItems:rows,workItemTotal:3},ctx:{permissionPatterns:['internship.report.view','internship.report.review']},$router:{push:path=>routes.push(path)}}
  for(const [key,method] of Object.entries(c.methods))vm[key]=(...args)=>method.apply(vm,args)
  for(const [key,get] of Object.entries(c.computed))Object.defineProperty(vm,key,{get:()=>get.call(vm)})
  for(const row of rows){vm.workFilter=row.kind;assert.equal(vm.workItems.length,1);assert.equal(vm.workKinds.find(item=>item.value===row.kind).count,1);vm.openWorkItem(row);assert.match(routes.at(-1),new RegExp('/process-reports/'+row.objectId+'\\?batchId=77'));assert.equal(queues.at(-1).kind,'process-report');assert.deepEqual(queues.at(-1).ids,[row.objectId]);assert.match(vm.activeQueue.path,/type=(daily|monthly|summary)/)}
})
test('求助来源、受理与办结留痕使用中文业务语义',()=>{
  const c=component('../src/modules/internship/views/RiskDisposalView.vue',{safeLocalizedText,formatDateTime:()=>''})
  const vm={detail:{riskCode:'INT-R-HELP',status:'CLOSED',sourceModule:'student_help',auditTrail:[{action:'STUDENT_HELP',detail:{content:'原始求助说明'}},{action:'HANDLE'},{action:'CLOSE'}]}}
  for(const [key,method] of Object.entries(c.methods))vm[key]=(...args)=>method.apply(vm,args)
  assert.equal(vm.sourceModuleLabel('student_help'),'学生主动求助');assert.equal(vm.sourceText('INT-R-HELP 虚构咨询'),'学生主动求助 · 虚构咨询')
  assert.equal(c.computed.summaryItems.call(vm).find(item=>item.label==='当前动作').value,'已办结，可查看处理记录')
  const trail=c.computed.auditRecords.call(vm);assert.deepEqual(trail.map(row=>row.actionLabel),['学生提交求助','受理','关闭办结']);assert.equal(trail[0].reason,'原始求助说明')
})
