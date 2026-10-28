import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { reactive, watchEffect, compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import * as presentation from '../src/services/weeklyReportPresentation.mjs'
import { loadReportMedia } from '../src/services/reportMedia.mjs'
import { formatDateTime } from '../src/utils/format.js'
import { normalizeError } from './request-module.mjs'

function page(api = {}, sdk = {}, path = 'student/weekly-report/index.vue', contextStore = { can: () => true }, storage = {}) {
  const source = fs.readFileSync(new URL('../src/pages/' + path, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm, '').replace('export default', 'return')
  let generation = 0, modal, sheet
  const names = ['ReportObligations','studentApi','fileSdk','normalizeError','currentSessionGeneration','ReportFilePreview','MobileInlineAlert','toast', ...Object.keys(presentation),
    'teacherInternshipProcessReports','teacherInternshipProcessReportDetail','teacherInternshipProcessReportReview','useInternshipContextStore','uni','formatDateTime','currentMobileSession']
  const component = new Function(...names, script)({}, api, sdk,
    error => error?.pageState ? {text:'请求未完成',pageState:error.pageState} : normalizeError(error),
    () => generation, {}, {}, () => {}, ...Object.values(presentation), api.teacherInternshipProcessReports, api.teacherInternshipProcessReportDetail,
    api.teacherInternshipProcessReportReview, () => contextStore, {showModal: value => {modal=value},showActionSheet:value=>{sheet=value},setNavigationBarTitle(){},setStorageSync(key,value){storage[key]=structuredClone(value)}}, formatDateTime, () => structuredClone(storage.gx_session_v1 || {}))
  const vm = { ...component.data(), $refs: { reportPreview: { reset() {} } }, $nextTick: callback => Promise.resolve().then(callback) }
  for (const [name, method] of Object.entries(component.methods)) vm[name] = (...args) => method.apply(vm,args)
  for (const [name,getter] of Object.entries(component.computed)) Object.defineProperty(vm,name,{get:()=>getter.call(vm)})
  return { vm, component, switchAccount: () => generation++, modal: () => modal, sheet: () => sheet }
}
const context = { hasBatch: true, batchId: '9007199254740993001', recordId: '9007199254740993002', company: '合成企业', post: '实习岗位', batch: '合成批次', weekly: { week: '第 9 周' } }
const report = (overrides={}) => ({ id:'9007199254740993003', week:1, status:'RETURNED', version:2, reportVersion:1, workContent:'岗位工作', harvestContent:'收获体会', planContent:'', attachments:[], ...overrides })
const metadata = {fileId:'f1',fileName:'岗位过程.mp4',mimeType:'video/mp4',status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true,allowedActions:['download','preview']}

function weeklyPresentation(vm) {
  const source=fs.readFileSync(new URL('../src/pages/student/weekly-report/index.vue',import.meta.url),'utf8')
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const shell={setup:(_,{slots})=>()=>h('div',slots.default?.())}
  const components={MobileNavBar:{props:['title','subtitle','fallbackUrl'],setup:p=>()=>h('nav',{'data-return':p.fallbackUrl},[p.title,p.subtitle])},MobileGlobalState:shell,MobileSafeAreaBar:shell,ReportFilePreview:{render:()=>null},MobileStatusTag:{props:['label'],setup:p=>()=>h('span',p.label)},MobileInlineAlert:{props:['description'],setup:p=>()=>h('p',p.description)}}
  const render=compile(template,{isCustomElement:tag=>['view','text','picker'].includes(tag)})
  const eventRender=compile(template,{isCustomElement:tag=>['view','text','picker'].includes(tag)||/^[A-Z]/.test(tag)})
  return {html:()=>renderToString(createSSRApp({components,render:()=>render(vm,[])})),tree:async()=>{let tree;await renderToString(createSSRApp({render:()=>{tree=eventRender(vm,[]);return tree}}));return tree}}
}
function weeklyNodes(node,predicate,result=[]) {if(!node||typeof node!=='object')return result;if(predicate(node))result.push(node);for(const child of Array.isArray(node.children)?node.children:[])weeklyNodes(child,predicate,result);return result}

test('已归档过程报告采用服务端历史只读状态，未提交草稿保留但不能新增或上传',async()=>{
  let uploaded=0;const p=page({getInternship:async()=>({...context,historyMode:true}),getInternshipProcessReports:async()=>({items:[],total:0})},{choose:async()=>{uploaded++;return {}}},'student-internship/process-report/index.vue')
  p.vm.form.content='保留本地未提交的原草稿';await p.vm.load();assert.equal(p.vm.historyMode,true);assert.equal(p.vm.form.content,'保留本地未提交的原草稿');assert.equal(p.vm.canEditReport,false);assert.equal(p.vm.canSubmit,false)
  await p.vm.addAttachment('image');assert.equal(uploaded,0)
})

test('周报呈现当前周期保留字数扫描与返回守卫，不重复泛化说明',async()=>{
  const {vm}=page();Object.assign(vm,{loaded:true,state:'ready',batchId:'18',internshipId:'18',currentWeek:3,selectedWeek:3,company:'真实企业',post:'原岗位',schoolMentor:'原导师',batchName:'原批次'})
  const view=weeklyPresentation(vm);let html=await view.html();for(const text of ['真实企业','原岗位','原导师','原批次','第 3 周','填写中','至少 30 字','每段最多2000字','本周工作内容','本周收获','存在问题 / 下周计划'])assert.ok(html.includes(text),text)
  assert.doesNotMatch(html,/提交后交给|同一登录会话中刷新|请结合本周岗位工作填写/)
  assert.equal(weeklyNodes(await view.tree(),n=>n.type==='MobileNavBar')[0].props['before-back'],vm.beforeBack)
  assert.match(html,/pages\/student-internship\/index\?batchId=18/);assert.equal(vm.canSubmit,false)
  vm.form.workContent='工作'.repeat(20);vm.form.harvestContent='原收获';vm.form.attachments=[{fileId:'1',readyForBusiness:false,statusText:'等待安全扫描'}];html=await view.html();assert.match(html,/附件安全就绪前不能提交/);assert.equal(vm.canSubmit,false)
  vm.conflict=true;vm.selectedWeek=1;vm.weeklyList=[report({id:'77',week:1,reviewComment:'请补检查成果'})];html=await view.html();assert.match(html,/请补检查成果/);assert.match(html,/填写内容已保留/);assert.equal(vm.form.harvestContent,'原收获')
})

test('周报呈现已审原文默认只显示一遍，历史反馈保留且每版正文附件可展开',async()=>{
  const {vm}=page();Object.assign(vm,{loaded:true,state:'ready',batchId:'18',internshipId:'18',currentWeek:3,selectedWeek:1,detailState:'ready'})
  vm.weeklyList=[report({id:'77',week:1,status:'APPROVED',statusLabel:'已批阅',version:8,reportVersion:2,workContent:'当前版本唯一正文',harvestContent:'当前收获',planContent:'下周计划',reviewComment:'当前导师有效反馈',attachments:[{fileId:'22',fileName:'当前附件.png'}]})]
  vm.detail={ratingLabel:'四星评价',immutableVersions:[{id:'102',versionNo:2,wordCount:171,content:{workContent:'当前版本唯一正文',harvestContent:'当前收获'},attachments:[{fileId:'22',fileName:'当前附件.png'}],review:{actionLabel:'批阅通过',ratingLabel:'四星评价',reviewerName:'原导师',comment:'当前导师有效反馈'}},{id:'101',versionNo:1,wordCount:111,content:{workContent:'历史版本正文必须保留',harvestContent:'历史收获',planContent:'历史计划'},attachments:[{fileId:'21',fileName:'历史附件.png'}],review:{actionLabel:'退回修改',ratingLabel:'暂无评价',reviewerName:'原导师',comment:'第一版退回原因'}}]}
  const view=weeklyPresentation(vm);let html=await view.html();assert.equal((html.match(/当前版本唯一正文/g)||[]).length,1);assert.doesNotMatch(html,/历史版本正文必须保留|历史附件.png/)
  for(const text of ['第 1 周','第 2 版','171 字','111 字','当前导师有效反馈','四星评价','下载当前提交版周报文书','当前附件.png'])assert.ok(html.includes(text),text)
  assert.equal((html.match(/当前导师有效反馈/g)||[]).length,1);assert.doesNotMatch(html,/第一版退回原因/)
  const buttons=weeklyNodes(await view.tree(),n=>n.type==='button'&&n.props?.['aria-expanded']===false);assert.equal(buttons.length,2);buttons[1].props.onClick()
  html=await view.html();assert.match(html,/历史版本正文必须保留/);assert.match(html,/历史附件.png/);assert.match(html,/第一版退回原因/);assert.equal(vm.selectedReport.version,8);assert.equal(vm.isEditableWeek,false)
  vm.generation=1;assert.doesNotMatch(await view.html(),/历史版本正文必须保留/)
  vm.detailState='error';html=await view.html();assert.match(html,/版本与评分读取失败/);assert.match(html,/当前版本唯一正文/);assert.match(html,/重试读取记录/)
})

test('full reload keeps process conflict text files and old version until explicit adoption',async()=>{
  const storage={gx_session_v1:{logged:true,isTeacher:false,identity:{tenantId:'t1',userId:'u1',activeContextId:'c1'}}}
  let row={id:'42',batchId:context.batchId,internshipId:context.recordId,reportType:'DAILY',periodKey:'2026-09-17',content:'原单',status:'RETURNED',version:2,reportVersion:1,attachments:[]}
  const api={getInternship:async()=>context,getInternshipProcessReports:async()=>({items:[row],total:1}),getInternshipProcessReportDetail:async()=>row}
  const make=()=>page(api,{metadata:async()=>metadata},'student-internship/process-report/index.vue',undefined,storage)
  const first=make();first.vm.focusReportId='42';await first.vm.load()
  first.vm.form.content='并行B-报告未提交正文';first.vm.form.attachments=[metadata];first.vm.conflict=true
  first.vm.saveDraft()
  row={...row,content:'另一个客户端的新版',version:5,reportVersion:2}
  const refreshed=make();await refreshed.vm.load()
  assert.equal(refreshed.vm.form.content,'并行B-报告未提交正文');assert.equal(refreshed.vm.form.attachments[0].fileId,'f1')
  assert.equal(refreshed.vm.selectedDetail.version,2);assert.equal(refreshed.vm.latestDetail.version,5)
  assert.equal(refreshed.vm.conflict,true);assert.equal(refreshed.vm.canSubmit,false)
  await refreshed.vm.rereadConflict();assert.equal(refreshed.vm.selectedDetail.version,2)
  refreshed.vm.continueAfterConflict();assert.equal(refreshed.vm.selectedDetail.version,5)
  assert.equal(refreshed.vm.form.content,'并行B-报告未提交正文')
  for(const field of ['tenantId','userId','activeContextId']){
    const original=storage.gx_session_v1.identity[field];storage.gx_session_v1.identity[field]='other'
    const other=make();other.vm.form.periodKey=row.periodKey;await other.vm.load()
    assert.notEqual(other.vm.form.content,'并行B-报告未提交正文');storage.gx_session_v1.identity[field]=original
  }
  delete storage.gx_session_v1
  const loggedOut=make();assert.equal(loggedOut.vm.restoreDrafts(),false)
})

test('reload retains other report drafts after the last active draft was submitted',()=>{
  for(const weekly of [false,true]){
    const storage={gx_session_v1:{logged:true,isTeacher:false,identity:{tenantId:'t1',userId:'u1',activeContextId:'c1'}}}
    const {vm}=page({}, {}, weekly?'student/weekly-report/index.vue':'student-internship/process-report/index.vue', undefined, storage)
    vm.batchId=context.batchId;vm.internshipId=context.recordId
    const key=[context.batchId,context.recordId,weekly?'1':'MONTHLY:2026-10'].join(':')
    const draft={form:{content:'保留另一类报告',workContent:'保留另一周',attachments:[metadata]}}
    storage.gx_session_v1[weekly?'weeklyReportDrafts':'processReportDrafts']={scope:vm.draftScope(storage.gx_session_v1),week:9,activeKey:'already-submitted',drafts:{[key]:draft}}
    vm.restoreDrafts()
    assert.deepEqual(vm.drafts[key],draft)
  }
})

test('full reload keeps weekly draft base version and attachments across a competing submission',async()=>{
  const storage={gx_session_v1:{logged:true,isTeacher:false,identity:{tenantId:'t1',userId:'u1',activeContextId:'c1'}}}
  let row=report()
  const api={getInternship:async()=>context,getInternshipWeeklyReports:async()=>({items:[row],total:1}),getInternshipWeeklyReportDetail:async()=>row}
  const make=()=>page(api,{metadata:async()=>metadata},'student/weekly-report/index.vue',undefined,storage)
  const first=make();first.vm.focusWeek=1;await first.vm.load()
  first.vm.form.workContent='并行B-报告未提交周报';first.vm.form.attachments=[metadata];first.vm.conflict=true
  first.vm.saveDraft()
  row=report({version:5,status:'PENDING_REVIEW',workContent:'他人已交新版'})
  const refreshed=make();await refreshed.vm.load()
  assert.equal(refreshed.vm.selectedWeek,1);assert.equal(refreshed.vm.baseVersion,2)
  assert.equal(refreshed.vm.form.workContent,'并行B-报告未提交周报');assert.equal(refreshed.vm.form.attachments[0].fileId,'f1')
  assert.equal(refreshed.vm.conflict,true);assert.equal(refreshed.vm.canSubmit,false)
  refreshed.vm.continueAfterConflict();assert.equal(refreshed.vm.baseVersion,2)
  row={...row,status:'RETURNED',version:6};await refreshed.vm.reloadConflict();refreshed.vm.continueAfterConflict()
  assert.equal(refreshed.vm.baseVersion,6);assert.equal(refreshed.vm.form.workContent,'并行B-报告未提交周报')
  storage.gx_session_v1.identity.userId='other'
  const other=make();other.vm.focusWeek=1;await other.vm.load()
  assert.notEqual(other.vm.form.workContent,'并行B-报告未提交周报')
})

function teacherReviewPage(api={}) {
  let generation=1,modal,sheet
  const notices=[],deps={teacherApi:api,teacherInternshipEvidenceV3Api:{},handleCheckinV3(){},
    useInternshipContextStore:()=>({can:()=>true}),normalizeError,
    toast:text=>notices.push(text),currentSessionGeneration:()=>generation,listPaging:()=>({}),
    InternshipVisitEvidenceForm:{},MobileSequentialQueue:{},ReportFilePreview:{},ReportObligations:{},
    uni:{showModal:options=>{modal=options},showActionSheet:options=>{sheet=options}}}
  const script=fs.readFileSync(new URL('../src/pages/teacher-internship/internship-review/index.vue',import.meta.url),'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm=reactive({...component.data(),$refs:{}})
  for(const [name,method] of Object.entries(component.methods)) vm[name]=method.bind(vm)
  for(const [name,getter] of Object.entries(component.computed)) Object.defineProperty(vm,name,{get:getter.bind(vm)})
  vm.batchId='18';vm.state='ready';vm.data={reports:[]}
  return {vm,notices,modal:()=>modal,sheet:()=>sheet,switchAccount:()=>generation++}
}

test('周报真实冲突保留等级与意见，采用前不能重写，明确核对新版才继续',async()=>{
  const writes=[],p=teacherReviewPage({reviewWeekly:async(...args)=>{writes.push(args);throw {code:1,bizCode:'DATA_CONFLICT',httpStatus:400}}})
  const row={id:'2',expectedVersion:3,_body:'ready',status:'PENDING_REVIEW'};p.vm.data.reports=[row]
  p.vm.sequentialMode=true;p.vm.load=async()=>{p.vm.readEpoch++};p.vm.review(row,'pass');p.vm.weeklyReviewPanel.draft.ratingLevel=4
  p.vm.weeklyReviewPanel.draft.comment='合成周报评分意见';await p.vm.submitWeeklyReview();await new Promise(resolve=>setImmediate(resolve))
  const draft=p.vm.commandDrafts['18:weekly:2'];assert.equal(draft.version,3);assert.equal(draft.ratingLevel,4)
  assert.equal(draft.comment,'合成周报评分意见');assert.equal(p.vm.acting,false);assert.equal(p.vm.sequentialConflict,true)
  p.vm.review(row,'pass');assert.equal(writes.length,1)
  row.expectedVersion=9;p.vm.review(row,'pass');p.modal().success({confirm:true})
  assert.equal(p.vm.weeklyReviewPanel.draft.comment,'合成周报评分意见');await p.vm.submitWeeklyReview()
  await new Promise(resolve=>setImmediate(resolve));assert.equal(writes[1][3],9);assert.equal(writes[1][4],4)
})

test('考勤异常冲突保存说明并解除自身刷新锁，缺事实仍不能恢复办理',async()=>{
  const writes=[],p=teacherReviewPage({handleCheckin:async(...args)=>{writes.push(args);throw {code:1,bizCode:'APPROVAL_VERSION_CONFLICT',httpStatus:409}}})
  p.vm.load=async()=>{p.vm.readEpoch++};p.vm.afterSequentialSuccess=()=>{}
  const row={id:'2',expectedVersion:3,decisionFactsComplete:true};p.vm.ck(row,'ok')
  p.modal().success({confirm:true,content:'已核对合成设备定位事实'});await new Promise(resolve=>setImmediate(resolve))
  assert.equal(p.vm.acting,false);assert.equal(p.vm.commandDrafts['18:abnormal:2'].version,3)
  p.vm.ck({...row,expectedVersion:9,decisionFactsComplete:false},'ok');assert.equal(writes.length,1)
  p.vm.ck({...row,expectedVersion:9},'ok');p.modal().success({confirm:true})
  assert.equal(p.modal().content,'已核对合成设备定位事实');assert.equal(writes.length,1)
})

test('过程报告真实冲突保留总结零分和意见，必须重开正文并明确采用',async()=>{
  const writes=[],p=page({teacherInternshipProcessReportReview:async(...args)=>{writes.push(args);throw {code:1,bizCode:'APPROVAL_VERSION_CONFLICT',httpStatus:409}}},{},'teacher-internship/process-report-review/index.vue')
  const row={id:'42',reportType:'SUMMARY'};p.vm.state='ready';p.vm.batchId='18';p.vm.detail={'42':{version:3,status:'PENDING_REVIEW'}}
  p.vm.load=async()=>{p.vm.loadSeq++};p.vm.review(row,'APPROVE')
  p.vm.reviewPanel.draft.summaryScore='0';p.vm.reviewPanel.draft.comment='总结合成评分意见';await p.vm.submitReview()
  const draft=p.vm.reviewDrafts['18:42'];assert.equal(draft.summaryScore,'0');assert.equal(draft.version,3);assert.equal(p.vm.actingId,'')
  p.vm.review(row,'APPROVE');assert.equal(writes.length,1)
  p.vm.detail['42'].version=9;p.vm.review(row,'APPROVE');p.modal().success({confirm:true})
  assert.equal(p.vm.reviewPanel.draft.comment,'总结合成评分意见');assert.equal(p.vm.reviewPanel.draft.summaryScore,'0')
  await p.vm.submitReview();assert.equal(writes[1][2].expectedVersion,9);assert.equal(writes[1][2].summaryScore,0)
})

test('teacher reads the exact report body and freezes the version from that same detail',async()=>{
  const detail={id:'2',batchId:'18',version:5,status:'PENDING_REVIEW',work:'原单正文',harvest:'收获',plan:'计划'}
  const {vm}=teacherReviewPage({getWeeklyDetail:async()=>detail}),row={id:'2',expectedVersion:1}
  vm.data.reports=[row];await vm.loadBody(row)
  assert.equal(row.tasks,'原单正文');assert.equal(row.expectedVersion,5);assert.equal(row._body,'ready')
  const wrong=teacherReviewPage({getWeeklyDetail:async()=>({...detail,batchId:'other'})}),other={id:'2'}
  wrong.vm.data.reports=[other];await wrong.vm.loadBody(other);assert.equal(other._body,'error');assert.equal(other.tasks,undefined)
})

test('teacher ignores a body arriving after account switch or page hide',async()=>{
  let finish;const wait=new Promise(resolve=>{finish=resolve})
  const {vm,switchAccount,notices}=teacherReviewPage({getWeeklyDetail:()=>wait}),row={id:'2'}
  vm.data.reports=[row];const pending=vm.loadBody(row);switchAccount();vm.invalidateReads()
  finish({id:'2',batchId:'18',version:5,status:'PENDING_REVIEW',work:'旧正文'});await pending
  assert.equal(row.tasks,undefined);assert.deepEqual(notices,[])
})

test('teacher must read the body before returning and sends its captured detail version',async()=>{
  const calls=[],{vm,modal}=teacherReviewPage({reviewWeekly:async(...args)=>{calls.push(args);return {status:'RETURNED'}}})
  const row={id:'2',expectedVersion:5};vm.data.reports=[row]
  vm.review(row,'return');assert.equal(modal(),undefined)
  row._body='ready';vm.load=async()=>{};vm.review(row,'return')
  vm.weeklyReviewPanel.draft.comment='请补充岗位工作成果';vm.submitWeeklyReview();await new Promise(resolve=>setImmediate(resolve))
  assert.deepEqual(calls[0],['2','RETURN','请补充岗位工作成果',5,null])
})

test('a late teacher command does not replace a new page state or unlock its operation',async()=>{
  let finish;const wait=new Promise(resolve=>{finish=resolve})
  const {vm,modal}=teacherReviewPage({reviewWeekly:()=>wait}),row={id:'2',expectedVersion:5,_body:'ready'}
  vm.data.reports=[row];vm.review(row,'return');vm.weeklyReviewPanel.draft.comment='请补充岗位工作成果';vm.submitWeeklyReview()
  vm.invalidateReads();vm.hidden=false;vm.batchId='other';vm.acting=true
  finish({status:'RETURNED'});await new Promise(resolve=>setImmediate(resolve))
  assert.equal(row.status,undefined);assert.equal(vm.acting,true)
})

test('focused teacher detail updates the reactive page rather than leaving a loading body',async()=>{
  let finish;const wait=new Promise(resolve=>{finish=resolve}),row={id:'2',status:'PENDING_REVIEW',expectedVersion:1}
  const {vm}=teacherReviewPage({getWeeklyReports:async()=>({batchId:'18',focusReportId:'2',reports:[row],abnormal:[]}),getWeeklyDetail:()=>wait})
  vm.focusReportId='2';vm.context={selectBatch:()=>true};vm.batches=[{id:'18'}];vm.pagedReset=()=>{};vm.ensureBatchContext=async()=>{}
  const states=[],stop=watchEffect(()=>states.push(vm.data?.reports?.[0]?._body))
  try {
    await vm.load();finish({id:'2',batchId:'18',version:1,status:'PENDING_REVIEW',work:'当前正文'})
    await new Promise(resolve=>setImmediate(resolve))
    assert.equal(vm.data.reports[0]._body,'ready');assert.equal(states.at(-1),'ready')
  } finally {stop()}
})

test('confirmed teacher command followed by an old refresh cannot advance a new queue',async()=>{
  let finish;const wait=new Promise(resolve=>{finish=resolve})
  const {vm,modal,switchAccount}=teacherReviewPage({reviewWeekly:async()=>({status:'RETURNED'})}),row={id:'2',expectedVersion:1,_body:'ready'}
  vm.data.reports=[row];vm.load=()=>wait;vm.review(row,'return');vm.weeklyReviewPanel.draft.comment='请补充岗位工作成果';vm.submitWeeklyReview()
  await new Promise(resolve=>setImmediate(resolve));switchAccount();vm.batchId='other';vm.sequentialIndex=1
  finish({reports:[]});await new Promise(resolve=>setImmediate(resolve));assert.equal(vm.sequentialIndex,1)
})

test('forbidden report or attendance sources remain unread rather than becoming an empty success',()=>{
  const {vm}=teacherReviewPage()
  vm.data.errors=[{source:'attendanceException',message:'无查看权限'}];vm.tab='abnormal'
  assert.equal(vm.abnormalPendingCount,'—');assert.match(vm.tabSummaryConclusion,/无法读取/)
  vm.data.errors=[{source:'weeklyReport',message:'无查看权限'}];vm.tab='weekly'
  assert.equal(vm.weeklyPendingCount,'—');assert.match(vm.tabSummaryConclusion,/无法读取/)
})

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

test('an explicit zero weekly minimum keeps mandatory body fields',()=>{
  const {vm}=page()
  vm.state='ready';vm.rules.weeklyMinWords=0
  assert.equal(vm.minimum,0);assert.equal(vm.canSubmit,false)
  vm.form.workContent='工';vm.form.harvestContent='获'
  assert.equal(vm.canSubmit,true)
  vm.rules.weeklyMinWords=3;assert.equal(vm.canSubmit,false)
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

test('process original reads its exact zero score and versions, while a late account response is discarded',async()=>{
  const detail={id:'42',batchId:context.batchId,internshipId:context.recordId,reportType:'SUMMARY',periodKey:'FINAL',content:'总结正文'.repeat(80),version:2,status:'APPROVED',reportVersion:2,
    review:{action:'APPROVE',summaryScore:0},immutableVersions:[{versionNo:2,content:'新版总结',review:{action:'APPROVE',summaryScore:0}},{versionNo:1,content:'原总结',review:{action:'RETURN',comment:'请补充成果'}}]}
  const p=page({getInternshipProcessReportDetail:async()=>detail},{},'student-internship/process-report/index.vue')
  p.vm.batchId=context.batchId;p.vm.internshipId=context.recordId;await p.vm.selectRecord({id:'42'})
  assert.equal(p.vm.selectedDetail.review.summaryScore,0);assert.equal(p.vm.selectedDetail.immutableVersions[1].review.actionLabel,'退回修改')
  assert.equal(p.vm.form.content,detail.content)
  let finish;const late=page({getInternshipProcessReportDetail:()=>new Promise(resolve=>{finish=resolve})},{},'student-internship/process-report/index.vue')
  late.vm.batchId=context.batchId;late.vm.internshipId=context.recordId
  const pending=late.vm.selectRecord({id:'42'});late.switchAccount();finish(detail);await pending
  assert.equal(late.vm.selectedDetail,null);assert.equal(late.vm.form.content,'')
})

test('process original read prevents attachment changes from being lost to the arriving detail',async()=>{
  let finish,chooseCalls=0
  const detail={id:'42',batchId:context.batchId,internshipId:context.recordId,reportType:'DAILY',periodKey:'2026-10-03',content:'原正文',status:'RETURNED',version:2,attachments:[metadata]}
  const p=page({getInternshipProcessReportDetail:()=>new Promise(resolve=>{finish=resolve})},
    {choose:async()=>{chooseCalls++;return metadata}},'student-internship/process-report/index.vue')
  p.vm.batchId=context.batchId;p.vm.internshipId=context.recordId;p.vm.form.attachments=[metadata]
  const pending=p.vm.selectRecord({id:'42'})
  await p.vm.addAttachment();p.vm.removeAttachment(0)
  assert.equal(chooseCalls,0);assert.equal(p.vm.form.attachments.length,1)
  finish(detail);await pending;assert.equal(p.vm.detailReading,false);assert.equal(p.vm.form.attachments.length,1)
})

test('process refresh keeps the editing version and draft until explicit conflict adoption',async()=>{
  let latest={id:'42',batchId:context.batchId,internshipId:context.recordId,reportType:'MONTHLY',periodKey:'2026-10',content:'原月报'.repeat(50),version:2,status:'RETURNED',reportVersion:1},calls=[]
  const p=page({getInternship:async()=>context,getInternshipProcessReports:async()=>({items:[latest]}),getInternshipProcessReportDetail:async()=>latest,
    submitInternshipProcessReport:async body=>{calls.push(body);latest={...latest,status:'PENDING_REVIEW',version:7};return latest}},{},'student-internship/process-report/index.vue')
  await p.vm.load();await p.vm.selectRecord(latest);p.vm.form.content='保留补正月报'.repeat(35)
  latest={...latest,version:6};await p.vm.load()
  assert.equal(p.vm.selectedDetail.version,2);assert.equal(p.vm.form.content,'保留补正月报'.repeat(35));assert.equal(p.vm.canSubmit,false)
  await p.vm.rereadConflict();assert.equal(p.vm.selectedDetail.version,2);assert.equal(p.vm.latestDetail.version,6)
  p.vm.continueAfterConflict();await p.vm.submit();assert.equal(calls[0].expectedVersion,6)
})

test('summary mobile review uses percent only, rejects empty input, and keeps explicit zero',async()=>{
  const calls=[],p=page({teacherInternshipProcessReportReview:async(...args)=>{calls.push(args)}},{},'teacher-internship/process-report-review/index.vue')
  const row={id:'42',reportType:'SUMMARY'};p.vm.state='ready';p.vm.batchId='18';p.vm.detail={'42':{version:3}};p.vm.load=async()=>{}
  p.vm.review(row,'APPROVE');assert.equal(p.sheet(),undefined);assert.equal(p.modal(),undefined)
  p.vm.reviewPanel.draft.summaryScore=' ';await p.vm.submitReview();assert.match(p.vm.reviewError,/0～100/);assert.equal(calls.length,0)
  p.vm.reviewPanel.draft.summaryScore='0';p.vm.reviewPanel.draft.comment='合成评分意见';await p.vm.submitReview()
  assert.equal(calls[0][2].summaryScore,0);assert.equal(calls[0][2].ratingLevel,null);assert.equal(calls[0][2].expectedVersion,3)
  p.vm.review(row,'APPROVE');p.vm.reviewPanel.draft.summaryScore='88';p.switchAccount();await p.vm.submitReview();assert.equal(calls.length,1)
})

test('review panel keeps input when closing or changing decision and validates before posting',async()=>{
  const calls=[],p=page({teacherInternshipProcessReportReview:async(...args)=>calls.push(args)},{},'teacher-internship/process-report-review/index.vue')
  const row={id:'42',reportType:'DAILY',studentName:'合成学生'};p.vm.state='ready';p.vm.batchId='18';p.vm.detail={'42':{version:3,status:'PENDING_REVIEW'}};p.vm.load=async()=>{}
  p.vm.review(row,'APPROVE');p.vm.reviewPanel.draft.comment='保留这段批阅意见';await p.vm.submitReview()
  assert.equal(calls.length,0);assert.match(p.vm.reviewError,/选择/)
  p.vm.setReviewRating(4);p.vm.closeReview();assert.equal(p.vm.reviewPanel,null)
  p.vm.review(row,'APPROVE');assert.equal(p.vm.reviewPanel.draft.ratingLevel,4);assert.equal(p.vm.reviewPanel.draft.comment,'保留这段批阅意见')
  p.vm.setReviewAction('RETURN');p.vm.reviewPanel.draft.comment='太短';await p.vm.submitReview();assert.equal(calls.length,0)
  p.vm.reviewPanel.draft.comment='请补充具体工作成果';await p.vm.submitReview()
  assert.equal(calls[0][2].action,'RETURN');assert.equal(calls[0][2].ratingLevel,null);assert.equal(calls[0][2].summaryScore,null)
})

test('review keyboard handles buttons and focus boundaries without consuming textarea newlines',()=>{
  const p=page({}, {}, 'teacher-internship/process-report-review/index.vue');let focused,clicks=0,prevented=0
  const first={tagName:'UNI-BUTTON',hasAttribute:()=>false,getClientRects:()=>[{}],focus(){focused=this},click(){clicks++}}
  const last={...first};p.vm.$refs.reviewSheet={querySelectorAll:()=>[first,last]}
  const key=(key,target,shiftKey=false)=>p.vm.onReviewKeydown({key,target,shiftKey,preventDefault(){prevented++}})
  key('Tab',last);assert.equal(focused,first);key('Tab',first,true);assert.equal(focused,last)
  key('Enter',first);key(' ',first);assert.equal(clicks,2)
  key('Enter',{tagName:'TEXTAREA'});assert.equal(prevented,4)
  p.vm.actingId='42';key('Enter',first);assert.equal(clicks,2)
})

test('review panel retains failed input and freezes commands while a request is pending',async()=>{
  let rejectRequest;const calls=[],pending=new Promise((_,reject)=>{rejectRequest=reject})
  const p=page({teacherInternshipProcessReportReview:(...args)=>{calls.push(args);return pending}},{},'teacher-internship/process-report-review/index.vue')
  const row={id:'42',reportType:'DAILY'};p.vm.state='ready';p.vm.batchId='18';p.vm.detail={'42':{version:3,status:'PENDING_REVIEW'}}
  p.vm.review(row,'APPROVE');p.vm.setReviewRating(5);p.vm.reviewPanel.draft.comment='保留原意见'
  const posting=p.vm.submitReview();p.vm.closeReview();p.vm.setReviewAction('RETURN');p.vm.setReviewRating(1);await p.vm.submitReview()
  assert.equal(calls.length,1);assert.equal(p.vm.reviewPanel.draft.action,'APPROVE');assert.equal(p.vm.reviewPanel.draft.ratingLevel,5)
  rejectRequest(new Error('网络中断'));await posting
  assert.equal(p.vm.actingId,'');assert.equal(p.vm.reviewPanel.draft.comment,'保留原意见');assert.match(p.vm.reviewError,/保留/)
  p.vm.closeReview();p.vm.detail['42'].version=7;p.vm.review(row,'APPROVE')
  assert.equal(p.vm.reviewPanel,null);assert.match(p.modal().title,/采用已核对/)
})

test('process history reads the focused bounded page and the remaining pages without replacing the draft',async()=>{
  const calls=[],detail={id:'old',batchId:context.batchId,internshipId:context.recordId,reportType:'DAILY',periodKey:'2026-10-01',content:'原正文',version:2,status:'RETURNED'}
  const p=page({getInternship:async()=>context,getInternshipProcessReports:async(...args)=>{
    calls.push(args);return {items:args[2]===2?[detail]:[],page:args[2],pageSize:20,total:60,focusPage:2}
  },getInternshipProcessReportDetail:async()=>detail},{},'student-internship/process-report/index.vue')
  p.vm.focusReportId='old';await p.vm.load()
  assert.deepEqual(calls.map(args=>args[2]),[1,2]);assert.equal(p.vm.selectedDetail.id,'old')
  p.vm.form.content='保留输入';await p.vm.loadMore()
  assert.deepEqual(calls.map(args=>args[2]),[1,2,3]);assert.equal(p.vm.hasMore,false);assert.equal(p.vm.form.content,'保留输入')
})

test('switching process type keeps text attachments and the original conflict version',async()=>{
  const p=page({}, {}, 'student-internship/process-report/index.vue'),vm=p.vm
  vm.loaded=true;vm.pageState='ready';vm.batchId=context.batchId;vm.internshipId=context.recordId;vm.prepareForm('DAILY')
  vm.form.content='并行B-报告未交正文';vm.form.attachments=[metadata];vm.conflict=true;vm.selectedDetail={id:'42',version:2,reportType:'DAILY',periodKey:vm.form.periodKey};vm.load=async()=>{}
  vm.pickType('MONTHLY');vm.form.content='另一类别待交正文';vm.pickType('DAILY')
  assert.equal(vm.form.content,'并行B-报告未交正文');assert.equal(vm.form.attachments[0].fileId,'f1')
  assert.equal(vm.selectedDetail.version,2);assert.equal(vm.conflict,true)
  p.switchAccount();p.component.onShow.call(vm);assert.deepEqual(vm.drafts,{})
})

test('process download is for the original id and cannot deliver after account changes',async()=>{
  let current;const p=page({downloadInternshipReportPdf:async(batch,record,kind,id,isCurrent)=>{
    assert.deepEqual([batch,record,kind,id],[context.batchId,context.recordId,'PROCESS','42']);current=isCurrent
  }},{},'student-internship/process-report/index.vue')
  p.vm.batchId=context.batchId;p.vm.internshipId=context.recordId;p.vm.selectedDetail={id:'42'}
  await p.vm.downloadReport();assert.equal(current(),true);p.switchAccount();assert.equal(current(),false)
})

test('teacher query uses selected type status and valid dates while omitting empty date values',()=>{
  const {vm}=page({}, {}, 'teacher-internship/process-report-review/index.vue')
  let loads=0;vm.load=()=>{loads++};vm.typeIndex=2;vm.statusIndex=3;vm.filters.keyword='合成学生'
  vm.queryReports();assert.equal(vm.appliedFilters.reportType,'MONTHLY');assert.equal(vm.appliedFilters.status,'')
  assert.equal(vm.appliedFilters.startDate,undefined);assert.equal(vm.appliedFilters.endDate,undefined)
  vm.filters.startDate='2026-10-05';vm.filters.endDate='2026-10-03';vm.queryReports();assert.equal(loads,1)
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

test('process report readonly originals cannot add or remove attachments',async()=>{
  for(const status of ['PENDING_REVIEW','APPROVED','RETURNED']) {
    let chooseCalls=0
    const original={id:'42',batchId:context.batchId,internshipId:context.recordId,reportType:'DAILY',periodKey:'2026-10-07',
      content:'并行B-报告原单正文',status,version:2,attachments:[metadata]}
    const p=page({getInternship:async()=>context,getInternshipProcessReports:async()=>({items:[original],total:1}),
      getInternshipProcessReportDetail:async()=>original},{metadata:async()=>metadata,choose:async()=>{chooseCalls++;return null}},'student-internship/process-report/index.vue')
    p.vm.form.periodKey=original.periodKey;await p.vm.load()
    await p.vm.addAttachment();p.vm.removeAttachment(0)
    assert.equal(chooseCalls,status==='RETURNED'?1:0)
    assert.equal(p.vm.form.attachments.length,status==='RETURNED'?0:1)
    assert.equal(p.vm.form.content,original.content)
  }
})

test('process load preserves draft and uses the normalized access or network state',async()=>{
  for(const pageState of ['forbidden','unauthorized','noLicense','offline']) {
    const p=page({getInternship:async()=>{throw {pageState}}},{},'student-internship/process-report/index.vue')
    p.vm.loaded=true;p.vm.form.content='并行B-报告保留输入';p.vm.form.attachments=[metadata]
    await p.vm.load()
    assert.equal(p.vm.pageState,pageState);assert.equal(p.vm.canSubmit,false)
    assert.equal(p.vm.form.content,'并行B-报告保留输入');assert.equal(p.vm.form.attachments.length,1)
    assert.equal(p.vm.loadError,'请求未完成')
  }
})

test('teacher failed context load clears old batch detail and private filters after account switch',async()=>{
  for(const pageState of ['forbidden','unauthorized','noLicense','offline']) {
    const store={can:()=>true,restore(){},load:async()=>{throw {pageState}}}
    const p=page({}, {}, 'teacher-internship/process-report-review/index.vue',store)
    Object.assign(p.vm,{batches:[{id:'old',name:'旧学校批次'}],batchId:'old',list:[{id:'old-report'}],
      detail:{'old-report':{content:'旧学生正文'}},expanded:'old-report',total:1,hasMore:true})
    p.vm.filters.keyword='旧学校学生';p.vm.appliedFilters={keyword:'旧学校学生'};p.switchAccount()
    await p.vm.load()
    assert.equal(p.vm.state,pageState);assert.equal(p.vm.loadError,'请求未完成')
    assert.deepEqual(p.vm.batches,[]);assert.equal(p.vm.batchId,'');assert.deepEqual(p.vm.list,[])
    assert.deepEqual(p.vm.detail,{});assert.equal(p.vm.expanded,'');assert.equal(p.vm.total,0);assert.equal(p.vm.hasMore,false)
    assert.equal(p.vm.filters.keyword,'');assert.deepEqual(p.vm.appliedFilters,{})
  }
})

test('a submitted process report stays readonly while another period opens without copying its body or files',async()=>{
  const original={id:'42',batchId:context.batchId,internshipId:context.recordId,reportType:'DAILY',periodKey:'2026-10-07',
    content:'已提交正文',status:'APPROVED',version:3,attachments:[metadata]}
  const p=page({getInternship:async()=>context,getInternshipProcessReports:async()=>({items:[original],total:1}),
    getInternshipProcessReportDetail:async()=>original},{metadata:async()=>metadata},'student-internship/process-report/index.vue')
  p.vm.form.periodKey=original.periodKey;await p.vm.load()
  assert.equal(p.vm.canEditReport,false);assert.equal(p.vm.canChangePeriod,true)
  await p.vm.changePeriod('2026-10-06')
  assert.equal(p.vm.form.periodKey,'2026-10-06');assert.equal(p.vm.form.content,'')
  assert.deepEqual(p.vm.form.attachments,[]);assert.equal(p.vm.selectedDetail,null);assert.equal(p.vm.canEditReport,true)
  await p.vm.changePeriod('2026-10-07')
  assert.equal(p.vm.canEditReport,false);assert.equal(p.vm.form.content,original.content)
})

test('switching the process period restores the original draft and keeps its old conflict version',async()=>{
  const original={id:'42',batchId:context.batchId,internshipId:context.recordId,reportType:'DAILY',periodKey:'2026-10-07',
    content:'原单正文',status:'RETURNED',version:2,attachments:[]}
  const p=page({getInternship:async()=>context,getInternshipProcessReports:async()=>({items:[original],total:1}),
    getInternshipProcessReportDetail:async()=>original},{metadata:async()=>metadata},'student-internship/process-report/index.vue')
  p.vm.form.periodKey=original.periodKey;await p.vm.load()
  p.vm.form.content='并行B-报告保留补正';p.vm.form.attachments=[metadata]
  await p.vm.changePeriod('2026-10-06')
  p.vm.form.content='另一日期草稿'
  original.version=5
  await p.vm.changePeriod('2026-10-07')
  assert.equal(p.vm.form.content,'并行B-报告保留补正');assert.equal(p.vm.form.attachments[0].fileId,'f1')
  assert.equal(p.vm.selectedDetail.version,2);assert.equal(p.vm.latestDetail.version,5);assert.equal(p.vm.conflict,true)
  p.vm.submitting=true;await p.vm.changePeriod('2026-10-05');assert.equal(p.vm.form.periodKey,'2026-10-07')
})

test('周报批阅弹层保留取消草稿，校验理由和评级，阻止重复与过期上下文提交',async()=>{
  let finish; const calls=[];const p=teacherReviewPage({reviewWeekly:(...args)=>{calls.push(args);return new Promise(resolve=>{finish=resolve})}})
  const row={id:'51',student:'测试同学',week:'第1周',expectedVersion:7,_body:'ready'};p.vm.data.reports=[row]
  p.vm.review(row,'return');p.vm.weeklyReviewPanel.draft.comment='不足';await p.vm.submitWeeklyReview();assert.equal(calls.length,0);assert.match(p.vm.weeklyReviewError,/至少/)
  p.vm.weeklyReviewPanel.draft.comment='请补充测试结果';p.vm.closeWeeklyReview();p.vm.review(row,'return');assert.equal(p.vm.weeklyReviewPanel.draft.comment,'请补充测试结果')
  p.vm.setWeeklyReviewType('pass');await p.vm.submitWeeklyReview();assert.equal(calls.length,0);assert.match(p.vm.weeklyReviewError,/五级/)
  p.vm.weeklyReviewPanel.draft.ratingLevel=4;const pending=p.vm.submitWeeklyReview();await p.vm.submitWeeklyReview();assert.equal(calls.length,1)
  p.vm.invalidateReads();p.vm.hidden=false;p.vm.batchId='another';finish({status:'APPROVED'});await pending;assert.equal(p.vm.weeklyReceipt,null)
})
test('周报回执绑定当前原单，切周后不会显示其他周的提交成功',async()=>{
  const {vm}=page();Object.assign(vm,{loaded:true,state:'ready',batchId:'18',internshipId:'18',selectedWeek:1,currentWeek:2,detailState:'ready'})
  vm.weeklyList=[report({id:'77',week:1,status:'PENDING_REVIEW',statusLabel:'待批阅'}),report({id:'78',week:2,status:'PENDING_REVIEW',statusLabel:'待批阅'})]
  vm.receipt={id:'77',version:1,title:'本次提交回执',nextStep:'等待教师'}
  const view=weeklyPresentation(vm);assert.match(await view.html(),/本次提交回执/);vm.selectedWeek=2;assert.doesNotMatch(await view.html(),/本次提交回执/)
})
