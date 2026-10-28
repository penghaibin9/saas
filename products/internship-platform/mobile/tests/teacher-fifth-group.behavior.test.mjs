import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { formatDateTime } from '../src/utils/format.js'
import { normalizeError, request } from './request-module.mjs'
import * as positions from '../src/modules/internshipPositionModel.js'

const batch='9007199254740993001'

test('只读志愿原单折叠正文但保留版本结果附件，消息返回受控且切对象重置',async()=>{
  const links=[],files=[],p=page('internship-volunteers',{uni:{redirectTo:({url})=>links.push(url)}})
  p.vm.scope={...p.vm.scope,batchId:batch,campaignId:'31',groupId:'32'};p.vm.fromMessages=true
  p.vm.detail={id:'32',status:'APPROVED',studentName:'原学生',submissionVersion:2,volunteers:[{id:'33',volunteerNo:1,positionName:'原岗位',companyName:'原企业',applicationStatement:'原申请说明全文',enterpriseDecision:{status:'ACCEPT_INTENT',effectStatus:'CONSUMED'}}],material:{submissionVersion:2,profileSnapshot:{profile:{selfIntro:'原版本材料正文'},items:[]},attachmentFileIds:['9007199254740993019']},decisionHistory:[{id:'34',applicationId:'33',submissionVersion:2,status:'ACCEPT_INTENT',effectStatus:'CONSUMED',reason:'原企业处理理由'}]}
  const before=JSON.stringify(p.vm.detail);p.vm.openFile=id=>files.push(id)
  let view=await p.snapshot();for(const text of ['原学生','原岗位','第 2 次投递','已用于确认','返回消息'])assert.ok(view.html.includes(text),text)
  for(const text of ['原申请说明全文','原版本材料正文','原企业处理理由'])assert.ok(!view.html.includes(text),text)
  view.nodes.find(n=>n.type==='button'&&String(n.children).includes('查看申请说明')).props.onClick()
  view.nodes.find(n=>n.type==='button'&&String(n.children).includes('查看本次材料')).props.onClick()
  view.nodes.find(n=>n.type==='button'&&String(n.children).includes('查看处理详情')).props.onClick()
  view=await p.snapshot();for(const text of ['原申请说明全文','原版本材料正文','原企业处理理由'])assert.ok(view.html.includes(text),text)
  view.nodes.find(n=>n.type==='button'&&String(n.children).includes('查看投递附件')).props.onClick();assert.deepEqual(files,['9007199254740993019']);assert.equal(JSON.stringify(p.vm.detail),before)
  p.vm.returnToList();assert.deepEqual(links,['/pages/teacher-internship/messages/index'])
  p.component.onHide.call(p.vm);assert.equal(p.vm.materialOpen,false);assert.equal(p.vm.historyOpen,false);assert.deepEqual(p.vm.statementOpen,{})
})

test('保险队列超过100条仍可分页核对，失败保留名单，旧批次后页不能追加',async()=>{
  const calls=[];let fail=false,waiting,resolve
  const p=page('insurance-verify',{teacherInternshipInsurancePending:async(id,page=1,size=20)=>{
    calls.push([id,page,size]);if(waiting)return waiting;if(fail)throw Error('后页暂不可用')
    return {items:Array.from({length:Math.min(size,101-(page-1)*size)},(_,i)=>({id:String((page-1)*size+i+1),hasFile:true})),total:101}
  }})
  await p.vm.load();assert.equal(p.vm.list.length,20);assert.equal(p.vm.total,101);assert.equal(p.vm.hasMore,true)
  fail=true;await p.vm.loadMore();assert.equal(p.vm.list.length,20);assert.equal(p.vm.page,1);assert.ok(p.vm.loadMoreError)
  fail=false;while(p.vm.hasMore)await p.vm.loadMore();assert.equal(p.vm.list.length,101);assert.equal(p.vm.page,6);assert.equal(calls.at(-1)[1],6)
  await p.vm.load();waiting=new Promise(done=>resolve=done);const pending=p.vm.loadMore();p.vm.hidden=true;p.vm.loadSeq++;p.vm.loadingMore=false
  resolve({items:[{id:'wrong-batch'}],total:101});await pending;assert.ok(!p.vm.list.some(item=>item.id==='wrong-batch'));assert.equal(p.vm.page,1)
})
function page(name,overrides={}){
  const source=fs.readFileSync(new URL(`../src/pages/teacher-internship/${name}/index.vue`,import.meta.url),'utf8'),links=[],calls=[]
  const context={selectedBatchId:batch,batches:[{id:batch,name:'合成批次'}],selectedBatch:{name:'合成批次'},can:()=>true,restore(){},load:async()=>{}}
  const deps={...positions,ReportFilePreview:{},formatDateTime,currentSessionGeneration:()=>1,useInternshipContextStore:()=>context,toast:()=>{},
    teacherInternshipProcurementStats:async id=>{calls.push(id);return {groups:[],scope:{recordCount:0}}},go:path=>links.push(path),normalizeError,...overrides}
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm=component.data()
  for(const [key,fn] of Object.entries(component.methods))vm[key]=fn.bind(vm)
  for(const [key,fn] of Object.entries(component.computed||{}))Object.defineProperty(vm,key,{get:fn.bind(vm)})
  vm.state='ready';vm.batches=context.batches;vm.batchId=batch
  const template=source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1],render=new Function('Vue',compile(template,{prefixIdentifiers:true,isCustomElement:()=>true}).code)(Vue)
  async function snapshot(){const nodes=[],walk=n=>{if(!n||typeof n!=='object')return;nodes.push(n);if(Array.isArray(n.children))n.children.forEach(walk)};const html=await renderToString(Vue.createSSRApp({render(){const tree=render(vm,[]);walk(tree);return tree}}));return {html,nodes}}
  return {vm,component,context,links,calls,snapshot}
}
const hasClass=(node,name)=>String(node.props?.class||'').split(/\s+/).includes(name)

