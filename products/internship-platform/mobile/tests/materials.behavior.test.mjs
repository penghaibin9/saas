import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as readiness from '../src/services/fileReadiness.mjs'

const clean = {fileId:'9007199254740993003',fileName:'原始 Insurance 保单.pdf',status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true,allowedActions:['preview','download']}
const pending = {...clean,status:'QUARANTINED',scanStatus:'PENDING',readyForBusiness:false}
const context = {batchId:'9007199254740993001',recordId:'9007199254740993002',hasBatch:true}
const requirement = {id:'9007199254740993004',materialName:'企业接收函',allowedExtensions:['pdf'],minFiles:1,maxFiles:2}
const deferred = () => {let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function page(path, api={}, sdk={}, extra={}) {
  const source=fs.readFileSync(new URL('../src/pages/'+path,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm,'').replace('export default','return')
  let generation=0
  const deps={studentApi:api,fileSdk:sdk,chooseSingleFile:()=>sdk.choose(),uploadBusinessFile:(...args)=>sdk.upload(...args),openBusinessFile:(...args)=>sdk.open?.(...args),toast:()=>{},normalizeError:()=>({text:'操作未完成，请重试'}),currentSessionGeneration:()=>generation,...readiness,...extra}
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...component.data()}
  for(const [name,fn]of Object.entries(component.methods))vm[name]=(...args)=>fn.apply(vm,args)
  for(const [name,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,name,{get:()=>fn.call(vm)})
  return {vm,component,switchAccount:()=>generation++}
}
function insurance(api={},sdk={}) {
  return page('student-internship/insurance/index.vue',{getInternship:async()=>context,getInternshipInsurance:async()=>({status:'NOT_SUBMITTED',version:0}),...api},{choose:async()=>({path:'private-file',name:clean.fileName}),upload:async()=>pending,metadata:async()=>clean,...sdk})
}
function materials(api={},sdk={}) {
  return page('student-internship/materials/index.vue',{getInternship:async()=>context,getInternshipMaterialRequirements:async()=>[requirement],...api},{choose:async()=>({path:'private-file',name:'企业接收函.pdf'}),upload:async()=>pending,metadata:async()=>clean,...sdk})
}
function fillInsurance(vm) {Object.assign(vm.form,{insurerName:'合成承保公司',policyNo:'SYNTHETIC-001',effectiveDate:'2026-09-01',expiryDate:'2027-12-31'})}

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
function teacher(meta=async()=>clean) {
  let modal;const posts=[],store={batches:[{id:context.batchId,name:'合成材料批次',studentCount:1}],selectedBatchId:context.batchId,restore(){},async load(){},can(){return true}}
  const p=page('teacher-internship/material-review/index.vue',{}, {metadata:meta},{useInternshipContextStore:()=>store,
    teacherInternshipMaterialRequirements:async()=>[{...requirement,materialCode:'INTERNAL_CODE'}],teacherInternshipMaterialCoverage:async()=>({requiredStudents:1}),teacherInternshipMaterialStudents:async()=>({items:[{internshipId:context.recordId,submission}],hasMore:false}),
    teacherInternshipMaterialReview:async(...args)=>posts.push(args),uni:{showModal:value=>{modal=value}}})
  return {...p,posts,store,modal:()=>modal}
}
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

test('正常教师已有材料审核权限时工作台显示入口，撤权后移除',()=>{
  let allowed=true
  const p=page('teacher-internship/index.vue',{}, {},{TeacherNoticeInbox:{},useInternshipContextStore:()=>({can:key=>allowed && key==='internship.report.review'})})
  assert.equal(p.vm.visibleItems.find(item=>item.label==='材料审核')?.path,'/pages/teacher-internship/material-review/index')
  allowed=false;assert.equal(p.vm.visibleItems.some(item=>item.label==='材料审核'),false)
})
