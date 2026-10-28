import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { normalizeError } from './request-module.mjs'
import { normalizeFileReadiness, refreshFileReadiness } from '../src/services/fileReadiness.mjs'
import { formatDateTime } from '../src/utils/format.js'
const source=fs.readFileSync(new URL('../src/pages/student-internship/makeup/index.vue',import.meta.url),'utf8')
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve}}
function page(api={},files={}){
  let generation=0;const messages=[],modals=[]
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm,'').replace('export default','return')
  const deps={studentApi:{getInternship:api.context||(async()=>({batchId:'3',recordId:'5'}))},studentInternshipMakeups:api.list||(async()=>({items:[]})),studentInternshipMakeupApply:api.apply||(async()=>({})),studentInternshipMakeupWithdraw:api.withdraw||(async()=>({})),normalizeError,normalizeFileReadiness,refreshFileReadiness,formatDateTime,currentSessionGeneration:()=>generation,chooseSingleFile:files.choose||(async()=>null),uploadBusinessFile:files.upload||(async()=>({})),fileSdk:{metadata:files.meta||(async()=>({}))},toast:text=>messages.push(text),uni:{showModal:options=>modals.push(options)}}
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...component.data()}
  for(const[name,fn]of Object.entries(component.methods))vm[name]=fn.bind(vm)
  for(const[name,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,name,{get:fn.bind(vm)})
  return {vm,component,messages,modals,switchAccount:()=>generation++}
}
const pendingFile={fileId:'9',fileName:'补卡证明.pdf',status:'QUARANTINED',scanStatus:'PENDING',readyForBusiness:false}
const readyFile={...pendingFile,status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true}
function fill(vm){vm.openApply();vm.form.checkinDate='2026-10-12';vm.form.reason='真实补卡原因说明';vm.form.makeupType='OUT_OF_RANGE'}

test('补卡待扫描不能提交，刷新失败保留证明和草稿，安全后才携原文件申请',async()=>{
  let fail=true;const writes=[],row={id:'8',version:0,status:'PENDING'}
  const p=page({apply:async body=>{writes.push(body);return row},list:async()=>({items:writes.length?[row]:[]})},{choose:async()=>({name:'补卡证明.pdf'}),upload:async()=>pendingFile,meta:async()=>{if(fail)throw Error('offline');return readyFile}})
  await p.vm.loadList();fill(p.vm);await p.vm.chooseEvidence();await p.vm.submit();assert.equal(writes.length,0)
  assert.equal(p.vm.pendingEvidence.statusText,'等待安全扫描');await p.vm.refreshEvidence();assert.equal(p.vm.form.reason,'真实补卡原因说明');assert.equal(p.vm.pendingEvidence.fileId,'9')
  fail=false;await p.vm.refreshEvidence();await p.vm.submit();assert.equal(writes.length,1);assert.equal(writes[0].evidenceFileId,'9');assert.equal(p.vm.receipt.id,'8');assert.equal(p.vm.list[0].id,'8')
})

test('补卡正常选择器临时隐藏保留草稿，回到同一页面才上传',async()=>{
  const chosen=deferred();let uploads=0
  const p=page({}, {choose:()=>chosen.promise,upload:async()=>{uploads++;return readyFile}})
  await p.vm.loadList();fill(p.vm);const run=p.vm.chooseEvidence();p.component.onHide.call(p.vm);chosen.resolve({name:'补卡.pdf'});await Promise.resolve();await Promise.resolve()
  assert.equal(uploads,0);p.component.onShow.call(p.vm);await run
  assert.equal(uploads,1);assert.equal(p.vm.form.reason,'真实补卡原因说明');assert.equal(p.vm.form.evidenceFileId,'9')
})

test('补卡选择器旧账号或已卸载页面不能上传，旧上传不能回填新表单',async()=>{
  for(const stop of ['account','unload']){
    const chosen=deferred();let uploads=0;const p=page({}, {choose:()=>chosen.promise,upload:async()=>uploads++})
    await p.vm.loadList();fill(p.vm);const run=p.vm.chooseEvidence();if(stop==='account')p.switchAccount();else p.component.onUnload.call(p.vm)
    chosen.resolve({name:'补卡.pdf'});await run;assert.equal(uploads,0)
  }
  const uploaded=deferred(),p=page({}, {choose:async()=>({name:'补卡.pdf'}),upload:()=>uploaded.promise})
  await p.vm.loadList();fill(p.vm);const run=p.vm.chooseEvidence();await Promise.resolve();p.switchAccount();p.vm.form.reason='新身份草稿'
  uploaded.resolve(readyFile);await run;assert.equal(p.vm.form.reason,'新身份草稿');assert.equal(p.vm.form.evidenceFileId,'')
})

test('补卡撤回确认冻结原单版本，切换上下文后的旧确认不得提交',async()=>{
  const writes=[],p=page({withdraw:async(...args)=>{writes.push(args);return {id:'8',version:3,status:'WITHDRAWN'}}})
  await p.vm.loadList();const row={id:'8',version:2,status:'PENDING'};p.vm.withdraw(row);p.switchAccount();await p.modals[0].success({confirm:true});assert.equal(writes.length,0)
  const q=page({withdraw:async(...args)=>{writes.push(args);return {id:'8',version:3,status:'WITHDRAWN'}},list:async()=>({items:[{id:'8',status:'WITHDRAWN'}]})});await q.vm.loadList();q.vm.withdraw(row);await q.modals[0].success({confirm:true})
  assert.equal(writes[0][0],'8');assert.deepEqual(writes[0][1],{batchId:'3',internshipId:'5',expectedVersion:2})
})

test('补卡失败不丢输入，取消重开仍是原草稿，历史或无批次不写入',async()=>{
  const p=page({apply:async()=>{throw Error('SQL secret')}});await p.vm.loadList();fill(p.vm);p.vm.form.makeupType='MISSING';await p.vm.submit()
  assert.equal(p.vm.form.reason,'真实补卡原因说明');assert.doesNotMatch(p.messages.join(' '),/SQL|secret/)
  p.vm.closeForm();p.vm.openApply();assert.equal(p.vm.form.reason,'真实补卡原因说明')
  let writes=0;for(const context of [{},{batchId:'3',recordId:'5',historyMode:true}]){
    const q=page({context:async()=>context,apply:async()=>writes++});await q.vm.loadList();q.vm.form.checkinDate='2026-10-12';q.vm.form.reason='错误上下文';await q.vm.submit()
  }assert.equal(writes,0)
})

test('补卡旧列表和旧提交回包不能回填切换后的页面',async()=>{
  const read=deferred(),p=page({list:()=>read.promise});const loading=p.vm.loadList();await Promise.resolve();p.switchAccount();p.vm.list=[{id:'new'}]
  read.resolve({items:[{id:'old'}]});await loading;assert.equal(p.vm.list[0].id,'new')
  const pending=deferred(),q=page({apply:()=>pending.promise});await q.vm.loadList();fill(q.vm);q.vm.form.makeupType='MISSING';const sending=q.vm.submit()
  q.component.onUnload.call(q.vm);q.vm.form.reason='新页面草稿';pending.resolve({id:'old',status:'PENDING',version:0});await sending
  assert.equal(q.vm.form.reason,'新页面草稿');assert.equal(q.vm.receipt,null)
})
