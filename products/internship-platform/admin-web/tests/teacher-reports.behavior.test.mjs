import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import {teacherReportTypes,teacherReportView,reportValidation} from '../src/modules/internship/services/teacherReportPresentation.mjs'
const batch='9007199254740993001',id='9007199254740993002'
const ok=data=>({code:0,data}),row=()=>({id,batchId:batch,reportType:'WEEKLY',periodKey:'2026-W40',content:'合成指导工作。'.repeat(10),version:0,attachments:[]})
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}
function page(api={},sdk={}){
  const source=fs.readFileSync(new URL('../src/modules/internship/views/MyTeacherReportsView.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  let generation=0,downloads=0
  const store={selectedBatchId:batch}
  const scope={ModulePageShell:{},ErrorState:{},LoadingState:{},AppButton:{},FilePreviewer:{},teacherReportTypes,teacherReportView,reportValidation,
    internshipApi:{getTeacherPeriodReports:async()=>ok({items:[row()],total:1,rules:{}}),saveTeacherPeriodReport:async()=>ok(row()),exportTeacherPeriodReports:async()=>ok({}),...api},
    useInternshipBatchStore:()=>store,canCode:()=>true,fileSdk:{metadata:async fileId=>({fileId}),...sdk},currentSessionGeneration:()=>generation,
    normalizeUiError:()=>({userMessage:'操作未完成'}),formatDateTime:x=>x,prepareXlsxDownload:data=>{downloads++;return {url:'blob:test',filename:data.filename,rowCount:data.rowCount}}}
  const c=new Function(...Object.keys(scope),script)(...Object.values(scope))
  const vm={...c.data(),ctx:{ctxKey:'test'},$route:{meta:{}}}
  for(const [key,fn] of Object.entries(c.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const [key,fn] of Object.entries(c.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  vm.form={...vm.form,reportType:'WEEKLY',periodKey:'2026-W40',content:row().content}
  return {vm,c,store,switchAccount:()=>generation++,downloads:()=>downloads}
}
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
  p.vm.selectReport(teacherReportView(row()));await p.vm.save();assert.equal(sent.expectedVersion,0);assert.equal(sent.batchId,batch);assert.equal(p.vm.receipt.edition,2);assert.equal(p.vm.saving,false)
})
test('版本冲突保留全部输入和原版本，不自动覆盖',async()=>{
  const p=page({saveTeacherPeriodReport:async()=>({code:1,bizCode:'DATA_CONFLICT'})});p.vm.selectReport(teacherReportView(row()));const content=p.vm.form.content
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
  const component=new Function('loginWithPassword','clearPermissionPatterns','getAuthContext','refreshLastActive',script)(async()=>actions.push('login'),()=>actions.push('permissions'),()=>actions.push('identity'),()=>actions.push('activity'))
  const vm={...component.data(),$route:{query:{redirect:'/admin/internship/teacher-reports?batchId=1'}},$router:{replace:async path=>actions.push(path)}}
  await component.methods.submit.call(vm)
  assert.deepEqual(actions,['login','permissions','identity','activity','/admin/internship/teacher-reports?batchId=1']);assert.equal(vm.error,'');assert.equal(vm.loading,false)
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
