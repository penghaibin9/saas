import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import * as readiness from '../src/services/fileReadiness.mjs'
import { formatDateTime } from '../src/utils/format.js'

function page(name) {
  const source=fs.readFileSync(new URL(`../src/pages/student-internship/${name}/index.vue`,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm,'').replace('export default','return')
  const deps={currentSessionGeneration:()=>0,formatDateTime,...readiness}
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...component.data()}
  for(const [name,fn]of Object.entries(component.methods||{}))vm[name]=fn.bind(vm)
  for(const [name,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,name,{get:fn.bind(vm)})
  vm.state='ready';vm.pageState='ready';vm.context={batchId:'18',internshipId:'21'};vm.requestedBatchId='18'
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const components={MobileNavBar:{props:['title','fallbackUrl'],setup:p=>()=>h('nav',{'data-return':p.fallbackUrl},p.title)},MobilePrivacyGate:{render:()=>null},
    MobileGlobalState:{props:['state','title','description'],setup:(p,{slots})=>()=>p.state==='ready'?h('div',slots.default?.()):h('section',[p.title,p.description])},
    MobileInlineAlert:{props:['title','description'],setup:p=>()=>h('p',[p.title,p.description])},MobileStatusTag:{props:['status','label'],setup:p=>()=>h('span',p.label||p.status)},
    MobileSafeAreaBar:{setup:(_,{slots})=>()=>h('footer',slots.default?.())}}
  const render=compile(template,{isCustomElement:tag=>['view','text','picker','image'].includes(tag)})
  const events=compile(template,{isCustomElement:tag=>['view','text','picker','image'].includes(tag)||/^[A-Z]/.test(tag)})
  return {vm,html:()=>renderToString(createSSRApp({components,render:()=>render(vm,[])})),tree:()=>events(vm,[])}
}
function nodes(node,predicate,result=[]) {if(!node||typeof node!=='object')return result;if(predicate(node))result.push(node);for(const child of Array.isArray(node.children)?node.children:[])nodes(child,predicate,result);return result}

test('学生通知和材料空态保留真实无数据及批次返回，不重复实现说明',async()=>{
  const notice=page('notices'),material=page('materials')
  for(const p of [notice,material])assert.match(await p.html(),/pages\/student-internship\/index\?batchId=18/)
  assert.match(await notice.html(),/当前批次暂无有效通知公告/);assert.doesNotMatch(await notice.html(),/强制弹框确认|岗位实习通知公告/)
  assert.match(await material.html(),/当前批次暂无材料任务/);assert.doesNotMatch(await material.html(),/不可变文件版本|病毒扫描未通过的文件不能进入审核和归档/)
  notice.vm.state='error';material.vm.state='error'
  assert.doesNotMatch(await notice.html(),/当前批次暂无有效通知公告/);assert.doesNotMatch(await material.html(),/当前批次暂无材料任务/)
})

test('学生计划详情实际展开保留原条目零值，任务退回与确认动作不因折叠消失',async()=>{
  const p=page('plan');p.vm.plan={id:'61',version:3,title:'合成实习计划',ackStatus:'PENDING',ackStatusLabel:'待确认',planNo:'原计划编号',majorName:'软件技术',objectives:'原完整目标',content:'原完整正文',rulesSnapshot:{requiredCheckinDays:0,summaryRequiredCount:1},basicSnapshot:{startDate:'2026-09-01',endDate:'2026-09-30'}}
  p.vm.summary={total:1,approved:0,rate:0};p.vm.minimumWords=10;p.vm.tasks=[{sortOrder:1,name:'岗位总结',progressStatus:'REJECTED',reviewComment:'补充实际工作',requirement:'原任务要求',_note:'未提交草稿',_evidenceFileId:'201'}]
  let html=await p.html();assert.match(html,/任务完成 0\/1/);assert.match(html,/待确认/);assert.match(html,/确认已阅读当前版本计划/);assert.match(html,/补充实际工作/);assert.doesNotMatch(html,/修改后重新提交|原计划编号|原完整正文/)
  nodes(p.tree(),n=>n.type==='button'&&n.props?.['aria-expanded']===false)[0].props.onClick();html=await p.html()
  for(const text of ['原计划编号','原完整目标','原完整正文','0 天','1 篇'])assert.ok(html.includes(text),text)
  p.vm.plan.ackStatus='ACKNOWLEDGED';p.vm.plan.ackStatusLabel='已确认';html=await p.html();assert.match(html,/修改后重新提交/);assert.doesNotMatch(html,/确认已阅读当前版本计划/)
  p.vm.plan={...p.vm.plan,version:4};assert.doesNotMatch(await p.html(),/原计划编号/);assert.equal(p.vm.tasks[0]._note,'未提交草稿')
})

test('任务完成后学生可回读原完成说明，通过意见不会误标为退回且无重复提交',async()=>{
  const p=page('plan');p.vm.plan={id:'61',version:3,title:'合成计划',ackStatus:'ACKNOWLEDGED',ackStatusLabel:'已确认'}
  p.vm.summary={total:1,approved:1,rate:100};p.vm.tasks=[{sortOrder:1,name:'岗前任务',progressStatus:'APPROVED',progressStatusLabel:'已完成',studentNote:'手机补正后的原完成说明',reviewComment:'导师确认符合任务要求'}]
  const html=await p.html();assert.match(html,/手机补正后的原完成说明/);assert.match(html,/教师意见：导师确认符合任务要求/)
  assert.doesNotMatch(html,/退回：|修改后重新提交|提交完成情况|未提交内容已保留/)
})

test('学生保险日期选择写回原字段，历史和已核验只读守卫及扫描禁提交保持',async()=>{
  const p=page('insurance');p.vm.info={status:'NOT_SUBMITTED',statusLabel:'未提交',version:0}
  let dates=nodes(p.tree(),n=>n.type==='picker'&&n.props?.mode==='date');assert.equal(dates.length,2)
  dates[0].props.onChange({detail:{value:'2026-09-01'}});dates[1].props.onChange({detail:{value:'2027-01-31'}})
  assert.equal(p.vm.form.effectiveDate,'2026-09-01');assert.equal(p.vm.form.expiryDate,'2027-01-31')
  let html=await p.html();for(const label of ['承保单位 *','保单号 *','生效日期 *','到期日期 *','保险凭证 *'])assert.ok(html.includes(label),label)
  assert.ok(nodes(p.tree(),n=>n.type==='button'&&n.props?.onClick===p.vm.submit)[0].props.disabled)
  p.vm.info={status:'VERIFIED',statusLabel:'已核验',canRenew:false};assert.equal(p.vm.readonly,true);assert.ok(nodes(p.tree(),n=>n.type==='picker').every(n=>n.props.disabled));assert.doesNotMatch(await p.html(),/提交保险信息/)
  p.vm.info={status:'VERIFIED',canRenew:true,coverageReason:'保障已过期'};assert.equal(p.vm.readonly,false);assert.match(await p.html(),/保障已过期/)
  p.vm.historyMode=true;assert.equal(p.vm.readonly,true)
})

test('学生材料退回理由格式数量和安全失败仍可见，原模板查看与重交动作保留',async()=>{
  const p=page('materials');p.vm.items=[{id:'31',materialName:'企业接收函',isRequired:true,minFiles:1,maxFiles:2,allowedFormatLabel:'PDF文档',template:{fileName:'学校模板',versionNo:3},submission:{status:'RETURNED',statusLabel:'已退回',reviewComment:'请补清晰印章',files:[{slotNo:1,fileId:'41',fileName:'原接收函',versionNo:1,statusText:'安全可用'}]}}]
  p.vm.pendingByRequirement={'31':[{fileId:'42',fileName:'重交材料',readyForBusiness:false,statusText:'安全扫描中'}]};p.vm.materialErrors={'31':'材料尚未安全可用，请读取扫描结果'}
  p.vm.previousOpen={'31':true};p.vm.requirementsOpen=true
  const html=await p.html();for(const text of ['请补清晰印章','PDF文档','需交1～2份','下载模板','查看','本次重交','安全扫描中','材料尚未安全可用'])assert.ok(html.includes(text),text)
  const submit=nodes(p.tree(),n=>n.type==='button'&&n.children==='重新提交审核')[0];assert.equal(submit.props.disabled,true)
})
