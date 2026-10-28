import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { INTERNSHIP_TABS as tabs } from '../src/platform/internshipNavigation.js'

const ctx = { hasData:true, batchId:'9007199254741001', recordId:'9007199254741002', status:'ONBOARD' }
const returned = { id:'9007199254741003', internshipId:ctx.recordId, batchId:ctx.batchId,
  week:1, version:2, reportVersion:1, status:'RETURNED', workContent:'原岗位工作记录'.repeat(5),
  harvestContent:'原收获体会', planContent:'原下周计划', attachments:[], reviewComment:'请补充具体成果' }
const deferred = () => { let resolve,reject; const promise = new Promise((a,b) => {resolve=a;reject=b}); return {promise,resolve,reject} }

async function actualUploadError(payload) {
  const source=fs.readFileSync(new URL('../src/services/request.js',import.meta.url),'utf8')
  const body=source.slice(source.indexOf('export async function uploadFile('),source.indexOf('export async function fetchFileBlob(')).replace('export async function','return async function')
  const deps={cleanupStaleGraduationTemps(){},sessionGeneration:1,getToken:()=>'',addInternshipBatchHeader(){},FormData:class{append(){}},fetch:async()=>({status:400}),API_BASE:'',API_PREFIX:'/api/v1',responseJson:async()=>payload,isUnauthorized:()=>false}
  const upload=new Function(...Object.keys(deps),body)(...Object.values(deps))
  try {await upload('/files?bizType=INTERNSHIP_REPORT',{name:'安全拒绝样本.zip'});assert.fail('必须保留上传拒绝')} catch(error){return error}
}

test('报告上传实际错误适配保留拒绝码，中文提示同时保留正文和原附件',async t=>{
  const payload={code:1,bizCode:'FILE_ZIP_REJECTED',message:'ZIP 含路径穿越，已拒绝'}
  const error=await actualUploadError(payload)
  assert.equal(error.code,1);assert.equal(error.bizCode,payload.bizCode);assert.equal(error.biz,true)
  assert.equal(error.message,payload.message)
  for(const target of ['weekly','process']){
    const {vm,notices}=page(t,{fileSdk:{upload:async()=>{throw error}}})
    const form=target==='weekly'?vm.weeklyForm:vm.reportForm
    const original=target==='weekly'?form.workContent:'已经填写的月报正文';if(target==='process')form.content=original
    form.attachments=[{fileId:'existing',fileName:'原有材料.doc'}]
    const input={files:[{name:'不安全压缩包.zip'}],value:'chosen'}
    await vm.uploadReportAttachment({target:input},target)
    assert.equal(target==='weekly'?form.workContent:form.content,original)
    assert.deepEqual(form.attachments,[{fileId:'existing',fileName:'原有材料.doc'}])
    assert.match(vm.reportError.value,/压缩包.*安全检查.*已拒绝/);assert.doesNotMatch(vm.reportError.value,/ZIP|FILE_ZIP_REJECTED|路径穿越/)
    assert.equal(notices.at(-1),vm.reportError.value);assert.equal(input.value,'')
  }
})

test('报告上传其他业务拒绝保留原说明，不误套压缩包提示',async t=>{
  const error=await actualUploadError({code:1,bizCode:'FILE_SIZE_EXCEEDED',message:'文件超过允许大小'})
  const {vm}=page(t,{fileSdk:{upload:async()=>{throw error}}})
  await vm.uploadReportAttachment({target:{files:[{name:'过大文件.doc'}]}},'weekly')
  assert.equal(vm.reportError.value,'文件超过允许大小');assert.deepEqual(vm.weeklyForm.attachments,[])
})

test('报告状态保留已有中文映射，未知或缺失状态只显示中文说明',t=>{
  const {vm}=page(t)
  assert.equal(vm.reviewText('PENDING_REVIEW'),'待审阅')
  assert.equal(vm.reviewText('APPROVED'),'已通过')
  assert.equal(vm.reviewText('RETURNED'),'已退回')
  assert.equal(vm.reviewText('UNKNOWN_INTERNAL_STATE'),'状态待核实')
  assert.equal(vm.reviewText(null),'状态待核实')
})

