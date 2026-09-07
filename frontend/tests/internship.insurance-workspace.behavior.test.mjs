import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { ref, computed, reactive } from 'vue'
import { normalizeUiError } from '../src/utils/presentationSafety.js'
const source = parse(fs.readFileSync(new URL('../src/modules/internship/views/InsuranceVerifyView.vue', import.meta.url), 'utf8')).descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
const record = { id:'9007199254740995', studentName:'测试学生', version:3, fileId:'8', status:'PENDING_VERIFY' }
const deferred = () => { let resolve; const promise = new Promise(r => { resolve=r }); return {resolve,promise} }
function view(api={}, permission=true) {
  const route=reactive({params:{insuranceId:record.id},query:{batchId:'1',page:'3',status:'ALL',keyword:'测试'}}), calls=[]
  const props={ctx:{permissionPatterns:permission?['internship.insurance.verify']:[]}}
  const result=new Function('computed','ref','watch','onBeforeUnmount','useRoute','useRouter','defineProps','insuranceApi','canCode','normalizeUiError','fileSdk', `${source}\nreturn {load,detail,rows,error,action,actionError,conflict,receipt,reasonInput,canHandle,askAction,submitAction,navigate,filter,nextPending,canContinue,openOnboard,file,fileBusy,fileError,approveBlockReason}`)(computed,ref,()=>{},()=>{},()=>route,()=>({push:async r=>calls.push(r)}),()=>props,api,(ctx,code)=>ctx.permissionPatterns.includes(code),normalizeUiError,{metadata:async()=>({fileId:'8',readyForBusiness:true,canPreview:true})})
  result.detail.value={...record}
  result.file.value={fileId:'8',readyForBusiness:true,canPreview:true}
  return {p:result,route,calls,props}
}

test('verified insurance continues with its actual student record and preserves the exact policy return link', async () => {
  const {p,route,calls,props}=view()
  props.ctx.permissionPatterns.push('internship.student.view')
  route.fullPath='/admin/internship/insurance/9007199254740995?batchId=1&page=3&status=ALL&keyword=测试'
  p.detail.value={...record,status:'VERIFIED',internshipId:'9007199254740999'}
  await p.openOnboard()
  assert.deepEqual(calls[0],{path:'/admin/internship/students/9007199254740999',query:{batchId:'1',section:'placement',returnTo:route.fullPath}})
})

test('insurance continuation respects dossier permission and verified status', async () => {
  const {p,calls,props}=view()
  p.detail.value={...record,status:'VERIFIED',internshipId:'31'}
  await p.openOnboard();assert.equal(calls.length,0)
  props.ctx.permissionPatterns.push('internship.student.view');p.detail.value.status='REJECTED'
  await p.openOnboard();assert.equal(calls.length,0)
  p.detail.value.status='VERIFIED';p.detail.value.internshipId=''
  await p.openOnboard();assert.equal(calls.length,0)
})
test('detail returns to same batch, queue filters and page',async()=>{
  const {p,calls}=view();await p.navigate();assert.deepEqual(calls[0],{path:'/admin/internship/insurance',query:{batchId:'1',page:'3',status:'ALL',keyword:'测试'}})
})
test('confirmation carries reviewed version once and reads server result again',async()=>{
  const work=deferred(), writes=[];let reads=0
  const {p}=view({verify:async(...args)=>{writes.push(args);return work.promise},getDetail:async()=>{reads++;return {code:0,data:{...record,version:4,status:'VERIFIED'}}}})
  p.askAction('APPROVE');const pending=p.submitAction();await p.submitAction();assert.equal(writes.length,1)
  assert.deepEqual(writes[0],[record.id,{action:'APPROVE',comment:'',expectedVersion:3}])
  work.resolve({code:0,data:{...record,status:'VERIFIED'}});await pending
  assert.equal(reads,1);assert.equal(p.detail.value.version,4);assert.equal(p.canHandle.value,false)
})
test('conflict blocks retry and keeps correction text through refresh',async()=>{
  let writes=0
  const {p}=view({verify:async()=>{writes++;return {code:409001,message:'记录已发生变化'}},getDetail:async()=>({code:0,data:{...record,version:4}})})
  p.reasonInput.value='请补充完整保障期限';p.askAction('REJECT');await p.submitAction();await p.submitAction()
  assert.equal(writes,1);assert.equal(p.conflict.value,true);assert.equal(p.reasonInput.value,'请补充完整保障期限')
  await p.load();assert.equal(p.reasonInput.value,'请补充完整保障期限');p.askAction('REJECT');assert.equal(p.action.value.version,4)
})
test('read-only and absent credentials cannot open approval',()=>{
  const {p}=view({},false);p.askAction('APPROVE');assert.equal(p.action.value,null)
  const writable=view().p;writable.detail.value.fileId='';writable.askAction('APPROVE');assert.equal(writable.action.value,null)
})