test('工资列表仅提供当前版本时，已确认意见仍可展开，金额零和退回原因保留',async()=>{
  const {vm,snapshot}=page('payroll-review');vm.list=[{id:'1',studentName:'合成学生',payMonth:'2026-10',current:{id:'v1',status:'APPROVED',statusLabel:'已确认',revisionNo:3,actualAmount:0,currency:'CNY',correctionReason:'原工资更正原因',reviewComment:'原工资审核意见'}}]
  let view=await snapshot();assert.ok(view.html.includes('0.00'));assert.ok(!view.html.includes('原工资审核意见'));assert.ok(!view.html.includes('原工资更正原因'))
  view.nodes.find(n=>n.type==='button'&&String(n.children).includes('查看审核详情')).props.onClick();view=await snapshot();assert.ok(view.html.includes('原工资审核意见'));assert.ok(view.html.includes('原工资更正原因'))
  vm.historyOpen={};vm.list[0].current.status='RETURNED';view=await snapshot();assert.ok(view.html.includes('原工资审核意见'));assert.ok(view.html.includes('原工资更正原因'))
})

test('教师协议统计评价鉴定成绩从授权原批次深链进入，不能读旧批次或越范围兜底',async()=>{
  const target='9007199254740993002'
  for(const name of ['agreement-confirm','school-stats','enterprise-eval','student-eval','internship-score','insurance-verify','payroll-review','plan-task-review','internship-risk']){
    const reads=[],read=async id=>{reads.push(id);return {items:[],total:0,groups:[],scope:{recordCount:0}}}
    const p=page(name,{createSubmitLock:request.createSubmitLock,useSessionStore:()=>({identity:{userId:'u1'}}),teacherInternshipAgreements:read,teacherInternshipProcurementStats:read,teacherInternshipEnterpriseEvals:read,teacherInternshipStudentEvals:read,teacherInternshipScores:read,teacherInternshipInsurancePending:read,teacherInternshipPayroll:read,teacherInternshipPlanTasks:read,teacherApi:{getInternshipRisks:query=>read(query.batchId)}})
    p.context.batches.push({id:target,name:'原单批次'});p.context.selectBatch=id=>{if(!p.context.batches.some(b=>b.id===id))return false;p.context.selectedBatchId=id;return true}
    const load=p.vm.load;p.vm.load=()=>{};p.component.onLoad.call(p.vm,{batchId:target});p.vm.load=load;await load()
    assert.equal(p.vm.batchId,target,name);assert.deepEqual(reads,[target],name);assert.equal(p.vm.requestedBatchId,'',name)
    reads.length=0;p.vm.requestedBatchId='9007199254740993999';await load();assert.deepEqual(reads,[],name);assert.ok(['error','forbidden'].includes(p.vm.state),name)
  }
})

test('移动任务身份失权显示权限拒绝并清除旧行，不误报空队列或系统失败',async()=>{
  const p=page('plan-task-review',{teacherInternshipPlanTasks:async()=>{throw {httpStatus:403,message:'当前身份无权查看任务'}}})
  p.vm.list=[{id:'old',studentName:'旧身份学生'}];await p.vm.load()
  assert.equal(p.vm.state,'forbidden');assert.deepEqual(p.vm.list,[])
})

