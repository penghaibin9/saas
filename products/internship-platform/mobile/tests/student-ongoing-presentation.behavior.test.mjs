import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import * as readiness from '../src/services/fileReadiness.mjs'
import * as reports from '../src/services/weeklyReportPresentation.mjs'
import { formatDateTime } from '../src/utils/format.js'

function page(name) {
  const source=fs.readFileSync(new URL(`../src/pages/student-internship/${name}/index.vue`,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm,'').replace('export default','return')
  const deps={currentSessionGeneration:()=>0,formatDateTime,MobileInlineAlert:{},ReportFilePreview:{},currentMobileSession:()=>({identity:{userId:'1',tenantId:'2'}}),...readiness,...reports}
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...component.data(),$refs:{}}
  for(const [name,fn]of Object.entries(component.methods||{}))vm[name]=fn.bind(vm)
  for(const [name,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,name,{get:fn.bind(vm)})
  vm.state='ready';vm.pageState='ready';vm.context={batchId:'18',internshipId:'21'};vm.requestedBatchId='18'
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const components={MobileNavBar:{props:['title','fallbackUrl'],setup:p=>()=>h('nav',{'data-return':p.fallbackUrl},p.title)},MobilePrivacyGate:{render:()=>null},ReportFilePreview:{render:()=>null},
    MobileGlobalState:{props:['state','title','description'],setup:(p,{slots})=>()=>p.state==='ready'?h('div',slots.default?.()):h('section',[p.title,p.description])},
    MobileInlineAlert:{props:['title','description'],setup:p=>()=>h('p',[p.title,p.description])},MobileStatusTag:{props:['status','label'],setup:p=>()=>h('span',p.label||p.status)},
    MobileSafeAreaBar:{setup:(_,{slots})=>()=>h('footer',slots.default?.())}}
  const render=compile(template,{isCustomElement:tag=>['view','text','picker','image'].includes(tag)})
  const events=compile(template,{isCustomElement:tag=>['view','text','picker','image'].includes(tag)||/^[A-Z]/.test(tag)})
  return {vm,html:()=>renderToString(createSSRApp({components,render:()=>render(vm,[])})),tree:async()=>{let tree;await renderToString(createSSRApp({render:()=>{tree=events(vm,[]);return tree}}));return tree}}
}
function nodes(node,predicate,result=[]) {if(!node||typeof node!=='object')return result;if(predicate(node))result.push(node);for(const child of Array.isArray(node.children)?node.children:[])nodes(child,predicate,result);return result}

test('在岗呈现补卡保留原草稿与扫描禁提交，弹层打开时隐藏底栏',async()=>{
  const p=page('makeup');p.vm.form={checkinDate:'2026-10-11',makeupType:'OUT_OF_RANGE',reason:'原超范围补卡说明',evidenceFileId:'',fileName:'原凭证.pdf'};p.vm.makeupTypeIndex=1
  p.vm.pendingEvidence={fileId:'236',statusText:'安全扫描中',readyForBusiness:false};p.vm.openApply()
  let html=await p.html();assert.match(html,/原超范围补卡说明/);assert.match(html,/安全扫描中/);assert.match(html,/定位异常补卡必须上传/);assert.doesNotMatch(html,/新建补卡申请/)
  assert.equal(nodes(await p.tree(),n=>n.type==='button'&&n.props?.onClick===p.vm.submit)[0].props.disabled,true)
  p.vm.closeForm();html=await p.html();assert.match(html,/新建补卡申请/);assert.equal(p.vm.form.reason,'原超范围补卡说明');assert.equal(p.vm.pendingEvidence.fileId,'236')
  assert.match(html,/pages\/student-internship\/index\?batchId=18/)
})

test('在岗呈现求助已关闭进度优先，已转人工历史可展开且活动咨询评价常显',async()=>{
  const p=page('help');p.vm.support={...p.vm.support,sessionId:'7',answerVersion:1,status:'TRANSFERRED',transferredRiskId:'10',history:[{question:'用户原始提问',answer:'原始答复'}]};p.vm.records=[{id:'10',title:'原人工求助',status:'CLOSED',latestFeedback:'学校已查明并关闭',updatedAt:'2026-10-13T03:19:00Z'}]
  let html=await p.html();assert.ok(html.indexOf('学校已查明并关闭')<html.indexOf('常见问题'));assert.match(html,/已关闭/);assert.doesNotMatch(html,/用户原始提问|原始答复/)
  nodes(await p.tree(),n=>n.type==='button'&&n.props?.['aria-expanded']===false)[0].props.onClick();html=await p.html();assert.match(html,/用户原始提问/);assert.match(html,/原始答复/);assert.equal(p.vm.support.status,'TRANSFERRED')
  p.vm.support={...p.vm.support,status:'ACTIVE',answerVersion:2,awaitingFeedback:true,unresolvedCount:1,remainingBeforeHuman:2};html=await p.html()
  for(const text of ['用户原始提问','原始答复','没解决','已解决','1/3','直接人工求助'])assert.ok(html.includes(text),text)
  assert.ok(!html.includes('提交人工求助'));p.vm.manualOpen=true;html=await p.html();assert.ok(html.includes('提交人工求助'))
  assert.equal(nodes(await p.tree(),n=>n.type==='button'&&n.props?.onClick===p.vm.askSupport)[0].props.disabled,true)
})

test('在岗呈现反馈保留级别图片原记录处理意见，历史只读不能提交',async()=>{
  const p=page('feedback');p.vm.records=[{id:'8',title:'原反馈',feedbackLevel:'DEPARTMENT',status:'ACCEPTED',content:'原反馈正文',conclusion:'学校处理意见原文',imageFileIds:['9']}];p.vm.form={title:'原未交标题',content:'原未交内容',images:[{fileId:'11',fileName:'原图片.png'}]}
  let html=await p.html();for(const text of ['原反馈正文','学校处理意见原文','撤回反馈','反馈级别','原未交标题','原图片.png','提交意见反馈'])assert.ok(html.includes(text),text)
  assert.doesNotMatch(html,/学校会在现有受理台账中跟进/);assert.match(html,/pages\/student-internship\/index\?batchId=18/)
  p.vm.historyMode=true;html=await p.html();assert.doesNotMatch(html,/提交意见反馈|撤回反馈/);assert.match(html,/原反馈正文/);assert.equal(p.vm.form.content,'原未交内容')
})

test('在岗呈现过程报告三类型保留模板字数扫描和原单冲突，空历史不重复零计数',async()=>{
  const p=page('process-report');p.vm.loaded=true;p.vm.batchId='18';p.vm.internshipId='21'
  for(const [type,label,min,section]of [['DAILY','日报',30,''],['MONTHLY','月报',100,'五、下月计划：'],['SUMMARY','实习总结',300,'四、不足与改进：']]){
    p.vm.reportType=type;p.vm.prepareForm(type);const original=p.vm.form.content
    if(section)assert.ok(original.includes(section));else assert.equal(original,'')
    assert.equal(p.vm.minimum,min);let html=await p.html();assert.ok(html.includes(`<nav data-return="/pages/student-internship/index?batchId=18" show-back>${label}</nav>`));assert.ok(html.includes(`至少 ${min} 字`));assert.doesNotMatch(html,/已读取 0 \/ 0 篇/)
    assert.equal(p.vm.canSubmit,false);p.vm.form.content='正'.repeat(min);assert.equal(p.vm.canSubmit,true)
    p.vm.form.attachments=[{fileId:'51',fileName:'原报告附件',statusText:'安全扫描中',readyForBusiness:false}];assert.equal(p.vm.canSubmit,false);assert.match(await p.html(),/附件安全就绪前不能提交/)
  }
  p.vm.form.attachments=[];p.vm.reports=[{id:'77',reportType:'SUMMARY',periodKey:'FINAL',status:'RETURNED',statusLabel:'已退回',reviewComment:'请补充工作成果',reportVersion:2}];p.vm.selectedDetail={id:'77',reportVersion:2,statusLabel:'已退回',review:{summaryScore:0},immutableVersions:[]};p.vm.conflict=true
  const html=await p.html();for(const text of ['请补充工作成果','总结评分：0分','读取最新原单核对','下载当前提交版报告文书'])assert.ok(html.includes(text),text);assert.equal(p.vm.canSubmit,false)
})

test('在岗呈现轮岗工资保留零值历史审核意见及原更正入口',async()=>{
  const p=page('process-facts');let html=await p.html();assert.match(html,/暂无轮岗安排/);assert.match(html,/暂无工资单/);assert.match(html,/新增本月工资单/);assert.doesNotMatch(html,/按月份留版本/)
  p.vm.payrolls=[{id:'31',payMonth:'2026-10',agreedSalary:0,agreedSalaryCurrency:'CNY',current:{id:'51',actualAmount:0,currency:'CNY',revisionNo:2,status:'RETURNED',statusLabel:'已退回',reviewComment:'请补工资凭证',evidenceFileId:'61'},history:[{id:'50',revisionNo:1,statusLabel:'已更正',actualAmount:10,currency:'CNY'},{id:'51',revisionNo:2,statusLabel:'已退回',actualAmount:0,currency:'CNY'}]}]
  p.vm.rotations=[{id:'41',rotationSeq:1,departmentName:'合成科室',status:'COMPLETED',projects:[],scores:{theory:0,skill:null,mentor:null,total:0},studentSelfEvaluation:'原部门自评',studentSelfRating:3}]
  html=await p.html();for(const text of ['人民币 0.00','第2版','请补工资凭证','查看工资凭证','更正工资单','查看历史版本','原部门自评','0.0','—'])assert.ok(html.includes(text),text)
  p.vm.openPayroll(p.vm.payrolls[0]);assert.equal(p.vm.payrollForm.actualAmount,'0');assert.equal(p.vm.payrollForm.statementId,'31');assert.equal(p.vm.payrollForm.payMonth,'2026-10');assert.match(await p.html(),/更正原因（至少5字）/)
})

test('在岗呈现变更保留审批影响拒绝理由与原单版本，无更多数据时收起无效分页',async()=>{
  const p=page('change');p.vm.context={batchId:'18',recordId:'21',company:'原企业',post:'原岗位',batch:'原批次名',statusText:'READY'}
  let html=await p.html();assert.match(html,/原企业/);assert.match(html,/原岗位/);assert.doesNotMatch(html,/原批次名|上一页岗位|下一页记录/)
  nodes(await p.tree(),n=>n.type==='button'&&n.props?.['aria-expanded']===false)[0].props.onClick();html=await p.html();assert.match(html,/原批次名/);assert.match(html,/实习记录编号 21/)
  p.vm.targetHasMore=true;p.vm.historyHasMore=true;p.vm.targets=[{id:'91',title:'不可申请岗位',companyName:'目标企业',remaining:0,canSelect:false,selectionReason:'名额已满'}];p.vm.editing={id:'71',version:8,reviewComment:'请补变更原因'};p.vm.formError='申请或岗位已变化，请重新读取后核对'
  html=await p.html();for(const text of ['上一页岗位','下一页记录','名额已满','第 8 版','请补变更原因','申请或岗位已变化','原企业导师权限停止','原知情确认与协议失效','重新合规前不能打卡'])assert.ok(html.includes(text),text)
  assert.equal(nodes(await p.tree(),n=>n.type==='button'&&String(n.props?.class||'').includes('sc__target'))[0].props.disabled,true)
})

test('在岗呈现鉴定首次表单全部可填，审核退回版本及正式零分申诉不丢失',async()=>{
  const p=page('self-eval');p.vm.loaded=true;p.vm.dashboard={batchId:'2673',recordId:'722',statusText:'READY'}
  let html=await p.html();for(const text of ['实习鉴定','尚未提交','提交自评','指导教师填写意见','企业、导师评价齐备','实习总结','至少20字','主要收获','存在问题','对企业评分','对企业评价','对岗位评分','对岗位评价'])assert.ok(html.includes(text),text)
  assert.match(html,/pages\/student-internship\/index\?batchId=2673/);assert.doesNotMatch(html,/修改并重新提交/)
  let tree=await p.tree();assert.equal(nodes(tree,n=>n.type==='textarea').length,5);assert.ok(nodes(tree,n=>n.type==='textarea').every(n=>n.props.disabled===false))
  const ratings=nodes(tree,n=>n.type==='picker');assert.equal(ratings.length,2);ratings[0].props.onChange({detail:{value:1}});ratings[1].props.onChange({detail:{value:4}});assert.equal(p.vm.form.enterpriseRating,2);assert.equal(p.vm.form.positionRating,5)
  p.vm.evalData={id:'71',version:8,submitStatus:'SUBMITTED',reviewStatus:'PENDING',reviewStatusLabel:'待审核'};html=await p.html();assert.match(html,/记录版本 8/);assert.match(html,/鉴定正在审核/);assert.doesNotMatch(html,/修改并重新提交/);assert.ok(nodes(await p.tree(),n=>n.type==='textarea').every(n=>n.props.disabled===true))
  p.vm.evalData={...p.vm.evalData,reviewStatus:'RETURNED',reviewStatusLabel:'已退回',reviewComment:'请补实际工作成果'};p.vm.conflictText='第8版已有变化，请核对原单';html=await p.html();assert.match(html,/版本已变化，草稿已保留/);assert.match(html,/第8版已有变化/)
  p.vm.conflictText='';html=await p.html();assert.match(html,/请补实际工作成果/);assert.match(html,/修改并重新提交/)
  p.vm.dashboard.score={totalScore:0,isPass:false,checkinScore:0,weeklyScore:null,monthlyScore:null,enterpriseScore:null,schoolScore:null};html=await p.html();assert.match(html,/正式成绩已发布/);assert.match(html,/打卡 0/);assert.match(html,/周报 —/);assert.match(html,/提交成绩申诉/)
  p.vm.evalData.reviewStatus='APPROVED';assert.equal(p.vm.readonly,true)
})
