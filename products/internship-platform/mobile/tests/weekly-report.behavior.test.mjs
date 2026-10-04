import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as presentation from '../src/services/weeklyReportPresentation.mjs'
import { loadReportMedia } from '../src/services/reportMedia.mjs'

function page(api = {}, sdk = {}, path = 'student/weekly-report/index.vue') {
  const source = fs.readFileSync(new URL('../src/pages/' + path, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm, '').replace('export default', 'return')
  let generation = 0
  const names = ['studentApi','fileSdk','normalizeError','currentSessionGeneration','ReportFilePreview','MobileInlineAlert','toast', ...Object.keys(presentation)]
  const component = new Function(...names, script)(api, sdk,
    error => ({ kind: error?.httpStatus === 409 ? 'conflict' : 'network', text: '请求未完成', pageState: 'error' }),
    () => generation, {}, {}, () => {}, ...Object.values(presentation))
  const vm = { ...component.data(), $refs: { reportPreview: { reset() {} } } }
  for (const [name, method] of Object.entries(component.methods)) vm[name] = (...args) => method.apply(vm,args)
  for (const [name,getter] of Object.entries(component.computed)) Object.defineProperty(vm,name,{get:()=>getter.call(vm)})
  return { vm, component, switchAccount: () => generation++ }
}
const context = { hasBatch: true, batchId: '9007199254740993001', recordId: '9007199254740993002', company: '合成企业', post: '实习岗位', batch: '合成批次', weekly: { week: '第 9 周' } }
const report = (overrides={}) => ({ id:'9007199254740993003', week:1, status:'RETURNED', version:2, reportVersion:1, workContent:'岗位工作', harvestContent:'收获体会', planContent:'', attachments:[], ...overrides })
const metadata = {fileId:'f1',fileName:'岗位过程.mp4',mimeType:'video/mp4',status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true,allowedActions:['download','preview']}

test('history message resolves a bounded focus page, with untouched current-page state', async () => {
  const calls=[]
  const {vm}=page({ getInternship:async()=>context,
    getInternshipWeeklyReports:async(...args)=>{ calls.push(args); return args[2]===1 ? {page:1,total:60,focusPage:2,items:[report({week:9,status:'APPROVED',id:'current'})]} : {page:args[2],total:60,items:[report()]} },
    getInternshipWeeklyReportDetail:async()=>({...report(),immutableVersions:[]}) })
  vm.focusReportId=report().id
  await vm.load()
  assert.deepEqual(calls.map(call=>call[2]),[1,2]); assert.equal(vm.selectedWeek,1); assert.equal(vm.baseVersion,2)
  await vm.loadMore(); assert.deepEqual(calls.map(call=>call[2]),[1,2,3]); assert.equal(vm.hasMore,false)
})

test('the school minimum counts all three fields and does not impose invented per-field ten-word gates', async()=>{
  const {vm}=page({getInternship:async()=>context,getInternshipWeeklyReports:async()=>({items:[],rules:{weeklyMinWords:80}})})
  await vm.load(); vm.form.workContent='工作'; vm.form.harvestContent='收获'; vm.form.planContent='计'.repeat(75)
  assert.equal(vm.canSubmit,false); vm.form.planContent+='划'; assert.equal(vm.canSubmit,true)
})

test('switching weeks keeps unsent text isolated by week and resubmission version',async()=>{
  const {vm}=page({getInternship:async()=>context,getInternshipWeeklyReports:async()=>({items:[report()]}),getInternshipWeeklyReportDetail:async()=>report()})
  await vm.load(); vm.form.workContent='尚未提交的第九周'; await vm.selectWeek(1); assert.equal(vm.form.workContent,'岗位工作')
  vm.form.workContent='根据退回意见补充'; await vm.selectWeek(9); assert.equal(vm.form.workContent,'尚未提交的第九周')
  await vm.selectWeek(1); assert.equal(vm.form.workContent,'根据退回意见补充'); assert.equal(vm.baseVersion,2)
})

test('pending attachments block submit until authoritative scan reread succeeds',async()=>{
  const {vm}=page({getInternship:async()=>context,getInternshipWeeklyReports:async()=>({items:[]})},{metadata:async()=>metadata})
  await vm.load(); vm.form.workContent='工作'.repeat(20); vm.form.harvestContent='收获'
  vm.form.attachments=[presentation.reportFileState({...metadata,scanStatus:'PENDING',status:'QUARANTINED',readyForBusiness:false})]
  assert.equal(vm.canSubmit,false); await vm.refreshAttachments(); assert.equal(vm.canSubmit,true)
  assert.equal(vm.form.attachments[0].kindLabel,'视频')
})

test('a scan error keeps text and attachment; a later retry can resume',async()=>{
  let fail=true
  const {vm}=page({getInternship:async()=>context,getInternshipWeeklyReports:async()=>({items:[]})},{metadata:async()=>{if(fail)throw Error('network');return metadata}})
  await vm.load(); vm.form.workContent='未提交正文'; vm.form.attachments=[{fileId:'f1',readyForBusiness:false}]
  await vm.refreshAttachments(); assert.equal(vm.form.workContent,'未提交正文'); assert.equal(vm.form.attachments.length,1)
  assert.match(vm.submitError,/已保留/); fail=false; await vm.refreshAttachments(); assert.equal(vm.attachmentsReady,true)
})

test('version conflict preserves edits and does not silently adopt the new version or automatically retry',async()=>{
  let server=report(),posts=0
  const {vm}=page({getInternship:async()=>context,getInternshipWeeklyReports:async()=>({items:[server]}),getInternshipWeeklyReportDetail:async()=>server,
    submitInternshipWeeklyReport:async()=>{posts++;server=report({version:4});throw {httpStatus:409}}})
  vm.focusWeek=1; await vm.load(); vm.form.workContent='学生补充内容'.repeat(8); vm.form.harvestContent='新的收获'
  await vm.submit(); assert.equal(posts,1); assert.equal(vm.baseVersion,2); assert.equal(vm.conflict,true); assert.match(vm.form.workContent,/学生补充/)
  await vm.reloadConflict(); assert.equal(vm.baseVersion,2); assert.equal(vm.canSubmit,false); assert.equal(posts,1)
  vm.continueAfterConflict(); assert.equal(vm.baseVersion,4); assert.equal(vm.canSubmit,true)
})

test('successful submit sends stable IDs and file IDs, then rereads a readonly receipt',async()=>{
  let rows=[],body
  const {vm}=page({getInternship:async()=>context,getInternshipWeeklyReports:async()=>({items:rows,total:rows.length,page:1}),getInternshipWeeklyReportDetail:async()=>rows[0],
    submitInternshipWeeklyReport:async payload=>{body=payload;const row=report({week:9,status:'PENDING_REVIEW',version:0}); rows=[row];return row}})
  await vm.load(); vm.form.workContent='工作总结'.repeat(10); vm.form.harvestContent='岗位学习';vm.form.attachments=[metadata]
  await vm.submit(); assert.equal(body.batchId,context.batchId); assert.equal(body.internshipId,context.recordId); assert.deepEqual(body.attachmentFileIds,['f1'])
  assert.equal(vm.selectedReport.status,'PENDING_REVIEW'); assert.equal(vm.isEditableWeek,false); assert.match(vm.receipt.nextStep,/指导教师/)
})

test('network submit failure retains all inputs and never displays a success receipt',async()=>{
  const {vm}=page({getInternship:async()=>context,getInternshipWeeklyReports:async()=>({items:[]}),submitInternshipWeeklyReport:async()=>{throw Error('network')}})
  await vm.load();vm.form.workContent='岗位工作'.repeat(10);vm.form.harvestContent='收获'; const old=vm.form.workContent
  await vm.submit(); assert.equal(vm.form.workContent,old);assert.equal(vm.receipt,null);assert.match(vm.submitError,/已保留/)
})

test('old-account responses cannot populate the page and switching account clears private drafts',async()=>{
  let resolve
  const {vm,component,switchAccount}=page({getInternship:()=>new Promise(r=>{resolve=r})})
  const pending=vm.load();switchAccount();resolve(context);await pending;assert.equal(vm.loaded,false)
  vm.form.workContent='旧学生未提交内容';vm.drafts.private={};vm.company='旧企业';component.onShow.call(vm)
  assert.equal(vm.form.workContent,'');assert.equal(vm.company,'');assert.deepEqual(vm.drafts,{})
})

test('reopening during an old detail and scan read starts a fresh detail rather than leaving returned reports blocked',async()=>{
  let detailResolve,scanResolve,detailCalls=0,scanCalls=0
  const {vm,component}=page({getInternship:async()=>context,getInternshipWeeklyReports:async()=>({items:[report()]}),
    getInternshipWeeklyReportDetail:()=>++detailCalls===1 ? new Promise(resolve=>{detailResolve=resolve}) : Promise.resolve(report())},
    {metadata:()=>++scanCalls===1 ? new Promise(resolve=>{scanResolve=resolve}) : Promise.resolve(metadata)})
  vm.loaded=true; vm.state='ready'; vm.batchId=context.batchId; vm.internshipId=context.recordId; vm.selectedWeek=1; vm.weeklyList=[report()]
  vm.form.workContent='学生补正'.repeat(10); vm.form.harvestContent='岗位收获'; vm.baseVersion=2
  vm.form.attachments=[presentation.reportFileState({...metadata,readyForBusiness:false,scanStatus:'PENDING',status:'QUARANTINED'})]
  const oldDetail=vm.loadDetail(), oldScan=vm.refreshAttachments(); component.onHide.call(vm); await component.onShow.call(vm)
  assert.equal(detailCalls,2); assert.equal(vm.detailState,'ready'); assert.match(vm.form.workContent,/学生补正/)
  detailResolve(report({workContent:'迟到的旧正文'})); scanResolve(metadata); await Promise.all([oldDetail,oldScan])
  assert.match(vm.form.workContent,/学生补正/); await vm.refreshAttachments(); assert.equal(vm.canSubmit,true)
})

test('unknown machine values have neutral Chinese labels and preserve student-authored text',()=>{
  const row=presentation.weeklyReportView(report({status:'NEW_INTERNAL_STATE',workContent:'PLC工序',review:{ratingLevel:6},immutableVersions:[{review:{action:'INTERNAL_ACTION',ratingLevel:7}}]}))
  assert.equal(row.statusLabel,'状态待确认');assert.equal(row.ratingLabel,'暂无评价');assert.equal(row.workContent,'PLC工序')
  assert.equal(row.immutableVersions[0].review.actionLabel,'批阅结果待确认')
  assert.equal(presentation.reportTypeLabel('INTERNAL'),'报告类型待确认');assert.equal(presentation.reportPeriodLabel('SUMMARY','SUMMARY'),'实习总结')
  assert.equal(presentation.makeupStatusLabel('INTERNAL'),'状态待确认');assert.equal(presentation.reportFileState({...metadata,scanStatus:'INTERNAL',statusText:'MYSQL_ERROR'}).statusText,'文件状态待确认')
  assert.equal(presentation.processReportView({reportType:'INTERNAL',periodKey:'MYSQL_ERROR',status:'NEW_INTERNAL_STATE'}).periodLabel,'周期待确认')
  assert.equal(presentation.reportPeriodLabel('WEEKLY','2026-W39'),'2026年第39周')
})

test('daily and monthly report attachments share the scan gate and keep unsent input when reopening',async()=>{
  const {vm,component}=page({getInternship:async()=>context,getInternshipProcessReports:async()=>({items:[]})},{metadata:async()=>metadata},'student-internship/process-report/index.vue')
  await vm.load(); vm.form.periodKey='2026-10-03'; vm.form.content='正文'.repeat(20)
  vm.form.attachments=[presentation.reportFileState({...metadata,scanStatus:'PENDING',status:'QUARANTINED',readyForBusiness:false})]
  assert.equal(vm.canSubmit,false); await vm.refreshAttachments(); assert.equal(vm.canSubmit,true)
  component.onHide.call(vm); assert.equal(vm.canSubmit,false); component.onShow.call(vm)
  assert.equal(vm.form.content,'正文'.repeat(20)); assert.equal(vm.canSubmit,true)
})

test('a late process-report scan response cannot repopulate files after the student session changes',async()=>{
  let resolve
  const {vm,component,switchAccount}=page({}, {metadata:()=>new Promise(r=>{resolve=r})},'student-internship/process-report/index.vue')
  vm.pageState='ready'; vm.loaded=true; vm.form.content='旧学生未提交正文'; vm.form.attachments=[{fileId:'f1',readyForBusiness:false}]
  const pending=vm.refreshAttachments(); switchAccount(); resolve(metadata); await pending
  assert.equal(vm.form.attachments[0].readyForBusiness,false); assert.equal(vm.canSubmit,false)
  component.onShow.call(vm); assert.equal(vm.form.content,''); assert.deepEqual(vm.form.attachments,[])
})

test('report media requires metadata authorization and uses authenticated bytes rather than a public URL',async()=>{
  let downloads=0
  const sdk={metadata:async()=>metadata,download:async id=>{downloads++;assert.equal(id,'f1');return {tempFilePath:'/temporary/video.mp4'}}}
  const ready=await loadReportMedia({fileId:'f1'},sdk);assert.equal(ready.kind,'video');assert.equal(downloads,1)
  sdk.metadata=async()=>({...metadata,readyForBusiness:false,scanStatus:'PENDING'})
  await assert.rejects(()=>loadReportMedia({fileId:'f1'},sdk));assert.equal(downloads,1)
  sdk.metadata=async()=>metadata;assert.equal(await loadReportMedia({fileId:'f1'},sdk,()=>false),null);assert.equal(downloads,1)
})

test('student and teacher activity entry pages are registered and exist',()=>{
  const pages=JSON.parse(fs.readFileSync(new URL('../src/pages.json',import.meta.url),'utf8'))
  for(const path of ['pages/student/weekly-report/index','pages/teacher-internship/activity/index']){
    assert.equal(pages.pages.filter(page=>page.path===path).length,1)
    assert.ok(fs.existsSync(new URL('../src/'+path+'.vue',import.meta.url)))
  }
})
