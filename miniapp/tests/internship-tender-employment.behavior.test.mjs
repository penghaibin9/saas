import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { compile, createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
import * as presentation from '../src/services/employmentPresentation.mjs'
import { reportFileState, reportFilesReady, refreshReportFiles } from '../src/services/weeklyReportPresentation.mjs'

const batch='9007199254740993001',record='9007199254740993002',id='9007199254740993003'
const prefill={identity:{studentName:'合成学生',studentNo:'SYN-001',collegeName:'合成学院',majorName:'合成专业',grade:'2024',className:'合成班级',enrollmentYear:'2024',studentPhone:'13800000000'},identityEditable:{enrollmentYear:false},canTransfer:false,transferHint:'请核对企业关联'}
const declaration={...prefill.identity,employmentType:'签约就业',companyName:'合成企业',creditCode:'91430100MA4L0ABC1D',companyAddress:'合成地址',companyScale:'小型',companyPhone:'073100000000',companyEmail:'synthetic@example.invalid',hrContact:'合成人事',companyNature:'民营',industry:'软件',jobCategory:'开发',positionName:'工程师',majorMatch:false,salary:'0',agreementNo:'SYN-001'}
const row=(version=1,status='SUBMITTED')=>({id,batchId:batch,internshipId:record,version,status,revisionCount:1,sensitiveVisible:true,current:{id:'9007199254740993004',revisionNo:1,registrationMode:'EMPLOYMENT',fields:{...declaration},sources:{},attachments:[]},history:[]})
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function page(overrides={},teacher=false,sdk={}){
  const source=fs.readFileSync(new URL(`../src/pages/${teacher?'teacher':'student'}-internship/employment/index.vue`,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  let generation=0;const reveals=[]
  const context={batches:[{id:batch,name:'合成批次'}],selectedBatchId:batch,can:()=>true,load:async()=>{},selectBatch(value){if(!this.batches.some(x=>x.id===value))return false;this.selectedBatchId=value;return true}}
  const api={getInternship:async()=>({hasBatch:true,batchId:batch,recordId:record,schoolMentor:'合成导师'}),getInternshipEmployment:async()=>({batchId:batch,internshipId:record,prefill,registration:null}),getEmploymentRegistrations:async()=>({items:[],total:0,hasMore:false}),getEmploymentRegistration:async()=>row(),...overrides}
  const employmentRead=api.getInternshipEmployment;api.getInternshipEmployment=async(...args)=>({canSubmit:true,...await employmentRead(...args)})
  const defaults={metadata:async fileId=>({fileId,status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true}),...sdk}
  const scope={go(){},studentApi:api,teacherApi:api,fileSdk:defaults,ReportFilePreview:{},normalizeError:e=>({text:'操作未完成',kind:Number(e?.code)===409001?'conflict':'unknown',pageState:'error'}),
    currentSessionGeneration:()=>generation,...presentation,reportFileState,reportFilesReady,refreshReportFiles,formatDateTime:x=>x,
    useInternshipContextStore:()=>context,uni:{pageScrollTo(){}}}
  const component=new Function(...Object.keys(scope),script)(...Object.values(scope))
  const vm={...component.data(),$refs:{photos:{reset(){},open:async()=>{},reveal:async()=>reveals.push('preview')}}}
  for(const [key,method] of Object.entries(component.methods))vm[key]=(...args)=>method.apply(vm,args)
  for(const [key,getter] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>getter.call(vm)})
  return {vm,component,api,context,reveals,switchAccount:()=>generation++}
}
async function ready(api={},sdk={}){const p=page(api,false,sdk);await p.vm.load();p.vm.form.fields={...declaration};p.vm.markDirty();return p}

test('精简页面默认收起长意见和通知，退回原因、办理限制及本版附件仍可见',async()=>{
  const source=fs.readFileSync(new URL('../src/pages/student-internship/employment/index.vue',import.meta.url),'utf8')
  const approved=presentation.employmentView({...row(8,'APPROVED'),revisionCount:4,current:{...row().current,revisionNo:4,review:{action:'APPROVE',comment:'应当收起的完整核验意见'},attachments:[{fileId:'9',fileName:'原版本照片.png'}]}})
  approved.history=[approved.current]
  async function render(overrides={}){
    const state=page(),shell={render(){return this.$slots.default?.()}}
    Object.assign(state.vm,{loaded:true,state:'ready',employmentWriteAllowed:true,submissionHint:'不应常驻首屏的冻结说明',prefill,registration:approved,
      form:presentation.employmentDraft(prefill,approved),notifications:{items:[{id:'n1',title:'核验通知',revisionNo:4,status:'READ',statusLabel:'已读',content:'应当收起的通知正文'}],total:1,unread:0},...overrides})
    const template=source.match(/<template>([\s\S]*?)<script>/)[1].replace(/<\/template>\s*$/,'')
    const renderTemplate=compile(template,{isCustomElement:tag=>['view','text'].includes(tag)})
    return renderToString(createSSRApp({components:{ReportFilePreview:shell,MobileNavBar:shell,MobileGlobalState:shell,MobileStatusTag:shell,MobileSafeAreaBar:shell},render:()=>renderTemplate(state.vm,[])}))
  }
  const html=await render();assert.ok(!html.includes('不应常驻首屏的冻结说明'));assert.ok(!html.includes('应当收起的完整核验意见'));assert.ok(!html.includes('应当收起的通知正文'))
  assert.ok(html.includes('查看全部通知'));assert.ok(!html.includes('通知详情'));assert.ok(html.includes('提交更正'));assert.ok(html.includes('查看本版详情'))
  const history=await render({expandedId:approved.current.id});assert.ok(history.includes('应当收起的完整核验意见'));assert.ok(history.includes('查看原版本照片.png'))
  const notices=await render({notificationsOpen:true,expandedId:'notice:n1'});assert.ok(notices.includes('应当收起的通知正文'));assert.ok(notices.includes('收起通知'))
  const returned={...approved,status:'RETURNED',current:{...approved.current,review:{action:'RETURN',comment:'请补齐4500元对应佐证'}}}
  const correction=await render({registration:returned});assert.ok(correction.includes('退回原因：请补齐4500元对应佐证'));assert.ok(correction.includes('补正重交'))
  assert.ok((await render({employmentWriteAllowed:false,submissionHint:'批次已关闭，仅可查看'})).includes('批次已关闭，仅可查看'))
})

test('visible result notifications stay unread until explicit acknowledgement and failed acknowledgement preserves the result',async()=>{
  const message={id:'9007199254740993020',title:'审核结果',content:'已退回补正',status:'UNREAD',statusLabel:'未读'}
  const p=await ready({getInternshipEmployment:async()=>({batchId:batch,internshipId:record,prefill,registration:row(2,'RETURNED'),resultNotifications:{items:[message],total:1,unread:1,page:1,hasMore:false}}),readInternshipEmploymentResult:async()=>{throw Error('network')}})
  assert.equal(p.vm.notifications.unread,1);await p.vm.readNotification(message);assert.equal(p.vm.notifications.items[0].status,'UNREAD');assert.ok(p.vm.notificationError);assert.equal(p.vm.form.fields.salary,'0')
  let submitted; p.api.readInternshipEmploymentResult=async(...args)=>{submitted=args;return {...message,status:'READ',statusLabel:'已读'}}
  await p.vm.readNotification(message);assert.deepEqual(submitted,[message.id,batch,record]);assert.equal(p.vm.notifications.unread,0);assert.equal(p.vm.notifications.items[0].statusLabel,'已读');assert.equal(p.vm.notificationError,'')
})
test('通知只预览最新一条，展开翻页收起不标已读、不清草稿，切身份恢复收起',async()=>{
  let acknowledged=0
  const p=await ready({getInternshipEmployment:async(b,r,page)=>({batchId:b,internshipId:r,prefill,registration:null,resultNotifications:{items:page===1?[{id:'n2',title:'最新通知'},{id:'n1',title:'较早通知'}]:[{id:'n0',title:'最早通知'}],total:3,unread:3,page,hasMore:page===1}}),readInternshipEmploymentResult:async()=>{acknowledged++}})
  p.vm.form.fields.positionName='尚未提交的更正';assert.deepEqual(p.vm.visibleNotifications.map(x=>x.id),['n2'])
  await p.vm.toggleNotifications();assert.equal(p.vm.visibleNotifications.length,2)
  await p.vm.changeNotificationPage(1);assert.equal(p.vm.notificationPage,2)
  await p.vm.toggleNotifications();assert.equal(p.vm.notificationsOpen,false);assert.equal(p.vm.notificationPage,1);assert.equal(p.vm.visibleNotifications[0].id,'n2')
  assert.equal(p.vm.form.fields.positionName,'尚未提交的更正');assert.equal(acknowledged,0);assert.equal(p.vm.notifications.unread,3)
  await p.vm.toggleNotifications();p.switchAccount();p.vm.resetAccount();assert.equal(p.vm.notificationsOpen,false);assert.equal(p.vm.visibleNotifications.length,0)
})
test('教师字段按真实来源分组，混合来源保留例外，隐藏信息和零值不被改写',()=>{
  const p=page({},true),sources=Object.fromEntries(presentation.employmentFields.map(f=>[f.key,f.school?'SCHOOL_PROFILE':'STUDENT_DECLARED']))
  sources.companyName='CURRENT_INTERNSHIP_COMPANY'
  p.vm.detail=presentation.employmentView({...row(),sensitiveVisible:false,current:{...row().current,sources}})
  const original=JSON.stringify(p.vm.detail),identity=p.vm.fieldGroups.find(g=>g.key==='identity'),company=p.vm.fieldGroups.find(g=>g.key==='company')
  assert.equal(identity.source,'学校档案');assert.equal(identity.fields.find(f=>f.key==='enrollmentYear').sourceLabel,'学生本次填报')
  assert.equal(company.source,'学生本次填报');assert.equal(company.fields.find(f=>f.key==='companyName').sourceLabel,'当前正式实习企业')
  assert.equal(p.vm.fieldValue({value:'已隐藏，请说明核验用途后查看'}),'已隐藏');assert.equal(p.vm.fieldValue({value:'0'}),'0')
  assert.equal(JSON.stringify(p.vm.detail),original)
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

test('就业附件预览完成后定位到预览区，旧上下文迟到结果不滚动当前页面',async()=>{
  for(const teacher of [false,true]){
    const p=teacher?page({},true):await ready();p.vm.state='ready';p.vm.detail=presentation.employmentView({...row(),sensitiveVisible:true})
    await p.vm.openPhoto({fileId:'9'});assert.deepEqual(p.reveals,['preview'])
    const wait=deferred();p.vm.$refs.photos.open=()=>wait.promise
    const opening=p.vm.openPhoto({fileId:'10'});p.vm.epoch++;wait.resolve();await opening
    assert.equal(p.reveals.length,1)
  }
})

test('附件图片就绪后可按实际布局定位，已关闭的预览不定位',async()=>{
  const source=fs.readFileSync(new URL('../src/components/ReportFilePreview.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
  const component=new Function('fileSdk','normalizeError','currentSessionGeneration','loadReportMedia','releasePreview',source.replace(/^import[^\n]+\r?\n/gm,'').replace('export default','return'))({},()=>({}),()=>0,()=>{},()=>{})
  const calls=[],vm={...component.data(),$nextTick:async()=>{},$el:{scrollIntoView:value=>calls.push(value)}}
  vm.visible=true;await component.methods.reveal.call(vm);assert.deepEqual(calls,[{block:'start',behavior:'smooth'}])
  const wait=deferred();vm.$nextTick=()=>wait.promise;const old=component.methods.reveal.call(vm)
  component.methods.reset.call(vm);wait.resolve();await old;assert.equal(calls.length,1);assert.equal(vm.revealRequested,false)
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
test('archived employment uses explicit server permission; a closed batch or missing permission stays readonly',async()=>{
  for(const allowed of [true,false,undefined]){
    const p=await ready({getInternship:async()=>({hasBatch:true,batchId:batch,recordId:record,historyMode:true}),
      getInternshipEmployment:async()=>({batchId:batch,internshipId:record,prefill,registration:null,canSubmit:allowed,submissionHint:'归档后就业单独留存'})})
    assert.equal(p.vm.editable,allowed===true);assert.equal(p.vm.submissionHint,'归档后就业单独留存')
  }
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
  const returned=row(2,'RETURNED'),latest=row(3,'RETURNED');const p=await ready({getInternshipEmployment:async()=>({batchId:batch,internshipId:record,prefill,registration:returned}),submitInternshipEmployment:async()=>{p.api.getInternshipEmployment=async()=>({batchId:batch,internshipId:record,prefill,registration:latest,canSubmit:true});throw {code:409001}}})
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

test('就业更正切换方式后保留各自单位岗位草稿，重复点当前方式不重置输入',async()=>{
  const p=await ready({getInternshipEmployment:async()=>({batchId:batch,internshipId:record,prefill,registration:row(4,'APPROVED')})})
  p.vm.prefill={...prefill,canTransfer:true,transfer:{companyName:'正式实习企业',creditCode:declaration.creditCode,companyAddress:'',positionName:'实习岗位'}}
  p.vm.form.fields.companyName='核验后更正单位';p.vm.form.fields.companyAddress='核验后更正地址';p.vm.form.fields.positionName='更正岗位'
  p.vm.form.attachments=[{fileId:'9'}];p.vm.form.correctionReason='本次已核对更正内容'
  p.vm.chooseMode('INTERNSHIP_TRANSFER');p.vm.form.fields.companyAddress='转就业地址';p.vm.form.fields.positionName='转就业岗位'
  p.vm.chooseMode('INTERNSHIP_TRANSFER');assert.equal(p.vm.form.fields.companyAddress,'转就业地址')
  p.vm.chooseMode('EMPLOYMENT');assert.equal(p.vm.form.fields.companyName,'核验后更正单位');assert.equal(p.vm.form.fields.companyAddress,'核验后更正地址');assert.equal(p.vm.form.fields.positionName,'更正岗位')
  p.vm.chooseMode('INTERNSHIP_TRANSFER');assert.equal(p.vm.form.fields.companyAddress,'转就业地址');assert.equal(p.vm.form.fields.positionName,'转就业岗位')
  assert.equal(p.vm.form.attachments[0].fileId,'9');assert.equal(p.vm.form.correctionReason,'本次已核对更正内容')
})

test('切换登记方式不恢复旧学校身份，账号和实习上下文变化清除方式草稿',async()=>{
  const p=await ready();p.vm.prefill={...prefill,canTransfer:true,transfer:{companyName:'实习企业',creditCode:declaration.creditCode}}
  p.vm.chooseMode('INTERNSHIP_TRANSFER');p.vm.form.fields.studentName='学校最新姓名';p.vm.form.fields.studentPhone='13900000000'
  p.vm.chooseMode('EMPLOYMENT');assert.equal(p.vm.form.fields.studentName,'学校最新姓名');assert.equal(p.vm.form.fields.studentPhone,'13900000000')
  p.vm.requestedBatch='';p.vm.contextKey='old:placement';await p.vm.load();assert.deepEqual(p.vm.modeFields,{})
  p.vm.modeFields={EMPLOYMENT:{companyName:'旧账号单位'}};p.vm.resetAccount();assert.deepEqual(p.vm.modeFields,{})
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
