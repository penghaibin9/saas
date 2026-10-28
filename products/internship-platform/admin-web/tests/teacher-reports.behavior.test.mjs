import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import {teacherReportTypes,teacherReportView,reportValidation} from '../src/modules/internship/services/teacherReportPresentation.mjs'
const batch='9007199254740993001',id='9007199254740993002'
const ok=data=>({code:0,data}),row=()=>({id,batchId:batch,reportType:'WEEKLY',periodKey:'2026-W40',content:'合成指导工作。'.repeat(10),version:0,attachments:[]})
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}
function page(api={},sdk={},canWrite=true){
  const source=fs.readFileSync(new URL('../src/modules/internship/views/MyTeacherReportsView.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  let generation=0,downloads=0
  const store={selectedBatchId:batch}
  const scope={ModulePageShell:{},ErrorState:{},LoadingState:{},AppButton:{},FilePreviewer:{},teacherReportTypes,teacherReportView,reportValidation,
    internshipApi:{getTeacherPeriodReports:async()=>ok({items:[row()],total:1,rules:{}}),saveTeacherPeriodReport:async()=>ok(row()),exportTeacherPeriodReports:async()=>ok({}),...api},
    useInternshipBatchStore:()=>store,canCode:(_ctx,code)=>code!=='internship.guidance.manage'||canWrite,fileSdk:{metadata:async fileId=>({fileId}),...sdk},currentSessionGeneration:()=>generation,
    normalizeUiError:()=>({userMessage:'操作未完成'}),formatDateTime:x=>x,prepareXlsxDownload:data=>{downloads++;return {url:'blob:test',filename:data.filename,rowCount:data.rowCount}}}
  const c=new Function(...Object.keys(scope),script)(...Object.values(scope))
  const vm={...c.data(),ctx:{ctxKey:'test'},$route:{meta:{}}}
  for(const [key,fn] of Object.entries(c.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const [key,fn] of Object.entries(c.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  vm.form={...vm.form,reportType:'WEEKLY',periodKey:'2026-W40',content:row().content}
  return {vm,c,store,switchAccount:()=>generation++,downloads:()=>downloads}
}

test('已保存本人报告默认只读且离页不误报，明确修改才保护输入，取消回到原文',async()=>{
  const {vm}=page();vm.selectReport(teacherReportView(row()))
  const source=fs.readFileSync(new URL('../src/modules/internship/views/MyTeacherReportsView.vue',import.meta.url),'utf8')
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const render=()=>{const descriptors=Object.fromEntries(Object.entries(Object.getOwnPropertyDescriptors(vm)).filter(([key])=>!key.startsWith('$')));return renderToString(createSSRApp({components:{ModulePageShell:{setup:(_,{slots})=>()=>h('main',slots.default?.())},AppButton:{props:['disabled'],setup:(props,{slots})=>()=>h('button',{disabled:props.disabled},slots.default?.())},ErrorState:{render:()=>null},LoadingState:{render:()=>null},FilePreviewer:{render:()=>null}},setup:()=>Object.defineProperties({},descriptors),render:compile(template)}))}
  const frame=fs.readFileSync(new URL('../src/components/workspace/TeacherWorkspaceFrame.vue',import.meta.url),'utf8')
  const body=frame.match(/async function confirmUnsubmitted\(to, from\) \{([\s\S]*?)\n\}\nonBeforeRouteLeave/)[1]
  let html=await render(),confirmations=0
  assert.doesNotMatch(html,/<textarea|<fieldset/)
  const field={readOnly:false,value:vm.form.content,matches:()=>/<fieldset\b[^>]*disabled/.test(html),getClientRects:()=>html.includes('<textarea')?[1]:[]}
  const guard=new Function('document','window','systemConfirm',`return async (to,from)=>{${body}}`)({querySelectorAll:()=>[field]}, {},async()=>{confirmations++;return false})
  assert.equal(await guard({path:'/login'},{path:'/admin/internship/my-reports'}),true)
  assert.equal(confirmations,0);assert.ok(html.includes('修改原报告'))
  vm.editReport();vm.form.content='已修改但尚未保存的正文';field.value=vm.form.content;html=await render()
  assert.equal(await guard({path:'/login'},{path:'/admin/internship/my-reports'}),false)
  assert.equal(confirmations,1)
  vm.cancelEdit();html=await render();field.value=vm.form.content
  assert.equal(vm.form.content,row().content);assert.equal(vm.form.expectedVersion,0)
  assert.equal(await guard({path:'/login'},{path:'/admin/internship/my-reports'}),true)
  assert.equal(confirmations,1)
})

test('已保存本人报告只读方法阻止增删保存，预览下载刷新仍授权，新报告可直接填写',async()=>{
  let writes=0,uploads=0,downloads=0
  const file={fileId:'31',fileName:'已保存.zip',readyForBusiness:true,canDownload:true}
  const api={saveTeacherPeriodReport:async()=>{writes++;return ok(row())}}
  const sdk={metadata:async fileId=>({...file,fileId}),download:async()=>{downloads++},upload:()=>{uploads++;return {promise:Promise.resolve({...file,fileId:'32'})}}}
  const {vm}=page(api,sdk)
  await vm.selectReport(teacherReportView({...row(),attachments:[file]}))
  assert.equal(vm.canEdit,false);await vm.save();vm.removeAttachment('31')
  await vm.uploadAttachments({target:{files:[{name:'新附件.zip'}],value:'chosen'}})
  assert.equal(writes,0);assert.equal(uploads,0);assert.equal(vm.attachments.length,1)
  await vm.preview(file);assert.equal(vm.previewFile.fileId,'31')
  await vm.downloadAttachment(file);await vm.refreshAttachments();assert.equal(downloads,1)
  assert.equal(vm.canEdit,false);assert.equal(vm.form.expectedVersion,0)
  vm.editReport();assert.equal(vm.canEdit,true);vm.removeAttachment('31');assert.equal(vm.attachments.length,0)
  await vm.cancelEdit();assert.equal(vm.canEdit,false);assert.equal(vm.attachments[0].fileId,'31')
  vm.newReport();assert.equal(vm.canEdit,true);assert.equal(vm.selectedId,'');assert.equal(vm.form.expectedVersion,null)
  const readonly=page(api,sdk,false);await readonly.vm.selectReport(teacherReportView(row()))
  readonly.vm.editReport();assert.equal(readonly.vm.canEdit,false);await readonly.vm.save();assert.equal(writes,0)
})

test('本人报告附件未就绪不能保存，刷新安全结果后保留正文和原版本提交',async()=>{
  let sent=0,ready=false
  const p=page({saveTeacherPeriodReport:async()=>{sent++;return ok(row())}}, {metadata:async fileId=>({fileId,readyForBusiness:ready,canDownload:ready,scanStatus:ready?'CLEAN':'PENDING'})})
  p.vm.form.attachments=[{fileId:'21',fileName:'工作材料.zip',readyForBusiness:false,scanStatus:'PENDING'}]
  const content=p.vm.form.content;p.vm.form.expectedVersion=0
  await p.vm.save();assert.equal(sent,0);assert.equal(p.vm.form.content,content);assert.equal(p.vm.form.expectedVersion,0)
  assert.match(p.vm.formError,/安全检查/)
  ready=true;await p.vm.refreshAttachments();assert.equal(p.vm.attachmentsReady,true)
  await p.vm.save();assert.equal(sent,1)
})

test('本人报告压缩包无预览时仍可授权下载，未就绪或无权不能下载',async()=>{
  const calls=[];let ready=true,allowed=true
  const p=page({}, {metadata:async fileId=>({fileId,fileName:'工作材料.zip',readyForBusiness:ready,canPreview:false,canDownload:allowed}),download:async(...args)=>calls.push(args)})
  const file={fileId:'22',fileName:'工作材料.zip'};p.vm.form.attachments=[file]
  await p.vm.downloadAttachment(file);assert.deepEqual(calls,[['22','工作材料.zip']])
  ready=false;await p.vm.downloadAttachment(file);assert.equal(calls.length,1)
  ready=true;allowed=false;await p.vm.downloadAttachment(file);assert.equal(calls.length,1)
})

test('本人报告附件刷新失败及切换报告时不能恢复旧附件可用状态',async()=>{
  const d=deferred();const p=page({}, {metadata:()=>d.promise})
  p.vm.form.attachments=[{fileId:'23',readyForBusiness:true}]
  const pending=p.vm.refreshAttachments();p.vm.reset();p.vm.form.content='新批次正文'
  d.resolve({fileId:'23',readyForBusiness:true});await pending
  assert.deepEqual(p.vm.form.attachments,[]);assert.equal(p.vm.form.content,'新批次正文')
  const failed=page({}, {metadata:async()=>{throw new Error('unavailable')}})
  failed.vm.form.attachments=[{fileId:'24',readyForBusiness:true,scanStatus:'CLEAN'}];await failed.vm.refreshAttachments()
  assert.equal(failed.vm.attachmentsReady,false);assert.ok(failed.vm.formError)
  assert.notEqual(failed.vm.attachmentStatus(failed.vm.attachments[0]),'安全可用')
})

test('本人报告附件真实模板提供下载退路和刷新入口，未就绪禁用保存',async()=>{
  const source=fs.readFileSync(new URL('../src/modules/internship/views/MyTeacherReportsView.vue',import.meta.url),'utf8')
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  for(const ready of [false,true]){
    const {vm}=page();vm.form.attachments=[{fileId:'31',fileName:'工作材料.zip',readyForBusiness:ready,canDownload:ready,canPreview:false}];vm.previewFile=vm.form.attachments[0]
    const descriptors=Object.fromEntries(Object.entries(Object.getOwnPropertyDescriptors(vm)).filter(([key])=>!key.startsWith('$')))
    let allowDownload,downloadHandler
    const components={ModulePageShell:{setup:(_,{slots})=>()=>h('main',slots.default?.())},AppButton:{props:['disabled'],setup:(props,{slots})=>()=>h('button',{disabled:props.disabled},slots.default?.())},ErrorState:{render:()=>null},LoadingState:{render:()=>null},FilePreviewer:{props:['allowDownload','downloadHandler'],setup:props=>{allowDownload=props.allowDownload;downloadHandler=props.downloadHandler;return()=>null}}}
    const html=await renderToString(createSSRApp({components,setup:()=>Object.defineProperties({},descriptors),render:compile(template)}))
    const buttons=[...html.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)]
    const save=buttons.find(([, ,text])=>text.includes('保存本人报告'))
    assert.equal(save[1].includes('disabled'),!ready)
    assert.ok(html.includes('刷新附件安全检查'))
    assert.equal(allowDownload,ready);assert.equal(typeof downloadHandler,'function')
    const download=buttons.find(([, ,text])=>text.includes('下载附件'))
    assert.equal(download[1].includes('disabled'),!ready)
  }
})
test('中文展示保留大编号并转换周次和未知类型',()=>{
  const view=teacherReportView(row());assert.equal(view.id,id);assert.equal(view.typeLabel,'周报');assert.equal(view.periodLabel,'2026年第40周');assert.equal(view.edition,1)
  assert.equal(teacherReportView({...row(),reportType:'SECRET',periodKey:'raw'}).typeLabel,'类型待确认')
  assert.equal(teacherReportView({...row(),periodKey:'raw'}).periodLabel,'周期待核实')
})
test('当前批次最大字数和人数校验阻止不合法提交',()=>{
  assert.ok(reportValidation({...row(),studentCount:''},{weeklyMaxWords:40}))
  assert.ok(reportValidation({...row(),studentCount:-1},{}))
  assert.equal(reportValidation({...row(),studentCount:0},{}),'')
})
test('保存使用原编号版本并成功回读',async()=>{
  let sent;const p=page({saveTeacherPeriodReport:async body=>{sent=body;return ok({...row(),version:1})}})
  p.vm.selectReport(teacherReportView(row()));p.vm.editReport();await p.vm.save();assert.equal(sent.expectedVersion,0);assert.equal(sent.batchId,batch);assert.equal(p.vm.receipt.edition,2);assert.equal(p.vm.saving,false)
})
test('版本冲突保留全部输入和原版本，不自动覆盖',async()=>{
  const p=page({saveTeacherPeriodReport:async()=>({code:1,bizCode:'DATA_CONFLICT'})});p.vm.selectReport(teacherReportView(row()));p.vm.editReport();const content=p.vm.form.content
  await p.vm.save();assert.equal(p.vm.form.content,content);assert.equal(p.vm.form.expectedVersion,0);assert.ok(p.vm.formError.includes('输入已保留'));assert.equal(p.vm.receipt,null)
})
test('重复点击只有一次实际保存请求',async()=>{
  const d=deferred();let requests=0;const p=page({saveTeacherPeriodReport:()=>{requests++;return d.promise}});const pending=p.vm.save();await p.vm.save();assert.equal(requests,1);d.resolve(ok(row()));await pending
})
test('切换批次后旧加载结果不能填入新工作区',async()=>{
  const d=deferred();const p=page({getTeacherPeriodReports:()=>d.promise});const pending=p.vm.load();p.store.selectedBatchId='other';p.vm.reset();d.resolve(ok({items:[row()],total:1}));await pending;assert.deepEqual(p.vm.rows,[])
})
test('切换账号后旧提交回执不能清空新账号输入',async()=>{
  const d=deferred();const p=page({saveTeacherPeriodReport:()=>d.promise});const pending=p.vm.save();p.switchAccount();p.vm.reset();p.vm.form.content='新账号尚未提交的工作记录';d.resolve(ok(row()));await pending;assert.equal(p.vm.form.content,'新账号尚未提交的工作记录');assert.equal(p.vm.receipt,null)
})
test('切换账号后迟到导出结果不能下载',async()=>{
  const d=deferred();const p=page({exportTeacherPeriodReports:()=>d.promise});const pending=p.vm.exportReports();p.switchAccount();d.resolve(ok({}));await pending;assert.equal(p.downloads(),0)
})
test('加载失败明确显示错误，不能伪装空报告',async()=>{
  const p=page({getTeacherPeriodReports:async()=>({code:1,message:'raw error'})});await p.vm.load();assert.equal(p.vm.error,'操作未完成');assert.deepEqual(p.vm.rows,[])
})
test('选择另一份报告后旧附件结果不能覆盖当前预览',async()=>{
  const d=deferred();const p=page({}, {metadata:()=>d.promise});p.vm.selectReport(teacherReportView(row()));const pending=p.vm.preview({fileId:'first'});p.vm.newReport();d.resolve({fileId:'first'});await pending;assert.equal(p.vm.previewFile,null)
})

test('生成报告后保留明确下载入口，切换批次时释放旧快照',async()=>{
  const p=page({exportTeacherPeriodReports:async()=>ok({filename:'教师本人报告.xlsx',rowCount:24})})
  const revoked=[];const original=URL.revokeObjectURL;URL.revokeObjectURL=url=>revoked.push(url)
  try {await p.vm.exportReports();assert.equal(p.vm.exportFile.rowCount,24);assert.equal(p.vm.exportFile.filename,'教师本人报告.xlsx');p.vm.reset();assert.equal(p.vm.exportFile,null);assert.deepEqual(revoked,['blob:test'])}
  finally {URL.revokeObjectURL=original}
})
test('正常重新登录后先重新读取权限与活跃时间再进入受保护页面',async()=>{
  const source=fs.readFileSync(new URL('../src/views/auth/StandaloneLoginView.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const actions=[]
  const component=new Function('loginWithPassword','clearPermissionPatterns','getAuthContext','refreshLastActive','request','getVisibleNavPlan',script)(async()=>{actions.push('login');return {}},()=>actions.push('permissions'),()=>actions.push('identity'),()=>actions.push('activity'),async path=>{assert.equal(path,'/rbac/current-context');actions.push('context');return {}},()=>{actions.push('navigation');return []})
  const vm={...component.data(),$route:{query:{redirect:'/admin/internship/teacher-reports?batchId=1'}},$router:{replace:async path=>actions.push(path)}}
  await component.methods.submit.call(vm)
  assert.deepEqual(actions,['login','permissions','identity','activity','context','navigation','/admin/internship/teacher-reports?batchId=1']);assert.equal(vm.error,'');assert.equal(vm.loading,false)
})
test('退出再登录仍使用电脑30分钟超时策略，不能落入移动7天策略',()=>{
  const source=fs.readFileSync(new URL('../src/security/auth/auth.context.js',import.meta.url),'utf8').replace(/^import[^\n]+\n/gm,'').replace(/export /g,'')
  let user=null
  const auth=new Function('reactive','readonly','SESSION_POLICY','currentUserFromToken','getToken',source+'\nreturn {getAuthContext,clearAuthContext,refreshLastActive,isSessionExpired}')(
    x=>x,x=>x,{PC_TIMEOUT_MS:1800000,MOBILE_TIMEOUT_MS:604800000,MAX_CONCURRENT_SESSIONS:3},()=>user,()=>user?'synthetic-test-token':'')
  auth.clearAuthContext();user={userId:'1',currentRoleCode:'SCHOOL_ADMIN'};auth.getAuthContext();auth.refreshLastActive()
  const context=auth.getAuthContext();assert.equal(context.currentDevice,'pc-web');assert.equal(auth.isSessionExpired(),false)
  const remaining=new Date(context.sessionExpireAt).getTime()-Date.now();assert.ok(remaining>1799000 && remaining<=1800000)
})
