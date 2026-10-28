import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { formatDateTime } from '../src/utils/format.js'
import { normalizeError } from './request-module.mjs'
import * as reports from '../src/services/weeklyReportPresentation.mjs'
import * as employment from '../src/services/employmentPresentation.mjs'

const batch='9007199254740993001',record='9007199254740993002'
function page(name,overrides={}){
  const source=fs.readFileSync(new URL(`../src/pages/teacher-internship/${name}.vue`,import.meta.url),'utf8')
  const links=[],context={selectedBatchId:batch,batches:[{id:batch,name:'合成批次'}],selectedBatch:{name:'合成批次'},roleCode:'INTERN_MENTOR',can:()=>true,restore(){},loaded:true,load:async()=>{}}
  const deps={teacherApi:{},ReportFilePreview:{},toast:()=>{},formatDateTime,normalizeError,currentSessionGeneration:()=>1,
    useInternshipContextStore:()=>context,currentMobileSession:()=>({identity:{roleCode:'INTERN_MENTOR'}}),
    uni:{navigateTo:({url})=>links.push(url)},...reports,localizedMakeupStatus:reports.makeupStatusLabel,...employment,...overrides}
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={}
  for(const [key,fn] of Object.entries(component.methods))vm[key]=fn.bind(vm)
  Object.assign(vm,component.data.call(vm))
  for(const [key,fn] of Object.entries(component.computed||{}))Object.defineProperty(vm,key,{get:fn.bind(vm)})
  vm.state='ready';vm.batches=context.batches;vm.batchId=batch
  const template=source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
  const render=new Function('Vue',compile(template,{prefixIdentifiers:true,isCustomElement:()=>true}).code)(Vue)
  async function snapshot(){
    const nodes=[],walk=n=>{if(!n||typeof n!=='object')return;nodes.push(n);if(Array.isArray(n.children))n.children.forEach(walk)}
    const html=await renderToString(Vue.createSSRApp({render(){const tree=render(vm,[]);walk(tree);return tree}}))
    return {html,nodes}
  }
  return {vm,context,snapshot,links,component}
}
const hasClass=(node,name)=>String(node.props?.class||'').split(/\s+/).includes(name)

test('教师本人工作按原链接选择授权批次，越范围时不能读取缓存批次',async()=>{
  const target='9007199254740993009',reads=[]
  const read=async id=>{reads.push(id);return []}
  const p=page('activity/index',{teacherApi:{getMyInternshipCheckins:read,getMyInternshipMakeups:read,getMyInternshipWorkReports:read,getMyInternshipPeriodReports:read,getInternshipEmergencyNotices:read,getPendingInternshipEmergencyNotices:read,getMyInternshipCheckinRule:read}})
  p.context.batches.push({id:target,name:'原链接批次'})
  p.context.selectBatch=id=>{if(!p.context.batches.some(batch=>batch.id===id))return false;p.context.selectedBatchId=id;return true}
  const load=p.vm.load;p.vm.load=()=>{};p.component.onLoad.call(p.vm,{batchId:target});p.vm.load=load;await load()
  assert.equal(p.vm.batchId,target);assert.equal(reads.length,7);assert.ok(reads.every(id=>id===target));assert.equal(p.vm.requestedBatchId,'')
  reads.length=0;p.vm.requestedBatchId='other-batch';await load();assert.equal(reads.length,0);assert.ok(['error','forbidden'].includes(p.vm.state))
})

test('移动教师任务提交时间转换到设备当地时间，缺失或错误不显示原始时间串',()=>{
  const {vm}=page('plan-task-review/index'),raw='2026-10-14T17:26:00Z'
  assert.equal(vm.fmt(raw),formatDateTime(raw))
  assert.equal(vm.fmt('invalid time'),'—');assert.equal(vm.fmt(null),'—')
  if(new Date(raw).getTimezoneOffset()===-480)assert.equal(vm.fmt(raw),'2026-10-15 01:26')
})

test('本人工作日历补签按需展开，未保存报告证明和定位前置保持',async()=>{
  const {vm,snapshot}=page('activity/index');vm.form.workContent='未保存的工作报告';vm.makeupForm.reason='原补签原因';vm.makeupForm.evidenceFileId='220'
  vm.periodForm.content='未保存周期报告';vm.periodForm.attachments=[{fileId:'221',fileName:'待扫描证明',readyForBusiness:false}]
  const before=JSON.stringify([vm.form,vm.makeupForm,vm.periodForm]);let view=await snapshot()
  assert.equal(vm.activeSection,'checkin');view.nodes.find(n=>n.type==='button'&&n.children==='周期报告').props.onClick();assert.equal(vm.activeSection,'period')
  view=await snapshot();view.nodes.find(n=>n.type==='button'&&n.children==='工作记录').props.onClick();assert.equal(vm.activeSection,'work');assert.equal(JSON.stringify([vm.form,vm.makeupForm,vm.periodForm]),before)
  assert.equal(vm.calendarExpanded,false);assert.equal(vm.makeupExpanded,false)
  assert.ok(view.html.includes('不会判为正常签到'));assert.ok(!view.html.includes('国际通用坐标')&&!view.html.includes('正式业务库'))
  const toggles=view.nodes.filter(n=>n.type==='button'&&hasClass(n,'g16-toggle'));assert.equal(toggles.length,2)
  toggles.forEach(n=>n.props.onClick());assert.equal(vm.calendarExpanded,true);assert.equal(vm.makeupExpanded,true)
  view=await snapshot();view.nodes.filter(n=>n.type==='button'&&hasClass(n,'g16-toggle')).forEach(n=>n.props.onClick())
  assert.equal(JSON.stringify([vm.form,vm.makeupForm,vm.periodForm]),before);assert.equal(vm.periodAttachmentsReady,false)
  const save=view.nodes.find(n=>n.type==='button'&&String(n.children).includes('保存周期报告'));assert.equal(save.props.disabled,true)
  vm.periodTotal=24;view=await snapshot();assert.ok(view.html.includes('下一页报告'))
})

