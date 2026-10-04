import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { employmentView, employmentStatuses } from '../src/modules/internship/services/employmentPresentation.mjs'

const batch='9007199254740993001',record='9007199254740993002',id='9007199254740993003'
const row=(version=1,status='SUBMITTED',visible=true)=>({id,batchId:batch,internshipId:record,version,status,revisionCount:1,sensitiveVisible:visible,
  fieldLabels:{studentName:'姓名',salary:'月薪（元）',majorMatch:'专业是否对口'},current:{id:'9007199254740993004',registrationMode:'EMPLOYMENT',fields:{studentName:'合成学生',salary:'0',majorMatch:false},sources:{},attachments:[]},history:[]})
const ok=data=>({code:0,data})
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function page(overrides={},sdk={}){
  const source=fs.readFileSync(new URL('../src/modules/internship/views/InternshipEmploymentView.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  let generation=0,replaced
  const store={selectedBatchId:batch},api={getEmploymentRegistration:async()=>ok(row()),listEmploymentRegistrations:async()=>ok({items:[row()],total:1,hasMore:false}),...overrides}
  const scope={internshipApi:api,useInternshipBatchStore:()=>store,canCode:()=>true,currentSessionGeneration:()=>generation,
    normalizeUiError:()=>({userMessage:'操作未完成'}),formatDateTime:x=>x,fileSdk:{metadata:async fileId=>({fileId,sha256:'stable'}),blob:async()=>new Uint8Array(),...sdk},
    employmentView,employmentStatuses,ModulePageShell:{},LoadingState:{},ErrorState:{},AppButton:{},AppSelect:{},AppFilePreview:{},FilePreviewer:{}}
  const component=new Function(...Object.keys(scope),script)(...Object.values(scope))
  const vm={...component.data(),ctx:{ctxKey:'test-context'},$route:{query:{batchId:batch,internshipId:record}},$router:{replace:async value=>{replaced=value}}}
  for(const [name,method] of Object.entries(component.methods))vm[name]=(...args)=>method.apply(vm,args)
  for(const [name,getter] of Object.entries(component.computed))Object.defineProperty(vm,name,{get:()=>getter.call(vm)})
  return {vm,component,api,store,switchAccount:()=>generation++,route:()=>replaced}
}

test('PC presentation preserves false, zero and large IDs with Chinese fallback labels',()=>{
  const result=employmentView({...row(),status:'UNKNOWN'})
  assert.equal(result.id,id);assert.equal(result.statusLabel,'状态待确认');assert.equal(result.current.fieldRows[1].value,'0');assert.equal(result.current.fieldRows[2].value,'否')
})
test('a registration from a different selected batch cannot populate the workspace',async()=>{
  const p=page({getEmploymentRegistration:async()=>ok({...row(),batchId:'other'})});await p.vm.select(id);assert.equal(p.vm.detail,null);assert.ok(p.vm.detailError)
})
test('old-account disclosures and reads cannot restore complete personal material',async()=>{
  const wait=deferred(),p=page({discloseEmploymentRegistration:()=>wait.promise});p.vm.detail=employmentView(row(1,'SUBMITTED',false));p.vm.selectedId=id;p.vm.purpose='核对本次就业材料'
  const call=p.vm.disclose();p.switchAccount();p.vm.reset();wait.resolve(ok(row()));await call;assert.equal(p.vm.detail,null);assert.equal(p.vm.processing,false);assert.equal(p.vm.previewFile,null)
})
test('failed review retains the exact submission, expected version and correction comment',async()=>{
  let payload;const p=page({reviewEmploymentRegistration:async(i,body)=>{payload={i,...body};throw Error('network')}});p.vm.detail=employmentView(row());p.vm.selectedId=id;p.vm.comment='请补充就业岗位职责'
  await p.vm.review('RETURN');assert.equal(payload.i,id);assert.equal(payload.submissionId,p.vm.detail.current.id);assert.equal(payload.expectedVersion,1);assert.equal(p.vm.comment,'请补充就业岗位职责');assert.equal(p.vm.receipt,null);assert.ok(p.vm.detailError)
})
test('conflict rereads the latest masked material and retains the teacher comment',async()=>{
  const p=page({reviewEmploymentRegistration:async()=>{throw {code:409001}},getEmploymentRegistration:async()=>ok(row(2,'SUBMITTED',false))});p.vm.detail=employmentView(row());p.vm.selectedId=id;p.vm.comment='请核对本次就业材料'
  await p.vm.review('RETURN');assert.equal(p.vm.detail.version,2);assert.equal(p.vm.detail.sensitiveVisible,false);assert.equal(p.vm.comment,'请核对本次就业材料');assert.ok(p.vm.detailError.includes('重新核对'))
})
test('photo access requires disclosed material and compares its immutable content hash',async()=>{
  let calls=0;const p=page({}, {metadata:async fileId=>{calls++;return {fileId,sha256:'changed'}}});p.vm.detail=employmentView(row(1,'SUBMITTED',false));p.vm.selectedId=id
  await p.vm.preview({fileId:'9007199254740993020',sha256:'stable'});assert.equal(calls,0)
  p.vm.detail.sensitiveVisible=true;await p.vm.preview({fileId:'9007199254740993020',sha256:'stable'});assert.equal(calls,1);assert.equal(p.vm.previewFile,null);assert.ok(p.vm.fileError)
})
test('a late photo response cannot replace the newly selected preview',async()=>{
  const wait=deferred(),p=page({}, {metadata:fileId=>fileId==='a'?wait.promise:Promise.resolve({fileId,sha256:'stable'})});p.vm.detail=employmentView(row());p.vm.selectedId=id
  const old=p.vm.preview({fileId:'a',sha256:'stable'});await p.vm.preview({fileId:'b',sha256:'stable'});wait.resolve({fileId:'a',sha256:'stable'});await old;assert.equal(p.vm.previewFile.fileId,'b');assert.equal(p.vm.fileLoading,false)
})
test('workspace disposal fences a late photo response and removes private data',async()=>{
  const wait=deferred(),p=page({}, {metadata:()=>wait.promise});p.vm.detail=employmentView(row());p.vm.selectedId=id;const call=p.vm.preview({fileId:'a',sha256:'stable'})
  p.component.beforeUnmount.call(p.vm);wait.resolve({fileId:'a',sha256:'stable'});await call;assert.equal(p.vm.previewFile,null);assert.equal(p.vm.detail,null);assert.equal(p.vm.fileLoading,false)
})
test('filter navigation preserves the placement and batch while resetting page and selected object',()=>{
  const p=page();p.vm.status='ALL';p.vm.changeFilter();assert.deepEqual(p.route().query,{batchId:batch,internshipId:record,status:'ALL',page:'1',registrationId:undefined})
})
