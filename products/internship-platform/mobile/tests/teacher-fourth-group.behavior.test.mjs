import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import * as positions from '../src/modules/internshipPositionModel.js'
import { formatDateTime } from '../src/utils/format.js'

const batch='9007199254740993001'
function page(path){
  const source=fs.readFileSync(new URL(`../src/pages/teacher-internship/${path}.vue`,import.meta.url),'utf8'),links=[],calls=[]
  const context={selectedBatchId:batch,batches:[{id:batch,name:'合成批次'}],selectedBatch:{name:'合成批次'},can:code=>code!=='internship.makeup.review',restore(){},load:async()=>{},clear(){}}
  const identity={roleCode:'INTERN_MENTOR',roleName:'INTERN_MENTOR',availableRoles:[{roleCode:'INTERN_MENTOR',roleName:'INTERN_MENTOR'}]}
  const deps={...positions,formatDateTime,InternshipApprovalCard:{},teacherApi:{},currentSessionGeneration:()=>1,useInternshipContextStore:()=>context,
    toast:value=>calls.push(['toast',value]),currentMobileSession:()=>({identity}),useSessionStore:()=>({setIdentity(){}}),relaunch:path=>links.push(path),
    switchMobileRole:async code=>{calls.push(['switch',code]);return {identity:{roleCode:code}}},
    teacherInternshipPositions:async()=>{calls.push(['positions']);return {items:[],total:0}},
    uni:{redirectTo:({url})=>links.push(url)},go:path=>links.push(path)}
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm=component.data()
  for(const [key,fn] of Object.entries(component.methods))vm[key]=fn.bind(vm)
  for(const [key,fn] of Object.entries(component.computed||{}))Object.defineProperty(vm,key,{get:fn.bind(vm)})
  vm.state='ready'
  const template=source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1],render=new Function('Vue',compile(template,{prefixIdentifiers:true,isCustomElement:()=>true}).code)(Vue)
  async function snapshot(){const nodes=[],walk=n=>{if(!n||typeof n!=='object')return;nodes.push(n);if(Array.isArray(n.children))n.children.forEach(walk)};const html=await renderToString(Vue.createSSRApp({render(){const tree=render(vm,[]);walk(tree);return tree}}));return {html,nodes}}
  return {vm,context,identity,links,calls,snapshot}
}
const hasClass=(node,name)=>String(node.props?.class||'').split(/\s+/).includes(name)

test('身份页面以中文呈现，当前身份不切换且原角色代码不被改写',async()=>{
  const {vm,identity,calls,snapshot}=page('role-switch/index');const before=JSON.stringify(identity);vm.load()
  let view=await snapshot();assert.ok(view.html.includes('实习指导教师')&&!view.html.includes('INTERN_MENTOR'))
  assert.ok(view.html.includes('当前身份'));assert.ok(!view.html.includes('当前只有一个可用身份，无需切换。'));await view.nodes.find(n=>hasClass(n,'rs-item')).props.onClick()
  assert.deepEqual(calls,[]);assert.equal(JSON.stringify(identity),before)
  assert.equal(vm.displayRoleName({roleCode:'CUSTOM_NEW',roleName:'CUSTOM_NEW'}),'当前工作身份')
  assert.equal(vm.displayRoleName({roleCode:'CUSTOM_NEW',roleName:'学校自定义中文身份'}),'学校自定义中文身份')
})

test('志愿无招聘季保留五类筛选和原批次，不伪造可办理数据',async()=>{
  const {vm,snapshot,links}=page('internship-volunteers/index');vm.scope.batchId=batch
  const view=await snapshot();assert.ok(view.html.includes('当前批次暂无招聘季。'));assert.equal(vm.filters.length,5)
  const tabs=view.nodes.filter(n=>n.type==='button'&&String(n.children)==='已审核');assert.equal(tabs.length,1);tabs[0].props.onClick()
  assert.ok(links[0].includes('batchId='+batch)&&links[0].includes('status=REVIEWED'))
  assert.equal(vm.rows.length,0)
})

test('岗位页保留正常导师拒绝，缺权限不读取有权列表',async()=>{
  const {vm,context,snapshot,calls}=page('internship-positions/index');context.can=()=>false
  await vm.load();assert.equal(vm.state,'forbidden');assert.ok(!calls.some(call=>call[0]==='positions'))
  const view=await snapshot();assert.ok(view.nodes.some(n=>n.type==='MobileGlobalState'&&n.props.state==='forbidden'))
  assert.equal(view.nodes.find(n=>n.type==='MobileNavBar').props.subtitle,undefined)
})

test('补卡请假销假类别保持，权限拒绝、读取失败与证明要求不删',async()=>{
  const {vm,snapshot}=page('internship-approval/ApprovalCore');vm.batches=[{id:batch,name:'合成批次'}];vm.batchId=batch;vm.sourceErrors.makeup='此类记录暂未读取，请核对权限或重试'
  for(const tab of ['makeup','leave','overdue']){
    vm.tab=tab;const view=await snapshot()
    for(const label of ['补卡审批','请假审批','销假办结'])assert.ok(view.html.includes(label))
    assert.ok(!view.html.includes('后端')&&!view.html.includes('真实查看'))
    if(tab==='makeup')assert.ok(view.html.includes('此类记录暂未读取')&&!view.html.includes('当前身份可查看补卡申请'))
  }
  vm.tab='leave';vm.leaves=[{id:'17',version:0,status:'PENDING',evidenceRequired:true}]
  assert.ok((await snapshot()).html.includes('缺少必需证明不能通过'))
  assert.deepEqual(vm.batchLabels,['合成批次'])
})
