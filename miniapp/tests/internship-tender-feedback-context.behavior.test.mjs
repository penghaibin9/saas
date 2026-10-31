import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { normalizeError } from './internship-request-module.mjs'
import { formatDateTime } from '../src/utils/format.js'

const source=fs.readFileSync(new URL('../src/pages/student-internship/feedback/index.vue',import.meta.url),'utf8')
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve}}
function page(api={},files={}){
  let generation=0;const messages=[]
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]*\n/gm,'').replace('export default','return')
  const calls={getInternship:async()=>({batchId:'3',recordId:'5'}),getInternshipFeedback:async()=>({items:[]}),...api}
  const component=new Function('studentApi','chooseSingleFile','uploadBusinessFile','toast','normalizeError','currentSessionGeneration','formatDateTime',script)(calls,files.choose||(async()=>null),files.upload||(async()=>({})),text=>messages.push(text),normalizeError,()=>generation,formatDateTime)
  const vm={...component.data()};for(const[name,fn]of Object.entries(component.methods))vm[name]=fn.bind(vm)
  for(const[name,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,name,{get:fn.bind(vm)})
  return {vm,component,messages,switchAccount:()=>generation++}
}

test('反馈选择器返回前切账号或离页不发上传，迟到上传不混入新表单',async()=>{
  for(const stop of ['account','hide']){
    const selected=deferred();let uploads=0
    const p=page({}, {choose:()=>selected.promise,upload:async()=>uploads++});await p.vm.load();const run=p.vm.addImage()
    if(stop==='account')p.switchAccount();else p.component.onHide.call(p.vm)
    selected.resolve({name:'合成.png',size:10,type:'image/png'});await run;assert.equal(uploads,0)
  }
  const pending=deferred(),p=page({}, {choose:async()=>({name:'合成.png',size:10}),upload:()=>pending.promise})
  await p.vm.load();const run=p.vm.addImage();await Promise.resolve();p.switchAccount();p.vm.form={title:'新身份',content:'保留新输入',images:[]}
  pending.resolve({fileId:'old-image'});await run;assert.equal(p.vm.form.title,'新身份');assert.deepEqual(p.vm.form.images,[])
})

test('反馈迟到读取和提交不能覆盖当前身份或清除新稿',async()=>{
  const read=deferred(),p=page({getInternshipFeedback:()=>read.promise});const loading=p.vm.load();await Promise.resolve();await Promise.resolve();p.switchAccount();p.vm.records=[{id:'new'}]
  read.resolve({items:[{id:'old'}]});await loading;assert.equal(p.vm.records[0].id,'new')
  const write=deferred(),q=page({submitInternshipFeedback:()=>write.promise});await q.vm.load();q.vm.form={title:'原反馈',content:'原反馈正文内容',images:[]};const sending=q.vm.submit()
  q.switchAccount();q.vm.form={title:'新反馈',content:'新账号输入保留',images:[]};write.resolve({id:'old',status:'RECEIVED'});await sending
  assert.equal(q.vm.form.title,'新反馈');assert.equal(q.messages.length,0)
})

test('反馈正常提交保留真实回执并读回原编号，回读失败不要求再次提交',async()=>{
  let fail=false;const writes=[],row={id:'8',status:'RECEIVED',version:0}
  const p=page({submitInternshipFeedback:async body=>{writes.push(body);fail=true;return row},getInternshipFeedback:async()=>{if(fail)throw Error('offline');return {items:[]}}})
  await p.vm.load();p.vm.form={title:'原反馈',content:'希望完善实际实习指导',images:[{fileId:'9'}]};await p.vm.submit()
  assert.equal(writes.length,1);assert.equal(writes[0].batchId,'3');assert.equal(p.vm.receipt.id,'8');assert.match(p.vm.errorMessage,/已提交|已登记/)
  assert.match(p.vm.errorMessage,/无需重复提交/);assert.equal(p.vm.submitting,false)
})

test('反馈失败保留输入并使用安全中文，历史或无记录不提交',async()=>{
  const p=page({submitInternshipFeedback:async()=>{throw Error('SQL secret C:/private')}});await p.vm.load();p.vm.form={title:'测试反馈',content:'原输入保留说明',images:[]};await p.vm.submit()
  assert.equal(p.vm.form.content,'原输入保留说明');assert.doesNotMatch(p.vm.errorMessage,/SQL|secret|private/)
  let writes=0;for(const dashboard of [{},{batchId:'3',recordId:'5',historyMode:true}]){
    const q=page({getInternship:async()=>dashboard,submitInternshipFeedback:async()=>writes++});await q.vm.load();q.vm.form={title:'测试反馈',content:'原输入保留说明',images:[]};await q.vm.submit()
  }assert.equal(writes,0)
})

test('反馈撤回携带原版本，旧回执不能改变切批次后的状态',async()=>{
  const pending=deferred(),calls=[],p=page({withdrawInternshipFeedback:async(id,body)=>{calls.push({id,body});return pending.promise}})
  await p.vm.load();const row={id:'7',version:2,status:'RECEIVED'};p.vm.records=[row];const run=p.vm.withdraw(row);p.vm.context={batchId:'new',internshipId:'new'}
  pending.resolve({id:'7',version:3,status:'WITHDRAWN'});await run
  assert.equal(calls[0].body.expectedVersion,2);assert.equal(calls[0].body.batchId,'3');assert.equal(p.vm.receipt,null)
})

test('反馈图片与提交共用明确上下文，成功后回读原编号及中文状态',async()=>{
  let saved=false;const row={id:'8',status:'RECEIVED',feedbackLevel:'DEPARTMENT',version:0},writes=[]
  const p=page({submitInternshipFeedback:async body=>{writes.push(body);saved=true;return row},getInternshipFeedback:async()=>({items:saved?[row]:[]})},
    {choose:async()=>({name:'合成.png',type:'image/png',size:10}),upload:async()=>({fileId:'9',fileName:'合成.png'})})
  await p.vm.load();p.vm.form.title='实习指导建议';p.vm.form.content='建议增加实际现场指导';p.vm.levelIndex=1;await p.vm.addImage();await p.vm.submit()
  assert.equal(writes[0].feedbackLevel,'DEPARTMENT');assert.deepEqual(writes[0].imageFileIds,['9']);assert.equal(p.vm.records[0].id,'8');assert.equal(p.vm.receipt.id,'8')
  assert.equal(p.vm.form.content,'');assert.equal(p.vm.statusLabel('INTERNAL_UNKNOWN'),'状态待确认');assert.equal(p.vm.levelLabel('UNKNOWN'),'反馈级别待确认')
})