test('report paging uses server totals and retains earlier rows and drafts',async t=>{
  const reads=[],first=Array.from({length:20},(_,i)=>({id:String(i+1),internshipId:ctx.recordId,reportType:'DAILY'}))
  const {vm}=page(t,{reports:async(context,page,size,kind)=>{
    reads.push({page,size,kind})
    return {items:kind==='DAILY'?(page===1?first:[{...first[0],id:'21'}]):[],page,total:kind==='DAILY'?21:0,hasMore:kind==='DAILY'&&page===1}
  }})
  vm.reportForm.content='尚未提交的日报'
  await vm.fetchTabSource('report')
  assert.equal(vm.my.value.processReports.length,20)
  assert.equal(vm.reportProgress.value.find(row=>row.key==='daily').submitted,21)
  await vm.loadMoreReports('DAILY')
  assert.equal(vm.my.value.processReports.length,21)
  assert.equal(vm.reportPages.DAILY.hasMore,false)
  assert.equal(vm.reportForm.content,'尚未提交的日报')
  assert.deepEqual(reads.at(-1),{page:2,size:20,kind:'DAILY'})
})

test('failed later page preserves rows, page and draft so it can be retried',async t=>{
  const {vm}=page(t,{weeklyReports:async()=>{throw Error('读取失败')}})
  vm.my.value.weeklyReports=[returned];vm.reportPages.WEEKLY={page:1,total:21,hasMore:true}
  const draft=vm.weeklyForm.workContent
  await vm.loadMoreReports('WEEKLY')
  assert.deepEqual(vm.my.value.weeklyReports,[returned]);assert.equal(vm.weeklyForm.workContent,draft)
  assert.equal(vm.reportPages.WEEKLY.page,1);assert.equal(vm.reportPages.WEEKLY.hasMore,true)
  assert.equal(vm.reportMoreBusy.value,false);assert.match(vm.reportError.value,/读取失败/)
})

test('late later page cannot append old account rows or release a new read',async t=>{
  const wait=deferred(),{vm,logout}=page(t,{weeklyReports:()=>wait.promise})
  vm.reportPages.WEEKLY={page:1,total:21,hasMore:true}
  const pending=vm.loadMoreReports('WEEKLY')
  logout();vm.resetSourceStates();vm.my.value={...ctx,batchId:'new',recordId:'new-record',weeklyReports:[]}
  vm.reportMoreBusy.value=true
  wait.resolve({items:[returned],page:2,total:21,hasMore:false});await pending
  assert.deepEqual(vm.my.value.weeklyReports,[]);assert.equal(vm.reportMoreBusy.value,true)
  assert.equal(vm.reportPages.WEEKLY.total,null)
})