test('保险查看身份保留凭证入口，隐藏核验操作且旧审核面板失权后不能提交',async()=>{
  let writes=0
  const p=page('insurance-verify',{teacherInternshipInsuranceVerify:async()=>{writes++}})
  p.context.can=code=>code==='internship.insurance.view'
  const item={id:'insurance-1',version:2,studentName:'原学生',fileId:'file-1',hasFile:true}
  p.vm.list=[item]
  const view=await p.snapshot()
  assert.ok(view.html.includes('查看原始保单凭证'));assert.ok(view.html.includes('当前仅可查阅'))
  assert.ok(!view.nodes.some(node=>hasClass(node,'iv__approve')||hasClass(node,'iv__reject')))
  p.vm.verify(item,'REJECT');assert.equal(p.vm.review,null)
  p.vm.review={...item,action:'REJECT',comment:'补充保险材料',seq:p.vm.loadSeq,batchId:p.vm.batchId}
  await p.vm.submitReview();assert.equal(writes,0)
})

test('指导覆盖2比1空比率显示口径待核对，零分母真零及其他指标保持',async()=>{
  const {vm,snapshot}=page('school-stats')
  for(const [item,label] of [
    [{key:'guidanceCoverRate',numerator:2,denominator:1,rate:null},'口径待核对'],
    [{key:'guidanceCoverRate',numerator:2,denominator:0,rate:null},'暂无数据'],
    [{key:'guidanceCoverRate',numerator:0,denominator:2,rate:0},'0%'],
    [{key:'guidanceCoverRate',numerator:1,denominator:2,rate:50},'50%'],
    [{key:'guidanceCoverRate',numerator:1,denominator:1,rate:100},'100%'],
    [{key:'guidanceCoverRate',numerator:0,denominator:2,rate:null},'暂无数据'],
    [{key:'otherMetric',numerator:2,denominator:1,rate:null},'暂无数据']
  ]){const before=JSON.stringify(item);assert.equal(vm.rateText(item),label);assert.equal(JSON.stringify(item),before)}
  vm.data={scope:{recordCount:2},groups:[{key:'activity',label:'过程活动',metrics:[{key:'guidanceCoverRate',label:'指导覆盖率',numerator:2,denominator:1,rate:null,note:'正常指导记录覆盖。'}]}],metricDefinitions:{}}
  const before=JSON.stringify(vm.data),view=await snapshot()
  assert.ok(view.html.includes('口径待核对')&&view.html.includes('2 / 1'))
  assert.equal(JSON.stringify(vm.data),before)
})

test('协议空态去重复零统计，正向材料双方确认与学校终审责任保留',async()=>{
  const {vm,snapshot}=page('agreement-confirm');vm.list=[];let view=await snapshot()
  assert.ok(!view.nodes.some(n=>hasClass(n,'ac__summary')))
  vm.list=[{id:'9',studentName:'合成学生',studentNo:'0001',enterpriseName:'原企业',positionName:'原岗位',studentConfirmLabel:'已确认',enterpriseConfirmLabel:'待确认',hasFile:false,sourceLabel:'原纸质来源',version:2}]
  view=await snapshot()
  for(const text of ['原企业','原岗位','学生确认','企业确认','签署扫描件','未上传','终审由学校办理','原纸质来源'])assert.ok(view.html.includes(text),text)
  assert.ok(!view.nodes.some(n=>n.type==='button'&&/通过|终审/.test(String(n.children))))
})

test('任务确认保留完成说明证据版本与缺件提示，空队列不铺零统计',async()=>{
  const {vm,snapshot}=page('plan-task-review');vm.list=[];let view=await snapshot()
  assert.ok(!view.nodes.some(n=>hasClass(n,'pt__summary')))
  vm.list=[{id:'3',studentName:'合成学生',studentNo:'0001',statusLabel:'待确认',taskSortOrder:1,taskName:'原计划任务',taskRequirement:'原任务要求与验收标准',taskDeadline:'2026-12-31',studentNote:'原完成说明',version:0,submittedAt:'2026-10-13T01:00:00Z'}]
  view=await snapshot()
  for(const text of ['原计划任务','原任务要求与验收标准','截止 2026-12-31','原完成说明','当前版本 0','未上传完成凭证','需要凭证时应退回补充'])assert.ok(view.html.includes(text),text)
})

