import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'

const source=fs.readFileSync(new URL('../src/pages/student-internship/index.vue',import.meta.url),'utf8')
const template=source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
const render=new Function('Vue',compile(template,{prefixIdentifiers:true,isCustomElement:tag=>tag!=='MobileNavBar'}).code)(Vue)
function page(api={}){
  let generation=0
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const links=[],component=new Function('SchoolServiceInfo','studentApi','currentSessionGeneration','formatDateTime','openBusinessFile','toast','go','uni',script)({}, api,()=>generation,value=>value,()=>{},()=>{},path=>links.push(path),{setStorageSync(){},removeStorageSync(){}})
  const vm={...component.data(),$refs:{}}
  for(const [key,fn] of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const [key,fn] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  vm.state='ready';vm.selectedBatchId='2673';vm.candidates=[{batchId:'2673',batchName:'合成测试批次'}]
  vm.i={hasBatch:true,batchId:'2673',batch:'合成测试批次',company:'已批准自主企业',post:'已批准岗位',destinationType:'SELF_ARRANGED',statusText:'READY',historyMode:false,schoolMentor:'合成导师',companyMentor:'企业导师',eligibilityReview:{status:'QUALIFIED',label:'资格合格',reason:'学校公开资格意见',reviewedAt:'2026-10-13'},basicInfo:{todoCount:0,statusLabel:'已完善',missingFields:[]}}
  const age={code:'minimumAge',label:'实习年龄',required:true,status:'PENDING',reason:'出生日期待学校核实，暂不能安排岗位实习',route:''}
  vm.compliance={batchName:'合成测试批次',passed:false,currentTask:age,nextAction:null,items:[age,{code:'eligibility',label:'实习资格',required:true,status:'VALID',statusLabel:'已完成',reason:'学校公开资格意见',route:''},{code:'enterpriseAccess',label:'企业准入考察',required:true,status:'MISSING',reason:'学校需核实企业准入条件',route:''}],blockers:[age],completeness:{done:1,required:3},timeline:[]}
  return {vm,component,links,switchAccount:()=>generation++}
}
async function snapshot(vm){
  const nodes=[];const walk=node=>{if(!node||typeof node!=='object')return;nodes.push(node);if(Array.isArray(node.children))node.children.forEach(walk)}
  const html=await renderToString(Vue.createSSRApp({components:{MobileNavBar:{setup:(_,{slots})=>()=>Vue.h('header',slots.right?.())}},render(){const tree=render(vm,[]);walk(tree);return tree}}))
  return {html,nodes}
}

test('本周已批阅的原周报显示已批阅和查看入口，不催写下一周',async()=>{
  const {vm}=page();vm.i.statusText='ONBOARD';vm.i.weekly={week:'第 1 周',submitted:false,approved:true,lastFeedback:''};vm.i.checkin={done:true,note:'按点击采集',time:''};vm.i.status={};vm.compliance={currentTask:null,items:[],blockers:[],timeline:[]}
  const {html}=await snapshot(vm);assert.match(html,/第 1 周.*已批阅/);assert.match(html,/查看周报/);assert.doesNotMatch(html,/第 1 周.*可填写/)
})

test('学生首页首屏优先真实去向，资格小状态且阻断只说明一次',async()=>{
  const {vm}=page(),{html,nodes}=await snapshot(vm)
  assert.ok(html.includes('已批准岗位')&&html.includes('已批准自主企业')&&html.includes('自主实习')&&html.includes('资格合格'))
  assert.ok(!html.includes('查看安排、资格与当前事项')&&html.includes('合成测试批次'))
  assert.ok(!html.includes('实习资格已通过')&&!html.includes('学校公开资格意见')&&!html.includes('按当前实习状态整理'))
  assert.equal(html.split('出生日期待学校核实，暂不能安排岗位实习').length-1,1)
  assert.ok(nodes.some(node=>String(node.props?.class||'').includes('in__details-toggle')))
  assert.equal(vm.compliance.nextAction,null);assert.equal(vm.canShowDailyWork,false);assert.equal(vm.i.basicInfo.todoCount,0)
})

test('首页真实详情开关保留完整资格合规和基础资料入口，不改后端状态',async()=>{
  const {vm}=page(),facts=JSON.stringify({i:vm.i,compliance:vm.compliance})
  const before=await snapshot(vm),toggle=before.nodes.find(node=>String(node.props?.class||'').includes('in__details-toggle'))
  assert.ok(toggle);toggle.props.onClick();assert.equal(vm.detailsOpen,true)
  const opened=await snapshot(vm)
  assert.ok(opened.html.includes('学校公开资格意见')&&opened.html.includes('2026-10-13')&&opened.html.includes('企业准入考察')&&opened.html.includes('查看基础资料'))
  assert.equal(opened.html.split('出生日期待学校核实，暂不能安排岗位实习').length-1,1)
  opened.nodes.find(node=>String(node.props?.class||'').includes('in__details-toggle')).props.onClick();assert.equal(vm.detailsOpen,false)
  assert.equal(JSON.stringify({i:vm.i,compliance:vm.compliance}),facts)
})

test('首页原下一步不与服务重复，全部原入口仍能携带真实批次',async()=>{
  const {vm,links}=page();vm.compliance.nextAction={label:'去处理：实习保险',route:'/pages/student-internship/insurance/index'}
  const paths=vm.serviceGroups.flatMap(group=>group.items.map(item=>item.path))
  assert.ok(!paths.includes(vm.compliance.nextAction.route))
  assert.deepEqual(new Set([...paths,vm.compliance.nextAction.route]),new Set(vm.navItems.map(item=>item.path)))
  vm.openSub('/pages/student-internship/process-report/index?type=monthly')
  assert.equal(links[0],'/pages/student-internship/process-report/index?type=monthly&batchId=2673')
  vm.candidates.push({batchId:'2674',batchName:'另一个真实批次'})
  assert.ok((await snapshot(vm)).nodes.some(node=>String(node.props?.class||'').includes('in__batch-switch')))
  vm.i.historyMode=true;vm.i.statusText='ONBOARD';assert.equal(vm.canShowDailyWork,false)
})

test('首页精简仍保留非合格原因和缺项待办，切批次收起旧详情',async()=>{
  const {vm}=page();vm.i.eligibilityReview={status:'UNQUALIFIED',label:'资格不合格',reason:'请向指导教师补充学校要求的材料'}
  vm.i.basicInfo={todoCount:1,missingFields:['生源地'],statusLabel:'待完善'}
  const {html}=await snapshot(vm)
  assert.ok(html.includes('请向指导教师补充学校要求的材料')&&html.includes('待完善：生源地'))
  vm.detailsOpen=true;vm.load=()=>{};vm.selectCandidate({batchId:'2674'})
  assert.equal(vm.detailsOpen,false);assert.equal(vm.selectedBatchId,'2674')
  vm.detailsOpen=true;vm.clearAccountContext();assert.equal(vm.detailsOpen,false);assert.equal(vm.i,null)
})

test('自主去向已登记仅修正缺关联的企业岗位说明，拒绝原因与后端事实保持',async()=>{
  const {vm}=page()
  const enterprise={code:'enterprise',status:'MISSING',required:true,route:'/pages/student-internship/enterprises/index',reason:'尚未落实实习企业'}
  const position={code:'position',status:'MISSING',required:true,route:'/pages/student-internship/application/index',reason:'尚未落实实习岗位'}
  vm.compliance.currentTask=enterprise;vm.compliance.items=[enterprise,position];vm.detailsOpen=true
  const original=JSON.stringify(vm.compliance)
  const {html}=await snapshot(vm)
  assert.ok(html.includes('企业已登记，待学校核实企业准入'))
  assert.ok(html.includes('岗位已登记，待学校核实岗位条件'))
  assert.ok(!html.includes('尚未落实实习企业')&&!html.includes('尚未落实实习岗位'))
  assert.equal(JSON.stringify(vm.compliance),original)
  for(const item of [{...enterprise,reason:'企业已列入黑名单'},{...enterprise,reason:'企业准入已过期'},{...position,reason:'岗位存在安全风险'},{...position,status:'REJECTED'}])assert.equal(vm.complianceReason(item),item.reason)
  vm.i.company='';assert.equal(vm.complianceReason(enterprise),enterprise.reason)
  vm.i.post='';assert.equal(vm.complianceReason(position),position.reason)
  vm.i.company='已批准自主企业';vm.i.post='已批准岗位';vm.i.destinationType='ASSIGNED'
  assert.equal(vm.complianceReason(enterprise),enterprise.reason);assert.equal(vm.complianceReason(position),position.reason)
})

test('首页分组名称对应已有实习阶段，全部入口保持',()=>{
  for(const [facts,label] of [[{company:'',post:''},'选岗申请'],[{},'上岗准备'],[{statusText:'ONBOARD'},'实习记录'],[{statusText:'ENDED'},'实习收尾']]){
    const {vm}=page();Object.assign(vm.i,facts)
    assert.equal(vm.serviceGroups.find(group=>group.key==='stage').label,label)
    assert.equal(vm.serviceGroups.find(group=>group.key==='more').label,'其他事项')
    assert.deepEqual(new Set(vm.serviceGroups.flatMap(group=>group.items.map(item=>item.path))),new Set(vm.navItems.map(item=>item.path)))
  }
})

test('首页只展示本人当前批次真实退回材料，按要求编号进入原任务',async()=>{
  const calls=[],returned={id:'9007199254740993333',materialName:'合成过程材料',submission:{status:'RETURNED',reviewComment:'请补清晰说明'}}
  const p=page({getInternshipMaterialRequirements:async(...args)=>{calls.push(args);return [returned,{id:'32',submission:{status:'APPROVED'}}]}})
  p.vm.i.recordId='9007199254740993111';p.vm.loadSequence=4
  await p.vm.loadReturnedMaterials(4,0)
  assert.deepEqual(calls,[['2673','9007199254740993111']]);assert.deepEqual(p.vm.returnedMaterials,[returned])
  assert.match((await snapshot(p.vm)).html,/材料需补正/)
  p.vm.openMaterial(returned);assert.equal(p.links.at(-1),'/pages/student-internship/materials/index?requirementId=9007199254740993333&batchId=2673')
})

test('首页材料读取失败明确提示，历史批次不催办，换会话后迟到结果丢弃',async()=>{
  const p=page({getInternshipMaterialRequirements:async()=>{throw Error('private path')}});p.vm.i.recordId='91'
  await p.vm.loadReturnedMaterials(0,0);assert.ok(p.vm.materialError);assert.deepEqual(p.vm.returnedMaterials,[])
  assert.doesNotMatch((await snapshot(p.vm)).html,/private path/)
  let resolve,reads=0;const q=page({getInternshipMaterialRequirements:()=>{reads++;return new Promise(done=>resolve=done)}})
  q.vm.i.recordId='92';q.vm.i.historyMode=true;await q.vm.loadReturnedMaterials(0,0);assert.equal(reads,0)
  q.vm.i.historyMode=false;const waiting=q.vm.loadReturnedMaterials(0,0);q.switchAccount();resolve([{id:'old',submission:{status:'RETURNED'}}]);await waiting
  assert.deepEqual(q.vm.returnedMaterials,[])
})

test('首页常用事项与更多事项保留全部入口，合规主动作不重复',()=>{
  const {vm}=page();vm.compliance.nextAction={route:'/pages/student-internship/plan/index',label:'查看计划'}
  const routes=[...vm.quickItems,...vm.moreServiceGroups.flatMap(group=>group.items)].map(item=>item.path)
  assert.equal(new Set(routes).size,routes.length);assert.equal(routes.includes(vm.compliance.nextAction.route),false)
  assert.deepEqual(new Set([...routes,vm.compliance.nextAction.route]),new Set(vm.navItems.map(item=>item.path)))
})


test('日报入口取学校实际规则，未配置不伪造应交，读取失败明确提示',async()=>{
 for(const count of [0,2,undefined]){
  const p=page({getInternship:async()=>({hasBatch:true,batchId:'2673',recordId:'9',statusText:'ONBOARD',historyMode:false}),getInternshipCompliance:async()=>({}),getInternshipProcessReports:async()=>({rules:{dailyRequiredCount:count}})})
  p.vm.loadEmergencyNotices=async()=>{};p.vm.loadReturnedMaterials=async()=>{};await p.vm.load()
  assert.equal(p.vm.dailyRequired,count===2);assert.equal(p.vm.dailyRuleError,count===undefined)
 }
})