test('unreadable, unsafe or mismatched evidence blocks approval but permits correction',()=>{
  for (const file of [null, {fileId:'8',readyForBusiness:false,canPreview:true}, {fileId:'9',readyForBusiness:true,canPreview:true}, {fileId:'8',readyForBusiness:true}]) {
    const {p}=view();p.file.value=file;p.askAction('APPROVE');assert.equal(p.action.value,null)
    p.askAction('REJECT');assert.equal(p.action.value.kind,'REJECT')
  }
})

test('approval rechecks evidence after opening confirmation',async()=>{
  const {p}=view({verify:async()=>assert.fail('must not approve unreadable evidence')})
  p.askAction('APPROVE');p.fileError.value='预览失败';await p.submitAction()
  assert.match(p.actionError.value,/读取失败/)
  p.fileError.value='';p.fileBusy.value=true;await p.submitAction();assert.match(p.actionError.value,/正在读取/)
})
test('late detail does not display records from previous batch',async()=>{
  const a=deferred(),b=deferred();const {p,route}=view({getDetail:(_,batch)=>batch==='1'?a.promise:b.promise})
  const first=p.load();route.query.batchId='2';const second=p.load();assert.equal(p.detail.value,null)
  b.resolve({code:0,data:{...record,studentName:'当前批次'}});await second;a.resolve({code:0,data:record});await first
  assert.equal(p.detail.value.studentName,'当前批次')
})
test('failed reads are explicit and clear stale facts',async()=>{
  const {p}=view({getDetail:async()=>({code:503001,message:'SQL failed'})});await p.load();assert.equal(p.detail.value,null);assert.match(p.error.value,/系统暂时/)
})
test('late successful write never replaces a new context',async()=>{
  const work=deferred();const {p,route}=view({verify:()=>work.promise,getDetail:async()=>({code:0,data:{...record,studentName:'新批次'}})})
  p.askAction('APPROVE');const pending=p.submitAction();route.query.batchId='2';await p.load();work.resolve({code:0,data:record});await pending
  assert.equal(p.detail.value.studentName,'新批次');assert.equal(p.receipt.value,'')
})
test('API adapter preserves expectedVersion without converting large identifiers',async()=>{
  const text=fs.readFileSync(new URL('../src/modules/internship/api/plan-insurance.api.js',import.meta.url),'utf8').replace(/^import .*$/gm,'').replace(/export const /g,'const ')
  const calls=[];const api=new Function('request',`${text}\nreturn insuranceApi`)(async(...args)=>{calls.push(args);return {}})
  await api.verify(record.id,{action:'APPROVE',comment:'已核对',expectedVersion:3})
  assert.equal(calls[0][0],`/internship/insurances/${record.id}/verify`);assert.equal(calls[0][1].body.expectedVersion,3)
  await api.getDetail(record.id,'9007199254740999');assert.equal(calls[1][1].params.batchId,'9007199254740999')
})

test('cancelled return comments never become approval comments',async()=>{
 const calls=[];const {p}=view({verify:async(...args)=>{calls.push(args);return {code:0,data:record}},getDetail:async()=>({code:0,data:{...record,status:'VERIFIED'}})})
 p.askAction('REJECT');p.reasonInput.value='这条意见原本用于退回';p.action.value=null;p.askAction('APPROVE');await p.submitAction()
 assert.equal(calls[0][1].comment,'');assert.equal(p.reasonInput.value,'')
})
test('next policy respects queue keyword and reports completion without losing receipt',async()=>{
 const calls=[];const {p}=view({getInsurances:async params=>{calls.push(params);return {code:0,data:{list:[]}}}})
 p.detail.value.status='VERIFIED';await p.nextPending();assert.equal(calls[0].keyword,'测试');assert.match(p.receipt.value,/已无待核验/)
})
