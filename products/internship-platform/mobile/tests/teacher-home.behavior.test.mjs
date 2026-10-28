import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { normalizeError } from './request-module.mjs'

const source=fs.readFileSync(new URL('../src/pages/teacher-internship/index.vue',import.meta.url),'utf8')
const template=source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
const render=new Function('Vue',compile(template,{prefixIdentifiers:true,isCustomElement:tag=>tag!=='MobileNavBar'}).code)(Vue)
function page(permissions=null,api={}){
  const reads=[],menus=[]
  const links=[],events=[],session={identity:{roleName:'实习指导教师',availableRoles:[{roleCode:'INTERN_MENTOR'}]}},runtime={generation:0,logoutAllowed:true}
  const context={selectedBatchId:'9007199254740993001',batches:[{id:'9007199254740993001',name:'当前合成批次'}],
    can:code=>permissions===null||permissions.includes(code),load:async()=>{},
    selectBatch(id){this.selectedBatchId=id;return true},clear(){events.push('clear')}}
  Object.defineProperty(context,'selectedBatch',{get:()=>context.batches.find(b=>b.id===context.selectedBatchId)})
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const component=new Function('SchoolServiceInfo','TeacherNoticeInbox','useInternshipContextStore','currentMobileSession','logoutMobile','go','relaunch','currentSessionGeneration','teacherApi','uni','normalizeError',script)(
    {},{},()=>context,()=>session,async()=>runtime.logoutAllowed,p=>links.push(p),p=>links.push(p),()=>runtime.generation,{getInternshipWorkbenchTodos:async params=>{reads.push(params);return {total:0,groupCounts:{ALL:0}}},...api},{showActionSheet:menu=>menus.push(menu)},normalizeError)
  const vm={...component.data(),$nextTick:async fn=>fn?.(),$refs:{schoolService:{load:()=>events.push('help')},importantNotices:{refresh:()=>events.push('refresh'),pause:()=>events.push('pause'),reset:()=>events.push('reset')}}}
  for(const [key,fn] of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const [key,fn] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  vm.state='ready';vm.roleName=session.identity.roleName
  return {vm,component,context,session,runtime,links,events,reads,menus}
}
async function snapshot(vm){
  const nodes=[],walk=node=>{if(!node||typeof node!=='object')return;nodes.push(node);if(Array.isArray(node.children))node.children.forEach(walk)}
  const html=await renderToString(Vue.createSSRApp({components:{MobileNavBar:{setup:(_, {slots})=>()=>Vue.h('header',slots.right?.())}},render(){const tree=render(vm,[]);walk(tree);return tree}}))
  return {html,nodes}
}
const hasClass=(node,name)=>String(node.props?.class||'').split(/\s+/).includes(name)

test('教师首页刷新采用深链的授权批次，范围外批次停止读取待办',async()=>{
  const p=page(),target='9007199254740993002';p.context.batches.push({id:target,name:'原单批次'})
  p.context.selectBatch=id=>{if(!p.context.batches.some(b=>b.id===id))return false;p.context.selectedBatchId=id;return true}
  p.component.onLoad.call(p.vm,{batchId:target});await p.vm.load();assert.equal(p.context.selectedBatchId,target);assert.equal(p.vm.state,'ready')
  p.reads.length=0;p.component.onLoad.call(p.vm,{batchId:'9007199254740993999'});await p.vm.load();assert.equal(p.vm.state,'forbidden');assert.deepEqual(p.reads,[])
})

test('已有身份无工作台权限时明确拒绝并保留切换入口，服务故障仍是故障',async()=>{
  const p=page();p.session.identity.availableRoles=[{roleCode:'SCHOOL_ADMIN'},{roleCode:'SYSTEM_ADMIN'}]
  p.context.load=async()=>{throw {httpStatus:403,bizCode:'NO_PERMISSION',message:'internal'}}
  await p.vm.load();assert.equal(p.vm.state,'forbidden');assert.match(p.vm.error,/可切换到已有的业务身份/)
  assert.ok((await snapshot(p.vm)).html.includes('切换身份'))
  p.context.load=async()=>{throw {httpStatus:503,message:'internal'}};await p.vm.load();assert.equal(p.vm.state,'error');assert.doesNotMatch(p.vm.error,/无权|没有岗位实习/)
})

test('教师首页身份优先中文名称，原枚举和未知身份均不直接展示',async()=>{
  const {vm}=page()
  for(const [identity,expected] of [
    [{roleCode:'INTERN_MENTOR',roleName:'校内指导老师'},'校内指导老师'],
    [{roleCode:'INTERN_MENTOR',roleName:'INTERN_MENTOR',availableRoles:[{roleCode:'SCHOOL_ADMIN',roleName:'其他身份'},{roleCode:'INTERN_MENTOR',roleName:'本校指导教师'}]},'本校指导教师'],
    [{roleCode:'INTERN_MENTOR',roleName:'INTERN_MENTOR'},'实习指导教师'],
    [{roleCode:'COLLEGE_ADMIN',roleName:''},'院系实习管理员'],
    [{roleCode:'CUSTOM_NEW',roleName:'CUSTOM_NEW'},'当前工作身份'],
    [{},'当前工作身份']
  ]){
    vm.roleName=vm.displayRoleName(identity)
    assert.equal(vm.roleName,expected)
    const {html}=await snapshot(vm)
    assert.ok(html.includes(expected));assert.ok(!html.includes('INTERN_MENTOR')&&!html.includes('CUSTOM_NEW'))
  }
})

test('教师首页突出真实待办消息，原十四入口只分层不重复并保持批次路径',async()=>{
  const {vm,links,menus}=page();vm.moreExpanded=true;vm.todoState='ready';const {html,nodes}=await snapshot(vm)
  assert.deepEqual(vm.primaryItems.map(item=>item.label),['分类待办','站内信'])
  assert.equal(vm.items.length,14);assert.equal(vm.workItems.length,12)
  assert.deepEqual(new Set([...vm.primaryItems,...vm.workItems].map(x=>x.path)),new Set(vm.items.map(x=>x.path)))
  const actions=nodes.filter(n=>['tw-shortcut','tw-item','tw-main-action','tw-messages','tw-all-todos'].some(name=>hasClass(n,name)))
  assert.equal(actions.length,21)
  actions.forEach(node=>node.props.onClick())
  assert.equal(menus.length,1);menus[0].success({tapIndex:1})
  assert.deepEqual(new Set(links.map(path=>path.split('?')[0])),new Set([...vm.items,...vm.visibleMoreItems].map(item=>item.path.split('?')[0])))
  assert.ok(links.includes('/pages/teacher-internship/internship-review/index?tab=visit&batchId=9007199254740993001'))
  assert.ok(links.filter(link=>!link.includes('/todos/')).every(link=>link.endsWith('batchId=9007199254740993001')))
  assert.ok(links.includes('/pages/teacher-internship/todos/index?group=ALL'));assert.ok(html.includes('本人全部批次'))
  assert.ok(html.includes('实习指导教师')&&html.includes('当前合成批次'))
  assert.ok(!html.includes('按权限显示')&&!html.includes('指导、审核、评价与统计'))
  assert.ok(nodes.some(node=>node.type==='SchoolServiceInfo'&&node.props.compact===''))
})

test('入口保持现有权限，只有多个批次才显示切换并选择真实批次',async()=>{
  const {vm,context}=page(['internship.dashboard.view'])
  let view=await snapshot(vm)
  assert.equal(vm.primaryItems.length,2);assert.equal(vm.workItems.length,0)
  assert.equal(view.nodes.filter(n=>hasClass(n,'tw-item')).length,0)
  assert.equal(view.nodes.filter(n=>hasClass(n,'tw-switch')).length,0)
  context.batches.push({id:'9007199254740993002',name:'另一批次'})
  view=await snapshot(vm)
  assert.equal(view.nodes.filter(n=>hasClass(n,'tw-switch')).length,1)
  view.nodes.find(n=>n.type==='picker').props.onChange({detail:{value:1}})
  assert.equal(context.selectedBatchId,'9007199254740993002')
  const denied=page([]),empty=await snapshot(denied.vm)
  assert.ok(empty.nodes.some(n=>n.type==='MobileInlineAlert'&&n.props.title==='暂无岗位实习操作权限'))
  assert.equal(empty.nodes.filter(n=>hasClass(n,'tw-primary')||hasClass(n,'tw-item')).length,0)
})

test('离页及换会话仍拦截迟到首页读取，通知与退出沿用原守卫',async()=>{
  const {vm,component,context,runtime,events,links,session}=page()
  let resolve;context.load=()=>new Promise(r=>{resolve=r})
  const loading=vm.load();component.onHide.call(vm);resolve();await loading
  assert.deepEqual(events,['pause'])
  vm.hidden=false;const changed=vm.load();runtime.generation++;resolve();await changed
  assert.deepEqual(events,['pause'])
  context.load=async()=>{};session.identity.roleName='院系实习管理员';session.identity.availableRoles.push({roleCode:'COLLEGE_ADMIN'})
  component.onShow.call(vm);await Promise.resolve();await Promise.resolve()
  assert.equal(vm.roleName,'院系实习管理员');assert.equal(vm.canSwitchRole,true)
  assert.ok(events.includes('help')&&events.includes('reset'))
  vm.openRoleSwitch();assert.equal(links.at(-1),'/pages/teacher-internship/role-switch/index')
  runtime.logoutAllowed=false;await vm.logout();assert.ok(!events.includes('clear'))
  runtime.logoutAllowed=true;await vm.logout();assert.ok(events.includes('clear'))
  assert.equal(links.at(-1),'/pages/login/index?entry=teacher')
})

test('更多办理默认收起，导师与学校授权入口真实点击保留长批次且原十四项不变',async()=>{
  const originalPaths=['todos','messages','internship-students','internship-positions','internship-application','internship-change','internship-review','process-report-review','material-review','payroll-review','enterprise-eval','school-stats','activity','employment']
  const mentorPermissions=['internship.dashboard.view','internship.student.view','internship.risk.view','internship.score.view','internship.agreement.view','internship.task.view','internship.guidance.manage']
  for(const [permissions,expected] of [[mentorPermissions,['风险处置','实习成绩','三方协议进度','计划任务确认','指导记录']],[null,['风险处置','实习成绩','三方协议进度','保险核验','计划任务确认','学生鉴定','指导记录']]]){
    const {vm,links}=page(permissions),original=JSON.stringify(vm.items)
    assert.deepEqual(vm.items.map(item=>item.path.split('/')[3]),originalPaths)
    let view=await snapshot(vm)
    assert.equal(vm.moreExpanded,false);assert.equal(view.nodes.filter(n=>hasClass(n,'tw-more-item')).length,0)
    view.nodes.find(n=>hasClass(n,'tw-more-toggle')).props.onClick()
    view=await snapshot(vm)
    assert.deepEqual(vm.visibleMoreItems.map(item=>item.label),expected)
    const actions=view.nodes.filter(n=>hasClass(n,'tw-more-item'))
    assert.equal(actions.length,vm.otherItems.length)
    actions.forEach(node=>node.props.onClick())
    assert.deepEqual(links,vm.otherItems.map(item=>item.path+(item.path.includes('?')?'&':'?')+'batchId=9007199254740993001'))
    assert.equal(JSON.stringify(vm.items),original)
    view.nodes.find(n=>hasClass(n,'tw-more-toggle')).props.onClick()
    assert.equal((await snapshot(vm)).nodes.filter(n=>hasClass(n,'tw-more-item')).length,0)
  }
})

test('更多办理无读取权限不显示，指导名单缺权拒显，批次及身份切换收起不带旧上下文',async()=>{
  for(const permissions of [[],['internship.score.manage','internship.insurance.verify','internship.task.review','internship.eval.self.review'],['internship.guidance.manage']]){
    const {vm}=page(permissions),view=await snapshot(vm)
    assert.equal(vm.visibleMoreItems.length,0)
    assert.equal(view.nodes.filter(n=>hasClass(n,'tw-more-toggle')||hasClass(n,'tw-more-item')).length,0)
  }
  const {vm,context,component,runtime,links,events}=page(['internship.risk.view'])
  let view=await snapshot(vm);view.nodes.find(n=>hasClass(n,'tw-more-toggle')).props.onClick()
  context.batches.push({id:'9007199254740993002',name:'另一合成批次'})
  vm.changeBatch({detail:{value:1}});await Promise.resolve();await Promise.resolve()
  assert.equal(vm.moreExpanded,false)
  view=await snapshot(vm);view.nodes.find(n=>hasClass(n,'tw-more-toggle')).props.onClick()
  view=await snapshot(vm);view.nodes.find(n=>hasClass(n,'tw-more-item')).props.onClick()
  assert.equal(links.at(-1),'/pages/teacher-internship/internship-risk/index?batchId=9007199254740993002')
  runtime.generation++;component.onShow.call(vm);await Promise.resolve();await Promise.resolve()
  assert.equal(vm.moreExpanded,false);assert.ok(events.includes('reset'))
  context.can=()=>false
  assert.equal((await snapshot(vm)).nodes.filter(n=>hasClass(n,'tw-more-toggle')).length,0)
})

test('教师首页待办只读服务端总数，明确全部批次范围，不用列表长度冒充统计',async()=>{
  const calls=[],p=page(null,{getInternshipWorkbenchTodos:async params=>{calls.push(params);return {total:9,items:[{id:'one'}],groupCounts:{ALL:9,REPORT:5,LEAVE:4}}}})
  await p.vm.load();assert.equal(p.vm.todoTotal,9);assert.equal(p.vm.todoState,'ready')
  assert.deepEqual(calls,[{status:'PENDING',group:'ALL',page:1,pageSize:3}]);assert.deepEqual(p.vm.todoGroups.map(item=>item.count),[4,5])
  const {html}=await snapshot(p.vm);assert.match(html,/本人全部批次/);assert.match(html,/共 9 项/)
  p.vm.openTodoGroup('REPORT');assert.equal(p.links.at(-1),'/pages/teacher-internship/todos/index?group=REPORT')
})

test('教师待办统计错误不伪装零，无权限不读取，迟到响应不能跨会话',async()=>{
  for(const response of [{}, {total:'0',groupCounts:{}}]){
    const p=page(null,{getInternshipWorkbenchTodos:async()=>response});await p.vm.load()
    assert.equal(p.vm.state,'ready');assert.equal(p.vm.todoState,'error');assert.match((await snapshot(p.vm)).html,/不能确认当前数量/)
  }
  let reads=0;const denied=page([],{getInternshipWorkbenchTodos:async()=>{reads++;return {}}});await denied.vm.load();assert.equal(reads,0)
  let resolve;const late=page(null,{getInternshipWorkbenchTodos:()=>new Promise(done=>resolve=done)}),waiting=late.vm.loadTodoCounts(0,0)
  late.runtime.generation++;resolve({total:8,groupCounts:{ALL:8}});await waiting;assert.equal(late.vm.todoState,'loading')
})

test('四类报告网关保留两个权威页面，取消或换身份后不跳转',()=>{
  const p=page(),report=p.vm.visibleItems.find(item=>item.reportGateway)
  p.vm.open(report);assert.deepEqual(p.menus[0].itemList,['周报批阅','日报、月报、总结批阅']);p.menus[0].success({tapIndex:0})
  assert.equal(p.links.at(-1),'/pages/teacher-internship/internship-review/index?tab=weekly&batchId=9007199254740993001')
  p.menus[0].success({tapIndex:-1});assert.equal(p.links.length,1)
  p.vm.open(report);p.runtime.generation++;p.menus[1].success({tapIndex:1});assert.equal(p.links.length,1)
})


test('首页保留所有有待办分类并直接打开服务端优先原单',async()=>{
 const p=page(null,{getInternshipWorkbenchTodos:async()=>({total:10,items:[{todoId:'9',title:'原单',actionPath:'/pages/teacher-internship/todos/index?focus=9'}],groupCounts:{LEAVE:2,REPORT:3,ATTENDANCE:2,VISIT:3}})})
 await p.vm.load();assert.equal(p.vm.todoGroups.length,4);p.vm.openPriority(p.vm.priorityTodos[0]);assert.match(p.links.at(-1),/focus=9/)
 assert.match((await snapshot(p.vm)).html,/另有 9 项/)
})
