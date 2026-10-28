import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { formatDateTime } from '../src/utils/format.js'
import { normalizeError } from './request-module.mjs'

const batch='9007199254740993001'

test('志愿消息只读打开原批次原组，大编号不变，未知目标不导航也不改变未读数',async()=>{
  const messageId='9007199254740993011',target={messageId,pageKey:'TEACHER_INTERNSHIP_VOLUNTEERS',batchId:batch,campaignId:'9007199254740993012',groupId:'9007199254740993013'}
  for(const result of [target,{...target,pageKey:'https://outside.invalid'},{...target,groupId:9007199254740994}]){
    let reads=0
    const p=page('messages',{teacherApi:{getInternshipMessageTarget:async id=>{assert.equal(id,messageId);return result},readInternshipWorkbenchMessage:async()=>{reads++}}})
    const row={messageId,hasBusinessTarget:true,readStatus:'UNREAD'};p.vm.items=[row];p.vm.unread=3
    await p.vm.openBusiness(row)
    assert.equal(reads,0);assert.equal(p.vm.unread,3);assert.equal(row.readStatus,'UNREAD');assert.equal(p.vm.expanded,'')
    if(result===target){assert.equal(p.links.length,1);assert.ok(p.links[0].includes('batchId='+batch));assert.ok(p.links[0].includes('groupId='+target.groupId))}
    else{assert.equal(p.links.length,0);assert.ok(p.vm.targetError)}
  }
})

test('消息原单解析迟到后不跨身份导航',async()=>{
  let generation=1,resolve
  const wait=new Promise(done=>resolve=done),messageId='51',p=page('messages',{currentSessionGeneration:()=>generation,teacherApi:{getInternshipMessageTarget:()=>wait}})
  const row={messageId,hasBusinessTarget:true};p.vm.items=[row]
  const opening=p.vm.openBusiness(row);generation++
  resolve({messageId,pageKey:'TEACHER_INTERNSHIP_VOLUNTEERS',batchId:batch,campaignId:'52',groupId:'53'});await opening
  assert.equal(p.links.length,0)
})
function page(name,overrides={}){
  const source=fs.readFileSync(new URL(`../src/pages/teacher-internship/${name}/index.vue`,import.meta.url),'utf8')
  const links=[],calls=[],context={selectedBatchId:batch,batches:[{id:batch,name:'合成批次'}],selectedBatch:{name:'合成批次'},can:()=>true}
  const deps={teacherApi:{readInternshipWorkbenchMessage:()=>{throw Error('不得为展开已读消息发已读请求')}},
    go:path=>links.push(path),toast:()=>{},formatDateTime,normalizeError,currentSessionGeneration:()=>1,useInternshipContextStore:()=>context,
    uni:{navigateTo:({url})=>links.push(url)},teacherInternshipRoster:async(b,params)=>{calls.push([b,params]);return {items:[],total:0}},
    teacherInternshipApplicationStudents:async(...args)=>{calls.push(args);return {items:[{recordId:'9007199254740993010',studentName:'合成学生',studentNo:'000001'}],total:1,hasMore:false}},...overrides}
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm=component.data()
  for(const [key,fn] of Object.entries(component.methods))vm[key]=fn.bind(vm)
  for(const [key,fn] of Object.entries(component.computed||{}))Object.defineProperty(vm,key,{get:fn.bind(vm)})
  vm.state='ready'
  const template=source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
  const render=new Function('Vue',compile(template,{prefixIdentifiers:true,isCustomElement:()=>true}).code)(Vue)
  async function snapshot(){
    const nodes=[],walk=n=>{if(!n||typeof n!=='object')return;nodes.push(n);if(Array.isArray(n.children))n.children.forEach(walk)}
    const html=await renderToString(Vue.createSSRApp({render(){const tree=render(vm,[]);walk(tree);return tree}}))
    return {html,nodes,nav:nodes.find(n=>n.type==='MobileNavBar')}
  }
  return {vm,component,context,snapshot,links,calls}
}
const hasClass=(node,name)=>String(node.props?.class||'').split(/\s+/).includes(name)