function page(t, overrides={}) {
  const { fileSdk={}, document, fetchFileBlob=async()=>null, Date: clock=Date,
    cache={getItem:()=>null,setItem(){},removeItem(){}}, sessionUser={tenantId:'11',userId:'18',roleCode:'STUDENT'},
    portalApi:portalOverrides={}, route=reactive({query:{}}), router={replace(){},push(){}}, ...apiOverrides } = overrides
  let generation=1
  const session=reactive({user:sessionUser})
  const scope=effectScope(), calls=[], lifecycle={}, notices=[]
  const api={
    agreements:async()=>[],insurance:async()=>null,plans:async()=>[],attendance:async()=>({items:[],summary:{}}),
    weeklyReports:async()=>({items:[],rules:{weeklyMinWords:30}}), reports:async()=>({items:[]}),
    weeklyReportDetail:async()=>({...returned,immutableVersions:[]}),
    submitWeeklyReport:async body=>{calls.push(body);return {id:returned.id,version:3,reportVersion:2,status:'PENDING_REVIEW'}},...apiOverrides
  }
  const deps={Date:clock,tabs,computed,reactive,ref,watch,onMounted:fn=>{lifecycle.mount=fn},onBeforeUnmount:fn=>{lifecycle.unmount=fn},
    useUiStore:()=>({notify:v=>notices.push(v)}),useSessionStore:()=>session,sessionStorage:cache,
    useRoute:()=>route,useRouter:()=>router,currentSessionGeneration:()=>generation,
    portalApi:{internshipMy:async()=>({...ctx}),...portalOverrides},document,fetchFileBlob,fileSdk,scanState:row=>row,scanFilesReady:()=>true,refreshScanFiles(){},systemPrompt(){},systemConfirm(){},internshipCoreApi:api}
  const script=parse(fs.readFileSync(new URL('../src/views/internship/InternshipView.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'')
  const names=['my','tab','busy','sourceStates','weeklyForm','weeklyCanSubmit','reportReceipt','reportError','editWeekly','submitWeekly','resetSourceStates','fetchTabSource','loadTab','uploadReportAttachment','reportVisibilityChanged','reportForm','processConflict','editProcessReport','submitReport','rereadProcessReport','continueProcessAfterConflict','rereadWeeklyAfterConflict','switchReportTab','reportTab','weeklyReading','processReading','reportRules']
  const optional=['reportReadMode','processExisting','reportMinimum','reportCanSubmit','returnToReportDraft','focusReportFromRoute','weeklyConflict','weeklyDetail','openWeekly','continueWeeklyAfterConflict','processDetail','openProcessReport','reportPages','reportMoreBusy','reportProgress','loadMoreReports','load','loading','weeklyBase','processBase','reviewText']
  const vm=scope.run(()=>new Function(...Object.keys(deps),script+'\nreturn {'+names.join(',')+','+optional.map(n=>`${n}:typeof ${n} === "undefined" ? undefined : ${n}`).join(',')+'}')(...Object.values(deps)))
  let closed=false
  const close=()=>{if(!closed){closed=true;lifecycle.unmount?.();scope.stop()}}
  t.after(close)
  vm.my.value={...ctx,weeklyReports:[]};vm.tab.value='report';vm.sourceStates.report.status='data'
  Object.assign(vm.weeklyForm,{week:1,workContent:'本周完成具体岗位任务与成果记录'.repeat(3),harvestContent:'学习安全工作流程',planContent:''})
  return {vm,calls,notices,session,close,logout:()=>generation++}
}

function draftCache() {
  const values=new Map()
  return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)}
}
test('退出后的过渡组件不读取实习或把旧地址批次写回缓存',async t=>{
  const cache=draftCache();let reads=0
  const {vm}=page(t,{cache,sessionUser:null,route:reactive({query:{view:'report',batchId:'old-batch'}}),portalApi:{internshipMy:async()=>{reads++;return {...ctx}}}})
  await vm.load();assert.equal(reads,0);assert.equal(cache.getItem('student_portal_internship_batch_v1'),null);assert.equal(vm.my.value.hasData,undefined)
})
test('同一深链返回后可重开，改变类型必须重新校验，退回原单沿原编号版本编辑',async t=>{
  const route=reactive({query:{reportId:'99',reportType:'DAILY'}}),row={id:'99',batchId:ctx.batchId,internshipId:ctx.recordId,reportType:'DAILY',periodKey:'2026-10-01',content:'旧日报补正内容',status:'RETURNED',version:5},reads=[]
  const p=page(t,{route,processReportDetail:async()=>{reads.push(1);return row}});p.vm.loading.value=false;p.vm.focusReportFromRoute();await nextTick();await nextTick();p.vm.returnToReportDraft();p.vm.focusReportFromRoute();await nextTick();await nextTick()
  assert.equal(reads.length,2);assert.equal(p.vm.reportReadMode.value,true);p.vm.editProcessReport(p.vm.processDetail.value);assert.equal(p.vm.processBase.value.id,'99');assert.equal(p.vm.processBase.value.version,5)
  route.query={reportId:'99',reportType:'MONTHLY'};await nextTick();await nextTick();assert.match(p.vm.reportError.value,/类型/);assert.equal(p.vm.processDetail.value,null)
})
test('返回填写或移除原单深链后，迟到正文不能抢回阅读模式或链接',async t=>{
  for(const exit of ['return','clear','invalid']){
    const route=reactive({query:{view:'report',reportId:'2',reportType:'DAILY'}}),wait=deferred(),router={replace:async({query})=>{route.query=query},push(){}}
    const {vm}=page(t,{route,router,processReportDetail:()=>wait.promise});vm.loading.value=false;vm.focusReportFromRoute();await nextTick()
    if(exit==='return')vm.returnToReportDraft();else route.query=exit==='clear'?{view:'report'}:{view:'report',reportId:'2',reportType:'INVALID'}
    await nextTick();wait.resolve({id:'2',batchId:ctx.batchId,internshipId:ctx.recordId,reportType:'DAILY',content:'迟到原文'});await nextTick();await nextTick()
    assert.equal(vm.reportReadMode.value,false);assert.equal(vm.processDetail.value,null);assert.notEqual(route.query.reportType,'DAILY')
  }
})
test('真实路由同步非周报深链，请求中换原单不会被旧响应抢回',async t=>{
  const route=reactive({query:{view:'report',batchId:ctx.batchId,reportType:'DAILY',reportId:'1'}}),reads=[],first=deferred(),second=deferred()
  const router={replace:async({query})=>{route.query=query},push(){}}
  const row=id=>({id,batchId:ctx.batchId,internshipId:ctx.recordId,reportType:'DAILY',content:'第'+id+'份正文'})
  const {vm}=page(t,{route,router,processReportDetail:async(_ctx,id)=>{reads.push(id);return id==='1'?first.promise:second.promise}})
  vm.loading.value=false;vm.focusReportFromRoute();await nextTick();assert.equal(route.query.reportId,'1')
  route.query={...route.query,reportId:'2'};await nextTick();assert.deepEqual(reads,['1','2'])
  second.resolve(row('2'));await nextTick();await nextTick();assert.equal(vm.processDetail.value.id,'2')
  first.resolve(row('1'));await nextTick();await nextTick();assert.equal(vm.processDetail.value.id,'2');assert.equal(route.query.reportId,'2')
  vm.returnToReportDraft();await nextTick();assert.equal(route.query.reportId,undefined);assert.equal(vm.reportReadMode.value,false)
})

test('阅读原单和返回填写保留草稿正文、附件及原版本',async t=>{
  const {vm}=page(t);vm.editWeekly(returned);vm.weeklyForm.workContent='我的未保存补正';vm.weeklyForm.attachments=[{fileId:'held'}];vm.reportReceipt.value={statusLabel:'待批阅'}
  await vm.openWeekly(returned);assert.equal(vm.reportReadMode.value,true)
  assert.equal(vm.reportReceipt.value,null)
  vm.returnToReportDraft();assert.equal(vm.reportReadMode.value,false);assert.equal(vm.weeklyForm.workContent,'我的未保存补正');assert.equal(vm.weeklyBase.value.version,2);assert.equal(vm.weeklyForm.attachments[0].fileId,'held')
})
test('日报月报总结分别保留本人输入和附件，不串入其他类别，刷新仍恢复',async t=>{
  const cache=draftCache(),p=page(t,{cache});await p.vm.load();p.vm.switchReportTab('日报');p.vm.reportForm.content='未提交日报';p.vm.reportForm.attachments=[{fileId:'day'}]
  p.vm.switchReportTab('月报');assert.equal(p.vm.reportForm.content,'');p.vm.reportForm.content='未提交月报'
  p.vm.switchReportTab('实习总结');assert.equal(p.vm.reportForm.content,'');p.vm.reportForm.content='未提交总结'
  p.vm.switchReportTab('日报');assert.equal(p.vm.reportForm.content,'未提交日报');assert.equal(p.vm.reportForm.attachments[0].fileId,'day');await nextTick();p.close()
  const restored=page(t,{cache});await restored.vm.load();assert.equal(restored.vm.reportForm.content,'未提交日报');restored.vm.switchReportTab('月报');assert.equal(restored.vm.reportForm.content,'未提交月报');restored.vm.switchReportTab('实习总结');assert.equal(restored.vm.reportForm.content,'未提交总结')
})
test('过程报告显式零字数和已有周期采用真实规则，空正文仍不得提交',t=>{
  const {vm}=page(t);vm.switchReportTab('日报');vm.reportRules.value={dailyMinWords:0};vm.reportForm.content='字'
  assert.equal(vm.reportMinimum.value,0);assert.equal(vm.reportCanSubmit.value,true)
  vm.my.value.processReports=[{id:'old',reportType:'DAILY',periodKey:vm.reportForm.periodKey,status:'APPROVED'}];assert.equal(vm.processExisting.value.id,'old');assert.equal(vm.reportCanSubmit.value,false)
  vm.my.value.processReports=[];vm.reportForm.content=' ';assert.equal(vm.reportCanSubmit.value,false)
})
test('原单深链打开第一页之外的精确正文，保留本人草稿并拒绝错类型批次',async t=>{
  const route=reactive({query:{view:'report',batchId:ctx.batchId,reportType:'DAILY',reportId:'999'}}),reads=[]
  const row={id:'999',batchId:ctx.batchId,internshipId:ctx.recordId,reportType:'DAILY',periodKey:'2026-10-01',content:'精确原单全文',status:'APPROVED'}
  const {vm}=page(t,{route,processReportDetail:async(_ctx,id)=>{reads.push(id);return row}});vm.loading.value=false;vm.reportForm.content='本人月报草稿';vm.focusReportFromRoute();await nextTick();await nextTick()
  assert.deepEqual(reads,['999']);assert.equal(vm.processDetail.value.content,'精确原单全文');assert.equal(vm.reportReadMode.value,true)
  vm.returnToReportDraft();vm.switchReportTab('月报');assert.equal(vm.reportForm.content,'本人月报草稿')
  const bad=page(t,{processReportDetail:async()=>({...row,reportType:'MONTHLY'})});bad.vm.switchReportTab('日报');await bad.vm.openProcessReport({id:'999'});assert.equal(bad.vm.processDetail.value,null);assert.match(bad.vm.reportError.value,/类型/)
  for(const query of [{reportType:'INTERNAL',reportId:'999'},{reportType:'DAILY',reportId:'0'},{reportType:'DAILY',reportId:'999',batchId:'other'}]){const p=page(t,{route:reactive({query}),processReportDetail:async()=>{assert.fail('无效链接不得读取')}});p.vm.loading.value=false;p.vm.focusReportFromRoute();assert.ok(p.vm.reportError.value)}
})
const draftKey='student_portal_report_draft_v1'

test('报告输入及附件即时保留，整体刷新仍恢复原稿',async t=>{
  const cache=draftCache(),{vm}=page(t,{cache});await vm.load()
  vm.weeklyForm.workContent='刷新前尚未提交的正文';vm.weeklyForm.attachments=[{fileId:'9007199254741019',name:'合成附件.pdf'}]
  await nextTick();assert.equal(JSON.parse(cache.getItem(draftKey)).weeklyForm.workContent,'刷新前尚未提交的正文')
  await vm.load();assert.equal(vm.weeklyForm.workContent,'刷新前尚未提交的正文')
  assert.equal(vm.weeklyForm.attachments[0].fileId,'9007199254741019')
})

test('整页重进保留旧读取版本，显式核对后才允许采用新版',async t=>{
  const cache=draftCache(),first=page(t,{cache});await first.vm.load();first.vm.editWeekly(returned)
  first.vm.weeklyForm.workContent='原稿补充成果';first.vm.weeklyForm.attachments=[{fileId:'76'}]
  await nextTick();first.close()
  const latest={...returned,version:6},second=page(t,{cache,weeklyReports:async()=>({items:[latest]}),weeklyReportDetail:async()=>latest})
  await second.vm.load();assert.equal(second.vm.weeklyForm.workContent,'原稿补充成果')
  assert.equal(second.vm.weeklyForm.attachments[0].fileId,'76');assert.equal(second.vm.weeklyBase.value.version,2)
  assert.equal(second.vm.weeklyConflict.value,true)
  await second.vm.rereadWeeklyAfterConflict();assert.equal(second.vm.weeklyBase.value.version,2)
  second.vm.continueWeeklyAfterConflict();assert.equal(second.vm.weeklyBase.value.version,6)
})

test('相同业务编号下切换学校、账号或角色不会恢复旧身份草稿',async t=>{
  for(const sessionUser of [{tenantId:'12',userId:'18',roleCode:'STUDENT'},{tenantId:'11',userId:'19',roleCode:'STUDENT'},{tenantId:'11',userId:'18',roleCode:'OTHER'}]){
    const cache=draftCache(),first=page(t,{cache});await first.vm.load();first.vm.weeklyForm.workContent='旧身份保留正文';await nextTick();first.close()
    const saved=cache.getItem(draftKey),second=page(t,{cache,sessionUser});await second.vm.load()
    assert.equal(second.vm.weeklyForm.workContent,'');assert.equal(second.vm.weeklyBase.value,null)
    assert.equal(cache.getItem(draftKey),saved)
  }
})

test('请求层清除会话后，迟到输入及页面卸载不重建旧草稿',async t=>{
  const cache=draftCache(),{vm,logout,close}=page(t,{cache});await vm.load()
  vm.weeklyForm.workContent='需清除的旧身份草稿';await nextTick();assert.ok(cache.getItem(draftKey))
  cache.removeItem(draftKey);logout();vm.weeklyForm.workContent='旧页面迟到输入';await nextTick();close()
  assert.equal(cache.getItem(draftKey),null)
})

test('中国时区凌晨与月年交界的日报默认日期采用设备当天',t=>{
  const oldTimezone=process.env.TZ
  process.env.TZ='Asia/Shanghai'
  try {
    for(const [instant,expected] of [
      ['2026-10-06T17:00:00Z','2026-10-07'],['2026-10-06T23:59:00Z','2026-10-07'],
      ['2026-10-07T00:00:00Z','2026-10-07'],['2026-10-31T17:00:00Z','2026-11-01'],
      ['2026-12-31T17:00:00Z','2027-01-01']
    ]) {
      class FixedDate extends Date { constructor(...args){super(...(args.length?args:[instant]))} }
      const {vm}=page(t,{Date:FixedDate});vm.switchReportTab('日报')
      assert.equal(vm.reportForm.periodKey,expected)
    }
  } finally { if(oldTimezone===undefined)delete process.env.TZ;else process.env.TZ=oldTimezone }
})

test('a school weekly minimum of zero accepts short work and harvest but still requires both',async t=>{
  const {vm,calls}=page(t)
  vm.reportRules.value.weeklyMinWords=0
  vm.weeklyForm.workContent='岗';vm.weeklyForm.harvestContent=' '
  await vm.submitWeekly();assert.equal(calls.length,0)
  vm.weeklyForm.harvestContent='学';vm.weeklyForm.planContent=''
  await vm.submitWeekly();assert.equal(calls.length,1)
  assert.equal(calls[0].workContent,'岗');assert.equal(calls[0].harvestContent,'学')
})

test('switching report type clears opened details and ignores late details without losing drafts',async t=>{
  const weeklyWait=deferred(),processWait=deferred()
  const {vm}=page(t,{weeklyReportDetail:()=>weeklyWait.promise,processReportDetail:()=>processWait.promise})
  const summary={...returned,id:'summary',reportType:'SUMMARY',content:'旧总结正文'}
  vm.weeklyDetail.value=returned;vm.processDetail.value=summary
  vm.reportForm.content='尚未提交的报告草稿'
  const weeklyDraft=vm.weeklyForm.workContent
  vm.switchReportTab('日报')
  assert.equal(vm.weeklyDetail.value,null);assert.equal(vm.processDetail.value,null)
  const weeklyRead=vm.openWeekly(returned),processRead=vm.openProcessReport(summary)
  vm.switchReportTab('月报')
  assert.equal(vm.weeklyReading.value,false);assert.equal(vm.processReading.value,false)
  weeklyWait.resolve(returned);processWait.resolve(summary)
  await Promise.all([weeklyRead,processRead])
  assert.equal(vm.weeklyDetail.value,null);assert.equal(vm.processDetail.value,null)
  assert.equal(vm.weeklyForm.workContent,weeklyDraft);assert.equal(vm.reportForm.content,'尚未提交的报告草稿')
})

test('switching batch clears the old report draft and receipt',t=>{
  const {vm}=page(t);vm.reportReceipt.value={id:'old'};vm.reportError.value='old error'
  vm.resetSourceStates();vm.my.value={...ctx,batchId:'new',recordId:'new-record'}
  assert.equal(vm.weeklyForm.week,null);assert.equal(vm.weeklyForm.workContent,'')
  assert.equal(vm.weeklyForm.harvestContent,'');assert.equal(vm.reportReceipt.value,null);assert.equal(vm.reportError.value,'')
  assert.equal(vm.weeklyCanSubmit.value,false)
})

test('the actual list row without a batch field still edits its own captured version',async t=>{
  const {vm,calls}=page(t), row={...returned};delete row.batchId
  vm.my.value.weeklyReports=[row];vm.editWeekly(row);await vm.submitWeekly()
  assert.equal(calls[0].expectedVersion,2);assert.equal(calls[0].batchId,ctx.batchId)
})

test('overview preloading retains the actual report and school rules before entering the report area',async t=>{
  let reads=0;const {vm}=page(t,{weeklyReports:async()=>{reads++;return {items:[returned],rules:{weeklyMinWords:80}}}})
  vm.tab.value='overview';await nextTick();await vm.loadTab('report',true)
  assert.equal(vm.my.value.weeklyReports[0].id,returned.id);assert.equal(vm.sourceStates.report.status,'data')
  vm.tab.value='report';await nextTick();await vm.loadTab('report')
  assert.equal(reads,1);assert.equal(vm.my.value.weeklyReports[0].id,returned.id)
})

test('first-submit conflict locates the returned same-week original and keeps the unsent text',async t=>{
  let visible=false,count=0;const calls=[]
  const {vm}=page(t,{weeklyReports:async()=>({items:visible?[returned]:[]}),
    submitWeeklyReport:async body=>{calls.push(body);if(!count++){visible=true;throw {status:409}}return {...returned,version:3,status:'PENDING_REVIEW'}}})
  const draft=vm.weeklyForm.workContent;await vm.submitWeekly();await vm.rereadWeeklyAfterConflict()
  assert.equal(vm.weeklyConflict.value,true);assert.equal(vm.weeklyForm.workContent,draft)
  vm.continueWeeklyAfterConflict();await vm.submitWeekly();assert.deepEqual(calls.map(row=>row.expectedVersion),[0,2])
})

test('late upload does not bind an old file or release the current operation',async t=>{
  const wait=deferred(),{vm,logout}=page(t,{fileSdk:{upload:()=>wait.promise}})
  const pending=vm.uploadReportAttachment({target:{files:[{name:'合成.png'}]}},'weekly')
  logout();vm.resetSourceStates();vm.my.value={...ctx,batchId:'other',recordId:'other-record'};vm.busy.value=true
  wait.resolve({fileId:'old',readyForBusiness:true});await pending
  assert.deepEqual(vm.weeklyForm.attachments,[]);assert.equal(vm.busy.value,true)
})

test('hidden report and overlapping detail responses cannot expose an old body',async t=>{
  const first=deferred(),second=deferred(),document={hidden:false},reads=[]
  const {vm}=page(t,{document,weeklyReportDetail:()=>{const d=reads.length?second:first;reads.push(d);return d.promise}})
  const a=vm.openWeekly(returned),b=vm.openWeekly({...returned,id:'other'})
  first.resolve({...returned});await a;assert.equal(vm.weeklyDetail.value,null)
  second.resolve({...returned,id:'other',workContent:'当前正文'});await b
  assert.equal(vm.weeklyDetail.value.workContent,'当前正文')
  const late=deferred(),hidden=page(t,{document,weeklyReportDetail:()=>late.promise})
  const pending=hidden.vm.openWeekly(returned);document.hidden=true;hidden.vm.reportVisibilityChanged()
  late.resolve({...returned});await pending;assert.equal(hidden.vm.weeklyDetail.value,null)
})

test('an oversized field keeps the original text and sends no command',async t=>{
  const {vm,calls}=page(t);vm.weeklyForm.workContent='字'.repeat(2001)
  await vm.submitWeekly();assert.equal(calls.length,0);assert.equal(vm.weeklyForm.workContent.length,2001)
})

test('the sibling period report keeps the opened version and requires explicit conflict adoption',async t=>{
  const row={id:'period',batchId:ctx.batchId,internshipId:ctx.recordId,reportType:'MONTHLY',periodKey:'2026-10',version:2,status:'RETURNED',content:'原月报正文'.repeat(25)}
  let latest={...row},count=0;const calls=[]
  const {vm}=page(t,{reports:async(_ctx,_page,_size,type)=>({items:type==='MONTHLY'?[latest]:[]}),processReportDetail:async()=>latest,
    submitReport:async body=>{calls.push(body);if(!count++)throw {status:409};return {...row,version:7,status:'PENDING_REVIEW'}}})
  vm.my.value.processReports=[row];vm.editProcessReport(row);vm.reportForm.content='保留补正月报正文'.repeat(25)
  vm.my.value.processReports=[{...row,version:6}]
  await vm.submitReport();assert.equal(calls[0].expectedVersion,2)
  await vm.submitReport();assert.equal(calls.length,1)
  latest={...row,version:6};await vm.rereadProcessReport();assert.equal(vm.processConflict.value,true)
  assert.equal(vm.reportForm.content,'保留补正月报正文'.repeat(25))
  vm.continueProcessAfterConflict();await vm.submitReport();assert.equal(calls[1].expectedVersion,6)
})

test('conflict preserves draft and prevents the same stale request from being sent twice',async t=>{
  let count=0
  const {vm}=page(t,{submitWeeklyReport:async()=>{count++;throw {bizCode:'DATA_CONFLICT',status:409}}})
  vm.my.value.weeklyReports=[returned];vm.editWeekly(returned);const original=vm.weeklyForm.workContent
  await vm.submitWeekly();await vm.submitWeekly()
  assert.equal(count,1);assert.equal(vm.weeklyForm.workContent,original);assert.equal(vm.weeklyConflict.value,true)
})

test('returned text uses its captured version even if the list has since refreshed',async t=>{
  const {vm,calls}=page(t);vm.my.value.weeklyReports=[returned];vm.editWeekly(returned)
  vm.my.value.weeklyReports=[{...returned,version:6}]
  await vm.submitWeekly();assert.equal(calls[0].expectedVersion,2)
})

test('late success after account and batch switch cannot clear new input or set a receipt',async t=>{
  const wait=deferred();const {vm,logout}=page(t,{submitWeeklyReport:()=>wait.promise})
  const pending=vm.submitWeekly();logout();vm.resetSourceStates()
  vm.my.value={...ctx,batchId:'other',recordId:'other-record'};vm.sourceStates.report.status='data'
  vm.weeklyForm.workContent='新批次未提交草稿';vm.busy.value=true
  wait.resolve({id:'old',version:1,reportVersion:1,status:'PENDING_REVIEW'});await pending
  assert.equal(vm.weeklyForm.workContent,'新批次未提交草稿');assert.equal(vm.reportReceipt.value,null);assert.equal(vm.busy.value,true)
})

test('report list arriving from an old context never replaces the new context list',async t=>{
  const wait=deferred();const {vm}=page(t,{weeklyReports:()=>wait.promise})
  const pending=vm.fetchTabSource('report');vm.resetSourceStates()
  vm.my.value={...ctx,batchId:'other',recordId:'other-record',weeklyReports:[]}
  wait.resolve({items:[returned]});await pending
  assert.deepEqual(vm.my.value.weeklyReports,[])
})

for (const oldFails of [false,true]) test(`an older report read ${oldFails?'failure':'success'} cannot overwrite the newest successful source state`,async t=>{
  const old=deferred(),newest=deferred();let reads=0
  const {vm}=page(t,{weeklyReports:()=>++reads===1?old.promise:newest.promise})
  const a=vm.loadTab('report',true),b=vm.loadTab('report',true)
  newest.resolve({items:[returned]});await b
  if(oldFails)old.reject(Error('旧请求网络故障'));else old.resolve({items:[]})
  await a
  assert.equal(vm.sourceStates.report.status,'data');assert.equal(vm.sourceStates.report.message,'')
  assert.equal(vm.my.value.weeklyReports[0].id,returned.id)
})

test('confirmed command with failed readback stays submitted and cannot be resubmitted',async t=>{
  const {vm,calls}=page(t,{weeklyReports:async()=>{throw Error('读取失败')}})
  await vm.submitWeekly();assert.equal(vm.reportReceipt.value.id,returned.id)
  assert.match(vm.reportReceipt.value.nextStep,/已提交|回读/);assert.equal(vm.sourceStates.report.status,'error')
  await vm.submitWeekly();assert.equal(calls.length,1)
})

test('own detail exposes immutable versions and rejects a response from another record',async t=>{
  const versions=[{versionNo:2,content:{workContent:'新正文'},review:{action:'APPROVE',ratingLevel:4}},
    {versionNo:1,content:{workContent:'旧正文'},review:{action:'RETURN',comment:'原退回意见'}}]
  const {vm}=page(t,{weeklyReportDetail:async()=>({...returned,immutableVersions:versions})})
  await vm.openWeekly(returned);assert.deepEqual(vm.weeklyDetail.value.immutableVersions,versions)
  const other=page(t,{weeklyReportDetail:async()=>({...returned,internshipId:'other'})})
  await other.vm.openWeekly(returned);assert.equal(other.vm.weeklyDetail.value,null)
})

test('reloading a conflicted report preserves input until the student explicitly adopts the read version',async t=>{
  let count=0
  const {vm,calls}=page(t,{submitWeeklyReport:async body=>{calls.push(body);if(!count++)throw {status:409};return {id:returned.id,version:7,reportVersion:3,status:'PENDING_REVIEW'}},
    weeklyReportDetail:async()=>({...returned,version:6})})
  vm.my.value.weeklyReports=[returned];vm.editWeekly(returned);vm.weeklyForm.workContent='保留补正正文'.repeat(8)
  await vm.submitWeekly();await vm.openWeekly(returned);assert.equal(vm.weeklyConflict.value,true)
  assert.equal(vm.weeklyForm.workContent,'保留补正正文'.repeat(8))
  vm.continueWeeklyAfterConflict();await vm.submitWeekly();assert.equal(calls[1].expectedVersion,6)
  await nextTick()
})

test('process original shows percent zero and immutable versions but rejects another record or late account',async t=>{
  const row={id:'period',batchId:ctx.batchId,internshipId:ctx.recordId,reportType:'SUMMARY',periodKey:'FINAL',version:4,status:'APPROVED',review:{summaryScore:0},
    immutableVersions:[{versionNo:2,content:'新总结',review:{summaryScore:0}},{versionNo:1,content:'原总结',review:{action:'RETURN'}}]}
  const p=page(t,{processReportDetail:async()=>row});await p.vm.openProcessReport(row)
  assert.equal(p.vm.processDetail.value.review.summaryScore,0);assert.deepEqual(p.vm.processDetail.value.immutableVersions,row.immutableVersions)
  const other=page(t,{processReportDetail:async()=>({...row,internshipId:'other'})});await other.vm.openProcessReport(row);assert.equal(other.vm.processDetail.value,null)
  const wait=deferred(),late=page(t,{processReportDetail:()=>wait.promise}),pending=late.vm.openProcessReport(row)
  late.logout();late.vm.resetSourceStates();wait.resolve(row);await pending;assert.equal(late.vm.processDetail.value,null)
})
