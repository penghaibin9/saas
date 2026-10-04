import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as presentation from '../src/services/employmentPresentation.mjs'
import { reportFileState, reportFilesReady, refreshReportFiles } from '../src/services/weeklyReportPresentation.mjs'

const batch='9007199254740993001',record='9007199254740993002',id='9007199254740993003'
const prefill={identity:{studentName:'合成学生',studentNo:'SYN-001',collegeName:'合成学院',majorName:'合成专业',grade:'2024',className:'合成班级',enrollmentYear:'2024',studentPhone:'13800000000'},identityEditable:{enrollmentYear:false},canTransfer:false,transferHint:'请核对企业关联'}
const declaration={...prefill.identity,employmentType:'签订劳动合同就业',companyName:'合成企业',creditCode:'91430100MA4L0ABC1D',companyAddress:'合成地址',companyScale:'小型',companyPhone:'073100000000',companyEmail:'synthetic@example.invalid',hrContact:'合成人事',companyNature:'民营',industry:'软件',jobCategory:'开发',positionName:'工程师',majorMatch:false,salary:'0',agreementNo:'SYN-001'}
const row=(version=1,status='SUBMITTED')=>({id,batchId:batch,internshipId:record,version,status,revisionCount:1,sensitiveVisible:true,current:{id:'9007199254740993004',revisionNo:1,registrationMode:'EMPLOYMENT',fields:{...declaration},sources:{},attachments:[]},history:[]})
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function page(overrides={},teacher=false,sdk={}){
  const source=fs.readFileSync(new URL(`../src/pages/${teacher?'teacher':'student'}-internship/employment/index.vue`,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  let generation=0
  const context={batches:[{id:batch,name:'合成批次'}],selectedBatchId:batch,can:()=>true,load:async()=>{},selectBatch(value){if(!this.batches.some(x=>x.id===value))return false;this.selectedBatchId=value;return true}}
  const api={getInternship:async()=>({hasBatch:true,batchId:batch,recordId:record,schoolMentor:'合成导师'}),getInternshipEmployment:async()=>({batchId:batch,internshipId:record,prefill,registration:null}),getEmploymentRegistrations:async()=>({items:[],total:0,hasMore:false}),getEmploymentRegistration:async()=>row(),...overrides}
  const defaults={metadata:async fileId=>({fileId,status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true}),...sdk}
  const scope={studentApi:api,teacherApi:api,fileSdk:defaults,ReportFilePreview:{},normalizeError:e=>({text:'操作未完成',kind:Number(e?.code)===409001?'conflict':'unknown',pageState:'error'}),
    currentSessionGeneration:()=>generation,...presentation,reportFileState,reportFilesReady,refreshReportFiles,formatDateTime:x=>x,
    useInternshipContextStore:()=>context,uni:{pageScrollTo(){}}}
  const component=new Function(...Object.keys(scope),script)(...Object.values(scope))
  const vm={...component.data(),$refs:{photos:{reset(){},open:async()=>{}}}}
  for(const [key,method] of Object.entries(component.methods))vm[key]=(...args)=>method.apply(vm,args)
  for(const [key,getter] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>getter.call(vm)})
  return {vm,component,api,context,switchAccount:()=>generation++}
}
async function ready(api={},sdk={}){const p=page(api,false,sdk);await p.vm.load();p.vm.form.fields={...declaration};p.vm.markDirty();return p}

test('visible result notifications stay unread until explicit acknowledgement and failed acknowledgement preserves the result',async()=>{
  const message={id:'9007199254740993020',title:'审核结果',content:'已退回补正',status:'UNREAD',statusLabel:'未读'}
  const p=await ready({getInternshipEmployment:async()=>({batchId:batch,internshipId:record,prefill,registration:row(2,'RETURNED'),resultNotifications:{items:[message],total:1,unread:1,page:1,hasMore:false}}),readInternshipEmploymentResult:async()=>{throw Error('network')}})
  assert.equal(p.vm.notifications.unread,1);await p.vm.readNotification(message);assert.equal(p.vm.notifications.items[0].status,'UNREAD');assert.ok(p.vm.notificationError);assert.equal(p.vm.form.fields.salary,'0')
  let submitted; p.api.readInternshipEmploymentResult=async(...args)=>{submitted=args;return {...message,status:'READ',statusLabel:'已读'}}
  await p.vm.readNotification(message);assert.deepEqual(submitted,[message.id,batch,record]);assert.equal(p.vm.notifications.unread,0);assert.equal(p.vm.notifications.items[0].statusLabel,'已读');assert.equal(p.vm.notificationError,'')
})
test('a hidden or old-account notification acknowledgement cannot repopulate private messages',async()=>{
  const message={id:'9007199254740993020',status:'UNREAD'},wait=deferred(),p=await ready({readInternshipEmploymentResult:()=>wait.promise})
  p.vm.notifications={items:[message],total:1,unread:1};const call=p.vm.readNotification(message);p.component.onHide.call(p.vm);p.switchAccount();p.vm.resetAccount();wait.resolve({...message,status:'READ'});await call
  assert.equal(p.vm.notifications.items.length,0);assert.equal(p.vm.readingNotification,'')
})
test('notification paging uses server pages and preserves the unsent employment correction',async()=>{
  let requested;const p=await ready({getInternshipEmployment:async(b,r,page)=>{requested=page;return {batchId:batch,internshipId:record,prefill,registration:null,resultNotifications:{items:[],total:25,unread:25,page,hasMore:page===1}}}})
  p.vm.form.fields.positionName='尚未提交岗位';await p.vm.changeNotificationPage(1);assert.equal(requested,2);assert.equal(p.vm.notificationPage,2);assert.equal(p.vm.form.fields.positionName,'尚未提交岗位');await p.vm.changeNotificationPage(1);assert.equal(requested,2)
})
test('teacher photo preview cannot bypass full-material disclosure',async()=>{
  const p=page({},true);let opened=0;p.vm.$refs.photos.open=async()=>{opened++};p.vm.state='ready';p.vm.detail=presentation.employmentView({...row(),sensitiveVisible:false})
  await p.vm.openPhoto({fileId:'1'});assert.equal(opened,0);p.vm.detail.sensitiveVisible=true;await p.vm.openPhoto({fileId:'1'});assert.equal(opened,1)
})
test('default application launch remains the registered login page',()=>{
  const pages=JSON.parse(fs.readFileSync(new URL('../src/pages.json',import.meta.url),'utf8'));assert.equal(pages.pages[0].path,'pages/login/index')
})

test('all 23 fields, zero salary and false match are collected without inventing values',()=>{
  assert.equal(presentation.employmentFields.length,23)
  const form={fields:{...declaration},mode:'EMPLOYMENT'}
  assert.equal(presentation.validateEmployment(form,prefill),null)
  for(const value of ['NaN','-1','0.001'])assert.equal(presentation.validateEmployment({...form,fields:{...form.fields,salary:value}},prefill).key,'salary')
  assert.equal(presentation.validateEmployment({...form,fields:{...form.fields,majorMatch:null}},prefill).key,'majorMatch')
})
test('explicit no choice preserves the false business value and cannot edit a pending declaration',async()=>{
  const p=await ready();p.vm.form.fields.majorMatch=null;p.vm.chooseMatch(false);assert.equal(p.vm.form.fields.majorMatch,false);assert.equal(p.vm.dirty,true)
  p.vm.registration=presentation.employmentView(row());p.vm.chooseMatch(true);assert.equal(p.vm.form.fields.majorMatch,false)
})
test('school identity remains authoritative while an older submitted snapshot stays unchanged',()=>{
  const old=row(),fresh={...prefill,identity:{...prefill.identity,studentName:'学校更正姓名'}}
  const draft=presentation.employmentDraft(fresh,old)
  assert.equal(draft.fields.studentName,'学校更正姓名');assert.equal(old.current.fields.studentName,'合成学生')
})
test('employment registration read failure preserves unsent text and retry uses server authority',async()=>{
  const p=await ready();p.api.getInternshipEmployment=async()=>{throw Error('network')};await p.vm.load()
  assert.equal(p.vm.state,'error');assert.equal(p.vm.form.fields.agreementNo,'SYN-001');assert.equal(p.vm.receipt,null)
  p.api.getInternshipEmployment=async()=>({batchId:batch,internshipId:record,prefill,registration:null});await p.vm.load();assert.equal(p.vm.state,'ready');assert.equal(p.vm.form.fields.agreementNo,'SYN-001')
})
test('a teacher decision reread clears the obsolete waiting-for-review submission receipt',async()=>{
  const p=await ready({getInternshipEmployment:async()=>({batchId:batch,internshipId:record,prefill,registration:row(2,'RETURNED')})})
  p.vm.receipt=presentation.employmentView(row());await p.vm.load();assert.equal(p.vm.receipt,null);assert.equal(p.vm.registration.statusLabel,'已退回补正')
})
test('a failed submit retains the whole draft and never creates a success receipt',async()=>{
  const p=await ready({submitInternshipEmployment:async()=>{throw Error('network')}});const before=JSON.stringify(p.vm.form)
  await p.vm.submit();assert.equal(JSON.stringify(p.vm.form),before);assert.equal(p.vm.receipt,null);assert.equal(p.vm.submitting,false)
})
test('pending photo cannot be submitted until the authoritative safety reread succeeds',async()=>{
  let calls=0;const p=await ready({submitInternshipEmployment:async()=>{calls++;return row()}},{metadata:async fileId=>({fileId,status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true})})
  p.vm.form.attachments=[reportFileState({fileId:'9007199254740993010',status:'AVAILABLE',scanStatus:'PENDING',readyForBusiness:false})]
  await p.vm.submit();assert.equal(calls,0);assert.equal(p.vm.form.fields.salary,'0');await p.vm.refreshPhotos();assert.equal(p.vm.canSubmit,true)
})
test('failed scan retains photo/text and a later retry can unblock submission',async()=>{
  const p=await ready({}, {metadata:async()=>{throw Error('scan failure')}});p.vm.form.attachments=[reportFileState({fileId:'1',scanStatus:'PENDING'})]
  await p.vm.refreshPhotos();assert.equal(p.vm.photosReady,false);assert.equal(p.vm.form.attachments.length,1);assert.equal(p.vm.form.fields.positionName,'工程师');assert.equal(p.vm.scanning,false)
})
test('exact large IDs, current version and file IDs are sent once, then a real receipt is reread',async()=>{
  let payload,calls=0;const response=row();const p=await ready({submitInternshipEmployment:async body=>{calls++;payload=body;return response},getInternshipEmployment:async()=>({batchId:batch,internshipId:record,prefill,registration:response})})
  p.vm.registration=null;p.vm.baseVersion=0;p.vm.form.correctionReason='';await p.vm.submit()
  assert.equal(payload.batchId,batch);assert.equal(payload.internshipId,record);assert.equal(payload.expectedVersion,0);assert.equal(payload.fields.majorMatch,false);assert.equal(calls,1);assert.equal(p.vm.receipt.id,id);assert.equal(p.vm.editable,false)
})
test('version conflict keeps edits and base version until explicit acknowledgement of the reread',async()=>{
  const returned=row(2,'RETURNED'),latest=row(3,'RETURNED');const p=await ready({getInternshipEmployment:async()=>({batchId:batch,internshipId:record,prefill,registration:returned}),submitInternshipEmployment:async()=>{p.api.getInternshipEmployment=async()=>({batchId:batch,internshipId:record,prefill,registration:latest});throw {code:409001}}})
  p.vm.form.fields.positionName='本次修改岗位';p.vm.form.correctionReason='已经补充就业材料';await p.vm.submit()
  assert.equal(p.vm.baseVersion,2);assert.equal(p.vm.registration.version,3);assert.equal(p.vm.form.fields.positionName,'本次修改岗位');assert.equal(p.vm.conflict,true);assert.equal(p.vm.canSubmit,false)
  p.vm.acceptLatestVersion();assert.equal(p.vm.baseVersion,3);assert.equal(p.vm.conflict,false)
})
test('only a canonical current internship company enables transfer and remains fixed',async()=>{
  const p=await ready();p.vm.chooseMode('INTERNSHIP_TRANSFER');assert.equal(p.vm.form.mode,'EMPLOYMENT')
  p.vm.prefill={...prefill,canTransfer:true,transfer:{companyName:'正式关联企业',creditCode:declaration.creditCode,positionName:'实习原岗位'}}
  p.vm.chooseMode('INTERNSHIP_TRANSFER');assert.equal(p.vm.form.fields.companyName,'正式关联企业');assert.equal(p.vm.fieldReadonly({key:'companyName'}),true)
  assert.equal(p.vm.form.fields.positionName,'实习原岗位');assert.equal(presentation.validateEmployment({...p.vm.form,fields:{...p.vm.form.fields,companyName:'伪造企业'}},p.vm.prefill).key,'companyName')
})
test('old-account read cannot populate the page and showing clears old private drafts',async()=>{
  const wait=deferred(),p=page({getInternshipEmployment:()=>wait.promise});const call=p.vm.load();await Promise.resolve();p.switchAccount();wait.resolve({batchId:batch,internshipId:record,prefill,registration:row()});await call
  assert.equal(p.vm.registration,null);p.vm.form.fields.companyEmail='old@example.invalid';p.component.onShow.call(p.vm);assert.equal(p.vm.form.fields.companyEmail,'');assert.equal(p.vm.receipt,null)
})
test('hide discards a late successful submit and reopening rereads its actual committed status',async()=>{
  const wait=deferred(),p=await ready({submitInternshipEmployment:()=>wait.promise});const call=p.vm.submit();p.component.onHide.call(p.vm);wait.resolve(row());await call
  assert.equal(p.vm.receipt,null);assert.equal(p.vm.submitting,false);p.api.getInternshipEmployment=async()=>({batchId:batch,internshipId:record,prefill,registration:row()});p.component.onShow.call(p.vm);await p.vm.load();assert.equal(p.vm.registration.status,'SUBMITTED');assert.equal(p.vm.editable,false)
})
test('an old context upload and scan cannot add files to the new draft',async()=>{
  const wait=deferred(),p=await ready({}, {choose:async()=>({path:'synthetic'}),upload:()=>wait.promise});const call=p.vm.addPhoto();await Promise.resolve();p.vm.contextKey='other:record';p.vm.epoch++;wait.resolve({fileId:'1',readyForBusiness:true});await call;assert.equal(p.vm.form.attachments.length,0)
})
test('teacher exact-object deep link selects only its allowed batch',async()=>{
  const p=page({},true);p.vm.requestedId=id;await p.vm.load();assert.equal(p.vm.selectedId,id);assert.equal(p.vm.detail.id,id)
  const denied=page({getEmploymentRegistration:async()=>({...row(),batchId:'foreign'})},true);denied.vm.requestedId=id;await denied.vm.load();assert.equal(denied.vm.state,'error');assert.equal(denied.vm.detail,null)
})
test('teacher hidden response cannot restore full personal information',async()=>{
  const wait=deferred(),p=page({getEmploymentRegistration:()=>wait.promise},true);p.vm.state='ready';const call=p.vm.select(id);p.component.onHide.call(p.vm);wait.resolve(row());await call;assert.equal(p.vm.detail,null);assert.equal(p.vm.detailLoading,false)
})
test('teacher failure retains review comment and uses the current immutable submission in the request',async()=>{
  let payload;const p=page({reviewEmploymentRegistration:async(target,body)=>{assert.equal(target,id);payload=body;throw Error('network')}},true);p.vm.state='ready';p.vm.selectedId=id;p.vm.detail=presentation.employmentView(row());p.vm.comment='请补充协议书照片'
  await p.vm.review('RETURN');assert.equal(payload.submissionId,'9007199254740993004');assert.equal(payload.expectedVersion,1);assert.equal(p.vm.comment,'请补充协议书照片');assert.equal(p.vm.receipt,null);assert.equal(p.vm.processing,false)
})
test('teacher conflict keeps the comment and requires another full-material inspection',async()=>{
  const p=page({reviewEmploymentRegistration:async()=>{throw {code:409001}},getEmploymentRegistration:async()=>({...row(2),sensitiveVisible:false})},true);p.vm.state='ready';p.vm.selectedId=id;p.vm.detail=presentation.employmentView(row());p.vm.comment='核对后确认材料齐全';await p.vm.review('APPROVE');assert.equal(p.vm.comment,'核对后确认材料齐全');assert.equal(p.vm.detail.version,2);assert.equal(p.vm.detail.sensitiveVisible,false)
})
test('teacher old-account disclosure and late review cannot change the current queue',async()=>{
  const wait=deferred(),p=page({discloseEmploymentRegistration:()=>wait.promise},true);p.vm.state='ready';p.vm.selectedId=id;p.vm.detail=presentation.employmentView({...row(),sensitiveVisible:false});p.vm.purpose='核对本次就业协议材料';const old=p.vm.detail,call=p.vm.disclose();p.switchAccount();wait.resolve(row());await call;assert.equal(p.vm.detail,old);p.vm.resetAccount();assert.equal(p.vm.detail,null);assert.equal(p.vm.purpose,'')
})
test('unknown machine values use neutral Chinese labels while user-authored content is preserved',()=>{
  const actual=presentation.employmentView({...row(),status:'UNKNOWN_STATE',current:{...row().current,registrationMode:'INTERNAL_MODE',sources:{studentName:'INTERNAL_SOURCE'},fields:{...declaration,companyName:'用户填写 Company 名称'}}})
  assert.equal(actual.statusLabel,'状态待确认');assert.equal(actual.current.modeLabel,'登记方式待确认');assert.equal(actual.current.fieldRows[0].sourceLabel,'来源待核实');assert.equal(actual.current.fieldRows.find(x=>x.key==='companyName').value,'用户填写 Company 名称');assert.equal(actual.current.fieldRows.find(x=>x.key==='majorMatch').value,'否')
})