test('免签与调岗已办结长原因默认收起，展开保留原文，离页清除展开状态',async()=>{
  for(const name of ['checkin-exemption','internship-change']){
    const {vm,component,snapshot}=page(name);vm.batchId=batch;vm.batches=[{id:batch,name:'合成批次'}];vm.list=[{id:'99',status:'APPROVED',statusLabel:'已通过',studentName:'合成学生',reason:'原申请原因必须保留',reviewComment:'原审核意见必须保留'}]
    let view=await snapshot();assert.ok(!view.html.includes('原申请原因必须保留'));assert.ok(!view.html.includes('原审核意见必须保留'))
    view.nodes.find(n=>n.type==='button'&&String(n.children)==='查看申请详情').props.onClick();view=await snapshot();assert.ok(view.html.includes('原申请原因必须保留'));assert.ok(view.html.includes('原审核意见必须保留'))
    component.onHide.call(vm);assert.equal(vm.expandedNotesId,'')
  }
})

test('待办去说明仍保留真实分类数、期限和原办理路径',async()=>{
  const {vm,snapshot,links}=page('todos')
  vm.counts={ALL:1,LEAVE:1};vm.items=[{todoId:'3',status:'PENDING',title:'合成学生请假',groupLabel:'请假',typeLabel:'请假审批',dueAt:'2026-10-14',actionPath:'/pages/teacher-internship/internship-approval/index?tab=leave&leaveId=77&batchId='+batch}]
  const view=await snapshot()
  assert.equal(view.nav.props.subtitle,undefined);assert.ok(!view.html.includes('脱离业务事实'))
  assert.ok(view.html.includes('全部 1')&&view.html.includes('截止：2026-10-14'))
  view.nodes.find(n=>n.type==='button'&&n.children==='去处理').props.onClick()
  assert.deepEqual(links,[vm.items[0].actionPath])
})

test('消息保留真实未读数，已读卡片展开全文和收起不产生已读写入',async()=>{
  const {vm,snapshot}=page('messages'),content='这是完整正文。'.repeat(45)
  vm.unread=7;vm.items=[{messageId:'8',readStatus:'READ',title:'合成消息',summary:'摘要',content,category:'BUSINESS',createdAt:'2026-10-13T01:18:02Z'}]
  let view=await snapshot();assert.equal(view.nav.props.subtitle,'未读 7 条')
  assert.ok(!view.html.includes(content));await view.nodes.find(n=>hasClass(n,'msg-item')).props.onClick()
  view=await snapshot();assert.ok(view.html.includes(content));assert.ok(view.nodes.some(n=>hasClass(n,'msg-summary')&&hasClass(n,'is-expanded')))
  assert.equal(vm.unread,7);await view.nodes.find(n=>hasClass(n,'msg-item')).props.onClick()
  assert.equal(vm.expanded,'');assert.equal(vm.unread,7)
})

test('教师消息未读筛选走正式查询，重复展开只记录一次已读且真零保留',async()=>{
  const queries=[],row={messageId:'9223372036854770001',readStatus:'UNREAD',title:'合成通知',category:'BUSINESS'};let finish,readCalls=0
  const wait=new Promise(r=>finish=r)
  const p=page('messages',{teacherApi:{getInternshipWorkbenchMessages:async q=>{queries.push(q);return {items:[row],unread:1,hasMore:false}},readInternshipWorkbenchMessage:()=>{readCalls++;return wait}}})
  p.vm.onlyUnread=true;await p.vm.load();assert.equal(queries[0].readStatus,'UNREAD')
  const reading=p.vm.openMessage(row);await p.vm.openMessage(row);assert.equal(readCalls,1)
  finish({messageId:row.messageId,readStatus:'READ'});await reading;assert.equal(p.vm.unread,0);assert.equal(row.readStatus,'READ')
  p.vm.openTodos();assert.equal(p.links.at(-1),'/pages/teacher-internship/todos/index?group=ALL')
})