test('指导精简重复对象卡但选中学生、输入、扫描与风险前置完整',async()=>{
  const {vm,snapshot}=page('internship-guidance');vm.students=[{id:'9007199254740993002',name:'合成学生',studentNo:'00001',enterpriseName:'原企业'}];vm.total=21
  vm.content='原未保存指导内容';vm.guidanceDate='2026-10-13';vm.toRisk=true;vm.notifyCounselor=true;vm.photo={fileId:'220',fileName:'原证明',readyForBusiness:false,statusText:'扫描中'}
  const before=JSON.stringify({content:vm.content,guidanceDate:vm.guidanceDate,toRisk:vm.toRisk,notifyCounselor:vm.notifyCounselor,photo:vm.photo})
  const view=await snapshot()
  for(const text of ['合成学生','00001','原企业','原未保存指导内容','2026-10-13','同步生成风险单','原证明','扫描中','加载更多学生'])assert.ok(view.html.includes(text),text)
  assert.ok(!view.nodes.some(n=>hasClass(n,'ig__selected')))
  assert.equal(view.nodes.find(n=>n.type==='button'&&String(n.children)==='保存指导记录').props.disabled,true)
  assert.equal(JSON.stringify({content:vm.content,guidanceDate:vm.guidanceDate,toRisk:vm.toRisk,notifyCounselor:vm.notifyCounselor,photo:vm.photo}),before)
})

test('统计中文展示不改比率分母金额，拒绝普通导师且口径按需展开',async()=>{
  const {vm,context,snapshot,calls}=page('school-stats');context.can=()=>false;await vm.load();assert.equal(vm.state,'forbidden');assert.deepEqual(calls,[])
  context.can=()=>true;vm.state='ready';vm.data={scope:{recordCount:2},groups:[{key:'overview',label:'学校概况',ratios:[{key:'accountBindingRate',label:'账号绑定率',numerator:1,denominator:2,rate:50,note:'ACTIVE StudentAccountLink',source:'t_student_account_link'},{key:'wechatBindingRate',label:'微信绑定率',numerator:0,denominator:1,rate:0}]},{key:'activity',label:'活动',metrics:[{key:'reportTaskCompletionRate',label:'报告完成',rate:null,numerator:0,denominator:0,note:'按学生实习周期推算'}],weeklyReportTasks:{frequency:'WEEKLY',expected:0,submitted:0}},{key:'quality',label:'质量',wageByCurrency:[{currency:'CNY',averageActualAmount:0,totalActualAmount:0,count:1}]}],metricDefinitions:{majorMatch:'major_match',transfer:'APPROVED 变更',wage:'APPROVED 工资',excellent:'PUBLISHED 总成绩>=90',reportCompletion:'周期乘频率'}}
  const before=JSON.stringify(vm.data);let view=await snapshot()
  for(const text of ['50%','0%','暂无数据','1 / 2','0 / 0','人民币 0.00'])assert.ok(view.html.includes(text),text)
  assert.ok(!view.html.includes('按本批次应交报告要求统计'))
  for(const text of ['StudentAccountLink','ACTIVE','major_match','APPROVED','PUBLISHED','t_student_account_link'])assert.ok(!view.html.includes(text),text)
  assert.equal(vm.definitionsOpen,false);view.nodes.find(n=>hasClass(n,'ss__toggle')).props.onClick();assert.equal(vm.definitionsOpen,true)
  view=await snapshot();assert.ok(view.html.includes('按本批次应交报告要求统计'));assert.ok(view.html.includes('已有效绑定校园账号的学生比例'))
  assert.equal((view.html.match(/按本批次应交报告要求统计/g)||[]).length,1)
  vm.data.groups.push({key:'shared',metrics:[{key:'guidanceCoverRate',label:'指导覆盖率',note:'共同分母说明'},{key:'visitCoverRate',label:'巡访覆盖率',note:'共同分母说明'}]});view=await snapshot();assert.ok(view.html.includes('指导覆盖率、巡访覆盖率'));assert.equal((view.html.match(/共同分母说明/g)||[]).length,1);vm.data.groups.pop()
  for(const text of ['StudentAccountLink','ACTIVE','major_match','APPROVED','PUBLISHED','t_student_account_link'])assert.ok(!view.html.includes(text),text)
  assert.equal(JSON.stringify(vm.data),before);assert.equal(vm.rateText({denominator:2,rate:null}),'暂无数据')
})

test('有权岗位列表保留筛选岗位事实余量及原详情批次路径',async()=>{
  const {vm,snapshot,links}=page('internship-positions');vm.total=2;vm.rows=[{id:'9007199254740993002',title:'原岗位',companyName:'原企业',statusLabel:'已上架',statusTone:'success',workLocation:'原地点',majorRequirement:'原专业要求',salaryRange:'原报酬条件',remaining:0,headcount:2}]
  const view=await snapshot();for(const text of ['原岗位','原企业','原地点','原专业要求','原报酬条件','剩余 0 / 2 人','2 个岗位','招聘季范围和学生资格'])assert.ok(view.html.includes(text),text)
  view.nodes.find(n=>hasClass(n,'ip__position')).props.onClick()
  assert.ok(links[0].includes('id=9007199254740993002')&&links[0].includes('batchId='+batch))
})
