import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as readiness from '../src/services/fileReadiness.mjs'
import { releasePreview } from '../src/services/reportMedia.mjs'

const clean = {fileId:'9007199254740993003',fileName:'原始 Insurance 保单.pdf',status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true,allowedActions:['preview','download']}
const pending = {...clean,status:'QUARANTINED',scanStatus:'PENDING',readyForBusiness:false}
const context = {batchId:'9007199254740993001',recordId:'9007199254740993002',hasBatch:true}
const requirement = {id:'9007199254740993004',materialName:'企业接收函',allowedExtensions:['pdf'],minFiles:1,maxFiles:2}
const deferred = () => {let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function page(path, api={}, sdk={}, extra={}) {
  const source=fs.readFileSync(new URL('../src/pages/'+path,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm,'').replace('export default','return')
  let generation=0
  const deps={studentApi:api,fileSdk:sdk,chooseSingleFile:()=>sdk.choose(),uploadBusinessFile:(...args)=>sdk.upload(...args),openBusinessFile:(...args)=>sdk.open?.(...args),toast:()=>{},normalizeError:()=>({text:'操作未完成，请重试'}),currentSessionGeneration:()=>generation,releasePreview,...readiness,...extra}
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...component.data()}
  for(const [name,fn]of Object.entries(component.methods))vm[name]=(...args)=>fn.apply(vm,args)
  for(const [name,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,name,{get:()=>fn.call(vm)})
  return {vm,component,switchAccount:()=>generation++}
}
function insurance(api={},sdk={}) {
  return page('student-internship/insurance/index.vue',{getInternship:async()=>context,getInternshipInsurance:async()=>({status:'NOT_SUBMITTED',version:0}),...api},{choose:async()=>({path:'private-file',name:clean.fileName}),upload:async()=>pending,metadata:async()=>clean,...sdk})
}
function materials(api={},sdk={},extra={}) {
  return page('student-internship/materials/index.vue',{getInternship:async()=>context,getInternshipMaterialRequirements:async()=>[requirement],...api},{choose:async()=>({path:'private-file',name:'企业接收函.pdf'}),upload:async()=>pending,metadata:async()=>clean,...sdk},extra)
}
function fillInsurance(vm) {Object.assign(vm.form,{insurerName:'合成承保公司',policyNo:'SYNTHETIC-001',effectiveDate:'2026-09-01',expiryDate:'2027-12-31'})}

test('八种规定材料格式显示为五类中文名称，压缩格式不显示未知或重复类别',async()=>{
  const {vm}=materials({getInternshipMaterialRequirements:async()=>[{...requirement,allowedExtensions:['png','doc','docx','pdf','xls','xlsx','zip','rar']}]})
  await vm.load()
  assert.equal(vm.items[0].allowedFormatLabel,'图片 / 文字文档 / 便携文档 / 电子表格 / 压缩文件')
})

test('统一文件适配严格核对可用状态，不把字符串或未知扫描状态当安全可用',()=>{
  const source=fs.readFileSync(new URL('../src/services/fileSdk.js',import.meta.url),'utf8').replace(/^import[^\n]+\n/gm,'').replace(/^export default[^\n]+/gm,'').replace(/^export /gm,'')
  const deps={...readiness,FILE_SCAN_TEXT:readiness.FILE_STATUS_TEXT};delete deps.FILE_STATUS_TEXT
  const normalize=new Function(...Object.keys(deps),'realRequest','realUpload','realDownload',source+'\nreturn normalizeFile')(...Object.values(deps))
  for(const changed of [{readyForBusiness:'false'},{scanStatus:'INFECTED'},{scanStatus:''},{status:'QUARANTINED'}])assert.equal(normalize({...clean,...changed}).readyForBusiness,false)
  assert.equal(normalize(clean).canPreview,true);assert.equal(normalize(pending).canPreview,false)
  assert.equal(normalize(clean).fileName,clean.fileName)
  assert.equal(normalize({...clean,scanStatus:'UNKNOWN_VALUE'}).statusText,'文件状态待确认')
})
test('保险等待扫描时阻止提交，读取真实扫描结果后原填写内容和大编号继续提交',async()=>{
  const posts=[],{vm}=insurance({submitInternshipInsurance:async body=>posts.push(body)})
  await vm.load();fillInsurance(vm);await vm.pickFile();await vm.submit();assert.equal(posts.length,0);assert.equal(vm.form.policyNo,'SYNTHETIC-001')
  await vm.refreshAttachment();await vm.submit();assert.equal(posts.length,1);assert.equal(posts[0].fileId,clean.fileId);assert.equal(posts[0].batchId,context.batchId);assert.equal(posts[0].internshipId,context.recordId)
})
test('分类材料等待扫描时不能提交，安全可用后按同一要求及当前实习记录办理',async()=>{
  const posts=[],{vm}=materials({submitInternshipMaterial:async(...args)=>posts.push(args)})
  await vm.load();await vm.pick(requirement);await vm.submit(requirement);assert.equal(posts.length,0);assert.equal(vm.pending(requirement.id).length,1)
  await vm.refreshPending(requirement);await vm.submit(requirement);assert.equal(posts.length,1);assert.equal(posts[0][0],requirement.id);assert.deepEqual(posts[0][1].fileIds,[clean.fileId]);assert.equal(posts[0][1].internshipId,context.recordId)
})
test('扫描读取失败和未知文件编号保留保险填写及分类材料，不提示成功',async()=>{
  const {vm}=insurance({}, {metadata:async()=>{throw Error('INTERNAL_ENGINE_PATH')}});await vm.load();fillInsurance(vm);await vm.pickFile();await vm.refreshAttachment()
  assert.equal(vm.form.fileId,clean.fileId);assert.equal(vm.form.policyNo,'SYNTHETIC-001');assert.match(vm.submitError,/保留/);assert.doesNotMatch(vm.submitError,/INTERNAL_ENGINE_PATH/)
  const m=materials({}, {metadata:async()=>({...clean,fileId:'other'})});await m.vm.load();await m.vm.pick(requirement);await m.vm.refreshPending(requirement);assert.equal(m.vm.pending(requirement.id).length,1);assert.equal(m.vm.pending(requirement.id)[0].readyForBusiness,false)
})
test('文件选择后换账号不能上传或回填旧材料',async()=>{
  const chosen=deferred();let uploads=0
  const {vm,switchAccount}=materials({}, {choose:()=>chosen.promise,upload:async()=>{uploads++;return clean}});await vm.load();const work=vm.pick(requirement);switchAccount();chosen.resolve({path:'private-file',name:'企业接收函.pdf'});await work;assert.equal(uploads,0);assert.equal(vm.pending(requirement.id).length,0)
})
test('迟到扫描结果不能恢复已移除材料或带入另一账号',async()=>{
  const scanned=deferred(),{vm,switchAccount}=materials({}, {metadata:()=>scanned.promise});await vm.load();await vm.pick(requirement);const work=vm.refreshPending(requirement);vm.removePending(requirement.id,0);switchAccount();scanned.resolve(clean);await work;assert.equal(vm.pending(requirement.id).length,0)
})
test('扫描回读缺少权威可用字段时，不能继承旧的安全状态',async()=>{
  const rows=await readiness.refreshFileReadiness([clean],async()=>({fileId:clean.fileId}))
  assert.equal(rows[0].readyForBusiness,false);assert.equal(rows[0].statusText,'文件状态待确认')
  assert.equal(readiness.materialSubmissionView({status:'INTERNAL_STATE',files:[{scanStatus:'UNKNOWN_ENGINE'}]}).statusLabel,'状态待确认')
  assert.equal(readiness.materialSubmissionView({files:[{scanStatus:'UNKNOWN_ENGINE'}]}).files[0].statusText,'文件状态待确认')
})
test('隐藏页面后迟到扫描不解锁提交，重新读取可以继续原保险填写',async()=>{
  const wait=deferred(),{vm,component}=insurance({}, {metadata:()=>wait.promise})
  await vm.load();fillInsurance(vm);await vm.pickFile();const work=vm.refreshAttachment();component.onHide.call(vm);wait.resolve(clean);await work
  assert.equal(vm.attachmentReady,false);assert.equal(vm.scanning,false);assert.equal(vm.form.policyNo,'SYNTHETIC-001')
  component.onShow.call(vm);await vm.refreshAttachment();assert.equal(vm.attachmentReady,true)
})
const submission={id:'9007199254740993005',status:'SUBMITTED',version:1,files:[{fileId:clean.fileId,scanStatus:'CLEAN',versionNo:1}],reviewComment:''}
function teacher(meta=async()=>clean,extra={}) {
  let modal;const posts=[],store={batches:[{id:context.batchId,name:'合成材料批次',studentCount:1}],selectedBatchId:context.batchId,restore(){},async load(){},can(){return true}}
  const p=page('teacher-internship/material-review/index.vue',{}, {metadata:meta},{useInternshipContextStore:()=>store,
    teacherInternshipMaterialRequirements:async()=>[{...requirement,materialCode:'INTERNAL_CODE'}],teacherInternshipMaterialCoverage:async()=>({requiredStudents:1}),teacherInternshipMaterialStudents:async()=>({items:[{internshipId:context.recordId,submission}],hasMore:false}),
    teacherInternshipMaterialReview:async(...args)=>posts.push(args),uni:{showModal:value=>{modal=value}},...extra})
  return {...p,posts,store,modal:()=>modal}
}
test('学生模板下载传递所见版本，教师可分别查询已通过、退回及撤回', async()=>{
  const downloads=[]
  const p=materials({downloadInternshipMaterialTemplate:async(...args)=>{downloads.push(args);return {} }})
  await p.vm.load();await p.vm.downloadTemplate({...requirement,template:{versionId:'9007199254740993999',versionNo:1}})
  assert.deepEqual(downloads[0],[requirement.id,context.batchId,context.recordId,'9007199254740993999'])
  const t=teacher();await t.vm.load()
  for(const state of ['APPROVED','RETURNED','WITHDRAWN','DRAFT']) {
    assert(t.vm.states.some(item=>item.value===state));await t.vm.setState(state)
    assert.equal(t.vm.stateFilter,state);assert.doesNotMatch(t.vm.emptyTitle,/APPROVED|RETURNED|WITHDRAWN|DRAFT/)
  }
})

test('网页模板下载实际保存所见文件名并释放临时地址',async()=>{
  const saved=[],released=[];const link={click(){saved.push({url:this.href,name:this.download})},remove(){}}
  const p=materials({downloadInternshipMaterialTemplate:async()=>({tempFilePath:'blob:checked-template'})},{},
    {document:{createElement:()=>link,body:{appendChild(){}}},releasePreview:url=>released.push(url),setTimeout:fn=>fn()})
  await p.vm.load();await p.vm.downloadTemplate({...requirement,template:{versionId:'5',fileName:'学校模板.docx'}})
  assert.deepEqual(saved,[{url:'blob:checked-template',name:'学校模板.docx'}]);assert.deepEqual(released,['blob:checked-template'])
})

test('模板下载期间换会话不保存旧文件，原生打开保留明确格式',async()=>{
  const wait=deferred(),released=[],opened=[]
  const p=materials({downloadInternshipMaterialTemplate:()=>wait.promise},{},{releasePreview:url=>released.push(url),uni:{openDocument:options=>opened.push(options)}})
  await p.vm.load();const request=p.vm.downloadTemplate({...requirement,template:{versionId:'5',fileName:'学校模板.docx'}})
  p.switchAccount();wait.resolve({tempFilePath:'blob:old-context'});await request
  assert.deepEqual(opened,[]);assert.deepEqual(released,['blob:old-context'])
  const native=materials({downloadInternshipMaterialTemplate:async()=>({tempFilePath:'/private/temporary-document'})},{},{uni:{openDocument:options=>opened.push(options)}})
  await native.vm.load();await native.vm.downloadTemplate({...requirement,template:{versionId:'5',fileName:'学校模板.docx'}})
  assert.equal(opened[0].fileType,'docx');assert.equal(opened[0].filePath,'/private/temporary-document')
})
test('教师审核展示中文扫描结果，当前文件未安全可用时不能发起通过命令',async()=>{
  let meta=pending;const p=teacher(async()=>meta);await p.vm.load()
  assert.equal(p.vm.rows[0].submission.files[0].statusText,'安全可用');assert.deepEqual(p.vm.requirementLabels,[requirement.materialName])
  p.vm.review(p.vm.rows[0],'APPROVE');await p.modal().success({confirm:true,content:'核对企业接收函'});assert.equal(p.posts.length,0)
  meta=clean;p.vm.review(p.vm.rows[0],'APPROVE');await p.modal().success({confirm:true,content:'核对企业接收函'});assert.equal(p.posts.length,1);assert.equal(p.posts[0][1].expectedVersion,submission.version)
})
test('教师旧审核确认框在换账号或换材料任务后不再提交',async()=>{
  const p=teacher();await p.vm.load();p.vm.review(p.vm.rows[0],'RETURN');p.switchAccount();await p.modal().success({confirm:true,content:'请补充清晰盖章接收函'});assert.equal(p.posts.length,0)
  const q=teacher();await q.vm.load();q.vm.review(q.vm.rows[0],'APPROVE');await q.vm.loadRequirement();await q.modal().success({confirm:true,content:''});assert.equal(q.posts.length,0)
})

test('教师材料读取按公共错误口径区分权限、失效、离线与失败，不保留旧名单',async()=>{
  for(const pageState of ['forbidden','unauthorized','noLicense','offline','error']) {
    const failure={httpStatus:403},normalizeError=e=>{assert.equal(e,failure);return {pageState,text:'读取未完成'}}
    const p=teacher(undefined,{normalizeError});p.store.load=async()=>{throw failure}
    p.vm.batches=[{id:'旧批次',name:'旧账号批次'}];p.vm.rows=[{studentName:'旧名单'}];p.vm.coverage={requiredStudents:99}
    await p.vm.load();assert.equal(p.vm.state,pageState);assert.deepEqual(p.vm.rows,[]);assert.equal(p.vm.coverage,null)
    assert.deepEqual(p.vm.batches,[]);assert.equal(p.vm.batchId,'')
    const q=teacher(undefined,{normalizeError,teacherInternshipMaterialStudents:async()=>{throw failure}})
    await q.vm.load();assert.equal(q.vm.state,pageState);assert.deepEqual(q.vm.rows,[]);assert.equal(q.vm.coverage,null)
  }
})

test('学生材料读取复用公共错误状态，清除旧显示并保留同一任务未交文件以便重试',async()=>{
  for(const stage of ['getInternship','getInternshipMaterialRequirements'])for(const pageState of ['forbidden','unauthorized','noLicense','offline','error']) {
    const failure={httpStatus:403};let fail=false
    const original=stage==='getInternship'?context:[requirement]
    const p=materials({[stage]:async()=>{if(fail)throw failure;return original}}, {}, {normalizeError:e=>{assert.equal(e,failure);return {pageState,text:'读取未完成'}}})
    await p.vm.load();await p.vm.pick(requirement);fail=true;await p.vm.load()
    assert.equal(p.vm.state,pageState);assert.deepEqual(p.vm.items,[]);assert.equal(p.vm.pending(requirement.id).length,1)
    fail=false;await p.vm.load();assert.equal(p.vm.state,'ready');assert.equal(p.vm.pending(requirement.id).length,1)
  }
})

test('首次加载被隐藏后返回可重新读取，不停留在加载界面',async()=>{
  for(const create of [insurance,materials]) {
    const delayed=deferred();let reads=0
    const p=create({getInternship:()=>++reads===1?delayed.promise:Promise.resolve(context)})
    const old=p.vm.load();p.component.onHide.call(p.vm);delayed.resolve(context);await old
    await p.component.onShow.call(p.vm)
    assert.equal(p.vm.pageState || p.vm.state,'ready');assert.equal(reads,2)
  }
})

test('旧账号的上传结束不会解锁新账号正在进行的上传',async()=>{
  const chosen=deferred(),p=insurance({}, {choose:()=>chosen.promise})
  await p.vm.load();const old=p.vm.pickFile();p.switchAccount();await p.vm.load();p.vm.uploading=true
  chosen.resolve({path:'private-file',name:'保单.pdf'});await old
  assert.equal(p.vm.uploading,true);assert.equal(p.vm.form.fileId,'')
})

test('保险读取显式传入同一批次和实习记录，不使用旧默认记录',async()=>{
  const reads=[],p=insurance({getInternshipInsurance:async(...args)=>{reads.push(args);return {status:'NOT_SUBMITTED',version:0}}})
  await p.vm.load();assert.deepEqual(reads,[[context.batchId,context.recordId]])
})

test('教师工作台按材料与巡访各自权限显示入口，携带同一批次且保留巡访页签',()=>{
  let allowed=true;const routes=[]
  const p=page('teacher-internship/index.vue',{}, {},{TeacherNoticeInbox:{},SchoolServiceInfo:{},go:path=>routes.push(path),useInternshipContextStore:()=>({selectedBatchId:context.batchId,can:key=>allowed && ['internship.report.review','internship.visit.view'].includes(key)})})
  assert.equal(p.vm.visibleItems.find(item=>item.label==='材料审核')?.path,'/pages/teacher-internship/material-review/index')
  const visit=p.vm.visibleItems.find(item=>item.label==='巡访任务');p.vm.open(visit)
  assert.equal(routes[0],'/pages/teacher-internship/internship-review/index?tab=visit&batchId='+context.batchId)
  p.vm.open(p.vm.visibleItems.find(item=>item.label==='材料审核'))
  assert.equal(routes[1],'/pages/teacher-internship/material-review/index?batchId='+context.batchId)
  allowed=false;assert.equal(p.vm.visibleItems.some(item=>item.label==='材料审核'),false)
  assert.equal(p.vm.visibleItems.some(item=>item.label==='巡访任务'),false)
})

test('教师工作台允许只读报告入口，材料审核仍需批阅权限且无查看权限不显示报告',()=>{
  const routes=[],permissions=new Set(['internship.report.view']);let menu
  const p=page('teacher-internship/index.vue',{}, {},{TeacherNoticeInbox:{},SchoolServiceInfo:{},uni:{showActionSheet:options=>menu=options},go:path=>routes.push(path),useInternshipContextStore:()=>({selectedBatchId:context.batchId,can:key=>permissions.has(key)})})
  const report=p.vm.visibleItems.find(item=>item.label==='报告批阅')
  assert.equal(report?.path,'/pages/teacher-internship/process-report-review/index')
  assert.equal(p.vm.visibleItems.some(item=>item.label==='材料审核'),false)
  p.vm.open(report)
  assert.equal(routes.length,0);menu.success({tapIndex:1})
  assert.deepEqual(routes,['/pages/teacher-internship/process-report-review/index?batchId='+context.batchId])
  permissions.add('internship.report.review')
  assert.equal(p.vm.visibleItems.some(item=>item.label==='报告批阅'),true)
  assert.equal(p.vm.visibleItems.some(item=>item.label==='材料审核'),true)
  permissions.delete('internship.report.view')
  assert.equal(p.vm.visibleItems.some(item=>item.label==='报告批阅'),false)
  assert.equal(p.vm.visibleItems.some(item=>item.label==='材料审核'),true)
  permissions.clear()
  assert.equal(p.vm.visibleItems.some(item=>item.label==='报告批阅'),false)
  assert.equal(p.vm.visibleItems.some(item=>item.label==='材料审核'),false)
})

test('材料折叠只改变显示，八份文件仍按原单版本全部提交',async()=>{
  const req={...requirement,minFiles:8,maxFiles:8,submission:{id:'55',version:4,status:'RETURNED'}},posts=[]
  const p=materials({getInternshipMaterialRequirements:async()=>[req],submitInternshipMaterial:async(...args)=>posts.push(args)})
  await p.vm.load();const files=Array.from({length:8},(_,i)=>({...clean,fileId:String(900+i),fileName:'合成'+i+'.pdf'}))
  p.vm.pendingByRequirement={[req.id]:files};assert.equal(p.vm.visibleFiles(files,req.id).length,4)
  p.vm.toggleFiles(req.id);assert.equal(p.vm.visibleFiles(files,req.id).length,8)
  p.vm.toggleFiles(req.id);await p.vm.submit(req)
  assert.deepEqual(posts[0][1].fileIds,files.map(file=>file.fileId));assert.equal(posts[0][1].expectedVersion,4)
})

test('材料要求切换保留各自未交文件，历史实习只有查看',async()=>{
  const second={...requirement,id:'second',materialName:'另一个材料'}
  const p=materials({getInternshipMaterialRequirements:async()=>[requirement,second]});await p.vm.load()
  p.vm.pendingByRequirement={[requirement.id]:[clean]};p.vm.requirementMenuOpen=true;p.vm.chooseRequirement(1)
  assert.equal(p.vm.requirementMenuOpen,false)
  assert.equal(p.vm.activeItem.id,'second');assert.equal(p.vm.pending(requirement.id).length,1)
  p.vm.historyMode=true;assert.equal(p.vm.canSubmit(second),false)
})

test('审核列表逐人展示与文件展开保留原集合，旧确认框在切人后失效',async()=>{
  const files=Array.from({length:8},(_,i)=>({...submission.files[0],slotNo:i+1,fileId:String(800+i)}))
  const p=teacher();await p.vm.load();p.vm.rows=[{internshipId:'one',submission:{...submission,files}},{internshipId:'two',submission:{...submission,id:'second'}}]
  assert.equal(p.vm.displayedRows.length,1);assert.equal(p.vm.visibleFiles(p.vm.activeRow).length,3)
  p.vm.toggleFiles(p.vm.activeRow);assert.equal(p.vm.visibleFiles(p.vm.activeRow).length,8)
  p.vm.review(p.vm.activeRow,'RETURN');const modal=p.modal();p.vm.selectReviewRow(1);await modal.success({confirm:true,content:'请按原要求补正材料'})
  assert.equal(p.posts.length,0);assert.equal(p.vm.activeRow.internshipId,'two');assert.equal(p.vm.rows.length,2)
})

test('审核意见按原版本保留，新版本必须明确核对后才能提交',async()=>{
  const p=teacher();await p.vm.load();const old=p.vm.rows[0]
  p.vm.setReviewComment(old,{detail:{value:'请按原要求补清晰文件'}})
  const latest={...old,submission:{...old.submission,version:2}};p.vm.rows=[latest]
  assert.equal(p.vm.draftConflict(latest),true);p.vm.review(latest,'RETURN');assert.equal(p.posts.length,0)
  p.vm.adoptReviewDraft(latest);assert.equal(p.vm.draftConflict(latest),false);p.vm.review(latest,'RETURN')
  assert.equal(p.modal().content,'请按原要求补清晰文件');await p.modal().success({confirm:true,content:p.modal().content})
  assert.equal(p.posts[0][1].expectedVersion,2);assert.equal(p.posts[0][1].comment,'请按原要求补清晰文件')
})

test('首页分类参数仅接受正式待办分组，并实际传给原查询',async()=>{
  const calls=[],p=page('teacher-internship/todos/index.vue',{}, {},{teacherApi:{getInternshipWorkbenchTodos:async args=>{calls.push(args);return {items:[],groupCounts:{},hasMore:false}}},go(){}})
  p.component.onLoad.call(p.vm,{group:'REPORT'});await p.vm.load();assert.equal(calls[0].group,'REPORT')
  p.component.onLoad.call(p.vm,{group:'UNTRUSTED'});assert.equal(p.vm.group,'REPORT')
})

test('新进入材料页先显示退回原单，明确选择已办要求后保持原选择',async()=>{
  const done={...requirement,id:'done',submission:{...submission,status:'APPROVED'}},returned={...requirement,id:'returned',submission:{...submission,status:'RETURNED'}}
  const p=materials({getInternshipMaterialRequirements:async()=>[done,returned]});await p.vm.load();assert.equal(p.vm.activeItem.id,'returned')
  p.vm.chooseRequirement(0);await p.vm.load();assert.equal(p.vm.activeItem.id,'done')
})