test('教师消息旧会话回执被丢弃，未完整读取不能显示为零消息',async()=>{
  let generation=1,finish;const wait=new Promise(r=>finish=r)
  const p=page('messages',{currentSessionGeneration:()=>generation,teacherApi:{getInternshipWorkbenchMessages:()=>wait}})
  const reading=p.vm.load();generation++;finish({items:[{messageId:'old'}],unread:7});await reading;assert.deepEqual(p.vm.items,[])
  const q=page('messages',{teacherApi:{getInternshipWorkbenchMessages:async()=>({items:[]})}});await q.vm.load();assert.equal(q.vm.state,'error');assert.match(q.vm.error,/未完整返回/)
})

test('学生名单保留数量、学号班级状态和原档案长编号，不改筛选分页',async()=>{
  const {vm,snapshot,links}=page('internship-students')
  vm.total=25;vm.page=1;vm.rows=[{id:'9007199254740993010',batchId:batch,name:'合成学生',studentNo:'00123001',className:'原班级',eligibilityLabel:'资格合格',eligibilityStatus:'QUALIFIED',statusLabel:'待上岗',positionName:'原岗位'}]
  const view=await snapshot();assert.ok(view.html.includes('25 名学生')&&view.html.includes('00****01')&&view.html.includes('原班级')&&view.html.includes('待上岗'))
  assert.ok(!view.html.includes('点击学生查看实习档案'));assert.ok(view.html.includes('1 / 2'))
  view.nodes.find(n=>hasClass(n,'its__student')).props.onClick()
  assert.equal(links[0],'/pages/teacher-internship/internship-students/detail?id=9007199254740993010&batchId='+batch)
  assert.equal(vm.filters.length,4);assert.equal(vm.pageSize,20);assert.equal(vm.total,25)
})

test('申请24/25统计口径不变，名单展开和审核事实完整，空队列不常驻通过提示',async()=>{
  const {vm,snapshot,calls}=page('internship-application')
  vm.batches=[{id:batch,name:'合成批次',studentCount:25}];vm.batchId=batch;vm.list=[]
  vm.summary={filledStudents:24,totalStudents:25,filledRate:96,unfilledStudents:1,pendingReviewApplications:0,reviewedApplications:1,rejectedApplications:0,totalApplications:24,recruitmentCampaigns:[]}
  const before=JSON.stringify(vm.summary);let view=await snapshot()
  assert.ok(!view.html.includes('/ 25 人'));view.nodes.find(n=>n.type==='button'&&String(n.children).includes('填报统计')).props.onClick();view=await snapshot()
  assert.ok(view.html.includes('24')&&view.html.includes('/ 25 人')&&view.html.includes('96%'))
  assert.ok(view.html.includes('仅统计普通申请和招聘季志愿')&&view.html.includes('不等于去向落实或实际上岗'));assert.ok(!view.html.includes('通过后将落实'))
  await vm.toggleStudentState('UNFILLED');assert.deepEqual(calls[0],[batch,'UNFILLED',1,20]);assert.equal(vm.studentTotal,1)
  vm.list=[{id:'77',studentName:'合成学生',studentNo:'00001',applicationType:'SELF_ARRANGED',applicationTypeLabel:'自主实习',status:'PENDING_REVIEW',statusLabel:'待审核',companyName:'原企业',positionName:'原岗位',workAddress:'原工作地点',contactName:'原联系人',contactPhone:'合成联系电话',applicationNote:'原申请说明',reviewComment:'原退回要求',evidenceFileId:'220',version:2,recordVersion:4,submittedAt:'2026-10-13T01:18:02Z'}]
  view=await snapshot()
  for(const text of ['原企业','原岗位','原工作地点','原联系人','原申请说明','原退回要求','申请证明材料','提交时间'])assert.ok(view.html.includes(text),text)
  assert.ok(!view.html.includes('学生记录'));assert.ok(view.html.includes('申请版本')&&view.html.includes('第 2 版'))
  assert.ok(view.html.includes('通过后将落实实习去向'));assert.equal(JSON.stringify(vm.summary),before)
})