test('就业空队列不显示假页码，敏感查看和退回前置保持',async()=>{
  const {vm,snapshot}=page('employment/index');let view=await snapshot()
  assert.ok(!view.nodes.some(n=>hasClass(n,'pager')));assert.ok(!view.html.includes('共 0 份'))
  vm.detail={id:'99',status:'SUBMITTED',statusLabel:'待审核',revisionCount:1,sensitiveVisible:false,
    current:{fields:{studentName:'合成学生'},fieldRows:[{key:'salary',label:'月薪',value:'0 元',sourceLabel:'本次登记'}],attachments:[],modeLabel:'就业上报',submittedAt:'2026-10-13T01:00:00Z',correctionReason:'原补正原因'},history:[]}
  vm.comment='保留原审核意见';view=await snapshot()
  assert.ok(view.html.includes('查看完整资料需说明用途。')&&view.html.includes('核验用途，至少5字')&&view.html.includes('原补正原因'))
  assert.equal(view.nodes.find(n=>hasClass(n,'approve')).props.disabled,true)
  assert.equal(vm.comment,'保留原审核意见');vm.hasMore=true;view=await snapshot();assert.ok(view.nodes.some(n=>hasClass(n,'pager')))
})

test('学生档案先显示去向资格，详情及账号安全可展开且不调用密码重置',async()=>{
  const {vm,context,snapshot,links}=page('internship-students/detail');vm.id=record
  vm.detail={name:'合成学生',batchName:'合成批次',className:'原班级',studentNo:'00000001',statusLabel:'待上岗',eligibilityLabel:'资格合格',eligibilityStatus:'QUALIFIED',enterpriseName:'原企业',positionName:'原岗位',advisorName:'原导师',eligibilityReview:{reason:'保留认定说明',studentVisible:false},auditTrail:[]}
  vm.account={bound:true,mustChangePassword:false,canReset:true,accountStatus:'ACTIVE',loginNameMasked:'st***nt'}
  let view=await snapshot();assert.equal(vm.detailsOpen,false);assert.equal(vm.accountOpen,false)
  assert.ok(view.html.includes('原企业')&&view.html.includes('原岗位')&&view.html.includes('资格合格'))
  view.nodes.filter(n=>hasClass(n,'itd__toggle')).forEach(n=>n.props.onClick())
  assert.equal(vm.detailsOpen,true);assert.equal(vm.accountOpen,true);view=await snapshot()
  assert.ok(view.html.includes('保留认定说明')&&view.html.includes('历史内部说明，仅教师可见')&&view.html.includes('原登录立即失效')&&view.html.includes('临时密码仅显示一次'))
  view.nodes.find(n=>hasClass(n,'itd__process')).props.onClick();assert.ok(links[0].includes('id='+record+'&batchId='+batch))
  context.can=()=>false;view=await snapshot();assert.ok(!view.nodes.some(n=>hasClass(n,'itd__reset')))
})

test('归档后的轮岗查询只读，在岗记录继续允许正常办理',async()=>{
  let status='ARCHIVED';const {vm,snapshot}=page('student-process/index',{teacherInternshipStudentDetail:async()=>({id:record,batchId:batch,status}),teacherInternshipStudentRotations:async()=>[]})
  vm.recordId=record;await vm.load();assert.equal(vm.canManage,false);vm.openCreate();assert.equal(vm.form.visible,false)
  assert.ok(!(await snapshot()).html.includes('新增轮岗'))
  status='ONBOARD';await vm.load();assert.equal(vm.canManage,true);vm.openCreate();assert.equal(vm.form.visible,true)
})

test('学生轮岗去技术说明，部门项目自评和零分缺项继续区分',async()=>{
  const {vm,snapshot}=page('student-process/index');vm.recordId=record;vm.studentName='合成学生'
  vm.rows=[{id:'18',rotationSeq:1,departmentName:'原轮岗部门',status:'ACTIVE',startDate:'2026-09-01',endDate:'2026-09-30',mentorName:'原带教老师',departmentManagerName:'原负责人',studentSelfEvaluation:'原自评内容',studentSelfRating:3,projects:[{id:'19',projectName:'原项目',projectContent:'原项目内容'}],scores:{theory:0,skill:null,mentor:80,total:null}}]
  const view=await snapshot();assert.ok(!view.html.includes('按批次权重合成')&&!view.html.includes('实习记录 '+record))
  for(const text of ['原轮岗部门','原项目','原项目内容','原自评内容','0.0','—','80.0'])assert.ok(view.html.includes(text),text)
  assert.equal(vm.score(0),'0.0');assert.equal(vm.score(null),'—')
  assert.equal(vm.statusLabel('FUTURE_INTERNAL_STATE'),'状态待核对')
  assert.ok(view.nodes.find(n=>n.type==='MobileNavBar').props['fallback-url'].includes('id='+record+'&batchId='+batch))
})
