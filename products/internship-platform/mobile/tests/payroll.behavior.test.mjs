import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {normalizeFileReadiness,refreshFileReadiness} from '../src/services/fileReadiness.mjs'

function page(role,overrides={}) {
  let generation=1,modal
  const calls=[],context={selectedBatchId:'2746',batches:[{id:'2746',name:'批次'}],restore(){},async load(){},can:()=>true}
  const source=fs.readFileSync(new URL(`../src/pages/${role==='student'?'student-internship/process-facts':'teacher-internship/payroll-review'}/index.vue`,import.meta.url),'utf8')
  const deps={studentApi:{getInternship:async()=>({hasBatch:true,batchId:'2746',recordId:'822'})},
    studentInternshipRotations:async()=>[],studentInternshipPayroll:async()=>[],studentInternshipRotationSelfEvaluation(){},
    studentInternshipPayrollSubmit:async body=>calls.push(body),teacherInternshipPayroll:async()=>({items:[],hasMore:false}),
    teacherInternshipPayrollReview:async(...args)=>calls.push(args),useInternshipContextStore:()=>context,
    currentSessionGeneration:()=>generation,normalizeFileReadiness,refreshFileReadiness,fileSdk:{metadata:async id=>({fileId:id,status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true})},
    uploadBusinessFile:async()=>({fileId:'1',status:'QUARANTINED',scanStatus:'PENDING',readyForBusiness:false}),openBusinessFile(){},go(){},toast(){},
    normalizeError:e=>({pageState:e.httpStatus===403?'forbidden':'error',text:'读取失败'}),uni:{showModal:v=>{modal=v},chooseImage:v=>{modal=v}},...overrides}
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...component.data()}
  for(const[key,fn]of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const[key,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  return {vm,component,calls,context,modal:()=>modal,setGeneration:v=>generation=v}
}

test('学生凭证待扫描禁止提交，刷新通过后按打开版本提交零金额',async()=>{
  const p=page('student');await p.vm.load();p.vm.openPayroll({id:'7',version:4,payMonth:'2026-10',current:{actualAmount:0}})
  p.vm.payrollForm.correctionReason='实际尚未收到工资';p.vm.pickPayrollPhoto();await p.modal().success({tempFilePaths:['photo'],tempFiles:[{name:'凭证.png',size:10}]})
  await p.vm.submitPayroll();assert.equal(p.calls.length,0)
  await p.vm.refreshPayrollEvidence();await p.vm.submitPayroll();assert.equal(p.calls.length,1)
  assert.equal(p.calls[0].actualAmount,'0');assert.equal(p.calls[0].expectedVersion,4);assert.equal(p.calls[0].evidenceFileId,'1')
})

test('工资币种选择保持原币种代码、零金额和凭证，不在切换时提交',async()=>{
  const p=page('student');await p.vm.load();p.vm.openPayroll()
  p.vm.payrollForm.actualAmount='0';p.vm.payrollForm.evidenceFileId='8'
  p.vm.chooseCurrency({detail:{value:1}});assert.equal(p.vm.payrollForm.currency,'USD')
  p.vm.chooseCurrency({detail:{value:0}});assert.equal(p.vm.payrollForm.currency,'CNY')
  p.vm.chooseCurrency({detail:{value:2}});assert.equal(p.vm.payrollForm.currency,'');p.vm.payrollForm.currency='EUR';p.vm.chooseCurrency({detail:{value:2}});assert.equal(p.vm.payrollForm.currency,'EUR')
  assert.equal(p.vm.payrollForm.actualAmount,'0');assert.equal(p.vm.payrollForm.evidenceFileId,'8');assert.equal(p.calls.length,0)
})
test('工资版本冲突保留金额、凭证和旧版本，禁止自动覆盖重试',async()=>{
  const p=page('student',{studentInternshipPayrollSubmit:async()=>{throw {bizCode:'DATA_CONFLICT'}}});await p.vm.load();p.vm.openPayroll({id:'7',version:4,payMonth:'2026-10',current:{actualAmount:0}})
  Object.assign(p.vm.payrollForm,{correctionReason:'实际尚未收到工资',evidenceFileId:'8',evidence:{readyForBusiness:true}})
  await p.vm.submitPayroll();assert.equal(p.vm.payrollForm.conflict,true);assert.equal(p.vm.payrollForm.actualAmount,'0');assert.equal(p.vm.payrollForm.expectedVersion,4);assert.equal(p.vm.payrollForm.evidenceFileId,'8')
})

test('工资冲突关闭重开后保留草稿，读取新版并明确核对后才可继续',async()=>{
  const latest={id:'7',version:5,payMonth:'2026-10',current:{actualAmount:3200,currency:'CNY',status:'RETURNED'}}
  const p=page('student',{studentInternshipPayroll:async()=>[latest],studentInternshipPayrollSubmit:async()=>{throw {bizCode:'DATA_CONFLICT'}}})
  await p.vm.load();p.vm.openPayroll({...latest,version:4})
  Object.assign(p.vm.payrollForm,{actualAmount:'3300',correctionReason:'补充核对到账金额',evidenceFileId:'88',evidence:{readyForBusiness:true}})
  await p.vm.submitPayroll();p.vm.closePayroll();await p.vm.load();p.vm.openPayroll(latest)
  assert.equal(p.vm.payrollForm.actualAmount,'3300');assert.equal(p.vm.payrollForm.evidenceFileId,'88');assert.equal(p.vm.payrollForm.correctionReason,'补充核对到账金额')
  assert.equal(p.vm.payrollForm.expectedVersion,4);assert.equal(p.vm.payrollForm.conflict,true)
  await p.vm.refreshPayrollConflict();assert.equal(p.vm.payrollForm.expectedVersion,4);assert.equal(p.vm.payrollForm.latest.version,5)
  p.vm.confirmPayrollLatest();assert.equal(p.vm.payrollForm.expectedVersion,5);assert.equal(p.vm.payrollForm.conflict,false);assert.equal(p.calls.length,0)
})

test('首次新增与另一窗口同月冲突时按月份找到原单，核对前不自动改版本',async()=>{
  const p=page('student',{studentInternshipPayroll:async()=>[{id:'9',version:0,payMonth:'2026-10',current:{actualAmount:1000,status:'RETURNED'}}],studentInternshipPayrollSubmit:async()=>{throw {bizCode:'DATA_CONFLICT'}}})
  await p.vm.load();p.vm.openPayroll()
  Object.assign(p.vm.payrollForm,{payMonth:'2026-10',actualAmount:'1200',evidenceFileId:'88',evidence:{readyForBusiness:true},correctionReason:'合成核对保留原始填写'})
  await p.vm.submitPayroll();assert.equal(p.vm.payrollForm.statementId,'');assert.equal(p.vm.payrollForm.conflict,true)
  await p.vm.refreshPayrollConflict();assert.equal(p.vm.payrollForm.latest.id,'9');assert.equal(p.vm.payrollForm.statementId,'')
  p.vm.confirmPayrollLatest();assert.equal(p.vm.payrollForm.statementId,'9');assert.equal(p.vm.payrollForm.expectedVersion,0)
  assert.equal(p.vm.payrollForm.actualAmount,'1200');assert.equal(p.vm.payrollForm.evidenceFileId,'88')
})
test('选择凭证期间离页再进入，旧选择不上传',async()=>{
  let uploads=0;const p=page('student',{uploadBusinessFile:async()=>{uploads++}});await p.vm.load();p.vm.openPayroll();p.vm.pickPayrollPhoto();const callback=p.modal();p.component.onHide.call(p.vm);p.component.onShow.call(p.vm)
  await callback.success({tempFilePaths:['old-photo']});assert.equal(uploads,0)
})
test('教师切身份后迟到名单不回填，失败不冒充空名单',async()=>{
  let resolve;const p=page('teacher',{teacherInternshipPayroll:()=>new Promise(r=>resolve=r)});const pending=p.vm.load();await new Promise(r=>setImmediate(r));p.setGeneration(2);resolve({items:[{id:'old'}]});await pending;assert.equal(p.vm.list,null)
  const failed=page('teacher',{teacherInternshipPayroll:async()=>{throw {httpStatus:403}}});await failed.vm.load();assert.equal(failed.vm.state,'forbidden');assert.equal(failed.vm.list,null)
})
test('教师审核确认框打开后离页或失权，不发送审核',async()=>{
  for(const change of ['leave','role']){const p=page('teacher');await p.vm.load();p.vm.review({current:{id:'1',status:'SUBMITTED',version:0}},'APPROVE');if(change==='leave')p.component.onHide.call(p.vm);else p.context.can=()=>false;await p.modal().success({confirm:true,content:'核对通过'});assert.equal(p.calls.length,0)}
})
test('教师正常退回带原版本；短原因不发请求；审核后重新读取队列',async()=>{
  const p=page('teacher');await p.vm.load();p.vm.review({current:{id:'1',status:'SUBMITTED',version:2}},'RETURN');await p.modal().success({confirm:true,content:'太短'});assert.equal(p.calls.length,0)
  await p.modal().success({confirm:true,content:'请重新填写实际金额'});assert.deepEqual(p.calls,[['1',{action:'RETURN',comment:'请重新填写实际金额',expectedVersion:2}]]);assert.equal(p.vm.actingId,'');assert.equal(p.vm.state,'ready')
})
