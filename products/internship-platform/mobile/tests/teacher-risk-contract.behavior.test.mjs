import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { normalizeError, request } from './request-module.mjs'
import { formatDateTime } from '../src/utils/format.js'
import { positionQuery, positionListUrl, positionFacts } from '../src/modules/internshipPositionModel.js'

const BIG='9007199254740993001', RISK='9007199254740993009'
const deferred=()=>{let resolve;const promise=new Promise(done=>{resolve=done});return {promise,resolve}}
const settled=()=>new Promise(resolve=>setImmediate(resolve))
function api(handler=()=>({items:[],total:0})) {
  const calls=[]
  const source=fs.readFileSync(new URL('../src/services/teacherApi.js',import.meta.url),'utf8').replace(/^import[^\n]+\r?\n/gm,'').replace('export const teacherApi','const teacherApi').replace('export default teacherApi','return teacherApi')
  const realRequest=(url,options={})=>{const call={url,method:options.method||'GET',data:options.data};calls.push(call);return Promise.resolve().then(()=>handler(call))}
  return {calls,value:new Function('realRequest','sequential','teacherInternshipEvidenceV3Api',source)(realRequest,{}, {})}
}
function component(path,deps={}) {
  const source=fs.readFileSync(new URL('../src/'+path,import.meta.url),'utf8'),script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm,'').replace('export default','return')
  return {source,value:new Function(...Object.keys(deps),script)(...Object.values(deps))}
}
function mount(value) {
  const vm={...(value.data?.()||{})};for(const [k,fn]of Object.entries(value.methods||{}))vm[k]=fn.bind(vm)
  for(const[k,fn]of Object.entries(value.computed||{}))Object.defineProperty(vm,k,{get:fn.bind(vm)})
  return vm
}
function fixture(kind='risk',handler,extra={}) {
  let generation=0
  const transport=api(handler),permissions=new Set(['internship.risk.view','internship.risk.handle','internship.score.manage','internship.position.view']),modals=[],messages=[],navigations=[]
  if (kind === 'score') permissions.add('internship.student.view')
  const context={selectedBatchId:BIG,selectedBatch:{id:BIG,name:'合成批次'},batches:[{id:BIG,name:'合成批次'},{id:'22',name:'另一批次'}],restore(){},load:async()=>{},can:permission=>permissions.has(permission),selectBatch(id){this.selectedBatchId=String(id||'');return !!id}}
  const uni={showModal:modal=>modals.push(modal),showToast:message=>messages.push(message),stopPullDownRefresh(){},redirectTo:item=>navigations.push(item.url)}
  const path=kind==='risk'?'pages/teacher-internship/internship-risk/index.vue':kind==='score'?'pages/teacher-internship/internship-score/index.vue':'pages/teacher-internship/internship-positions/detail.vue'
  const loaded=component(path,{teacherApi:transport.value,normalizeError,toast:text=>messages.push(text),useInternshipContextStore:()=>context,currentSessionGeneration:()=>generation,uni,createSubmitLock:request.createSubmitLock,teacherInternshipScores:async()=>({items:[]}),teacherInternshipMyStudents:async()=>({list:[]}),teacherInternshipPositionDetail:async()=>({}),positionQuery,positionListUrl,positionFacts,formatDateTime,...extra})
  return {vm:mount(loaded.value),component:loaded.value,source:loaded.source,transport,context,permissions,modals,messages,navigations,switchIdentity:()=>generation++}
}
function renderPage(p) {
  const template=p.source.slice(p.source.indexOf('<template>')+10,p.source.indexOf('<script>')).replace(/<\/template>\s*$/,'')
  const shell={setup:(_,{slots})=>()=>h('div',slots.default?.())}
  const components={MobileGlobalState:{props:['state','title','description'],setup:(q,{slots})=>()=>q.state==='ready'?h('div',slots.default?.()):h('div',[q.state,q.title,q.description])},MobileNavBar:{props:['title'],setup:q=>()=>h('nav',q.title)},MobileStatusTag:{props:['label'],setup:q=>()=>h('span',q.label)},MobileInlineAlert:{props:['title','description'],setup:q=>()=>h('p',[q.title,q.description])},MobileSegmented:{render:()=>null},MobileSafeAreaBar:shell}
  const render=compile(template,{isCustomElement:t=>['view','text','picker'].includes(t)})
  const events=compile(template,{isCustomElement:t=>['view','text','picker'].includes(t)||/^[A-Z]/.test(t)})
  return {html:()=>renderToString(createSSRApp({components,render:()=>render(p.vm,[])})),tree:async()=>{let tree;await renderToString(createSSRApp({render:()=>{tree=events(p.vm,[]);return tree}}));return tree}}
}
function nodes(node,predicate,result=[]) {if(!node||typeof node!=='object')return result;if(predicate(node))result.push(node);for(const child of Array.isArray(node.children)?node.children:[])nodes(child,predicate,result);return result}

test('已关闭风险只显示真实结案结果，旧动作和旧阻断不再误导，未关闭仍保留阻断',async()=>{
  const risk={id:RISK,status:'CLOSED',studentName:'合成学生',riskTitle:'合成返岗风险',currentAction:'继续核实销假',closeBlockers:['请先核实返岗'],closeAllowed:false}
  const p=fixture('risk',()=>({items:[risk],total:1}));await p.vm.load();let html=await renderPage(p).html()
  assert.match(html,/结案结果/);assert.match(html,/本条风险已关闭/);assert.doesNotMatch(html,/继续核实销假|关闭条件未满足|请先核实返岗|高风险事项优先处理/)
  p.vm.list=[{...risk,status:'PROCESSING'}];html=await renderPage(p).html();assert.match(html,/关闭条件未满足/);assert.match(html,/请先核实返岗/)
  p.vm.doClose({...risk,status:'PROCESSING'});assert.equal(p.modals.length,0)
})

test('教师正式风险及成绩SDK捕获真实请求构造，保留大编号和零版本且缺批次不发请求',async()=>{
  const t=api();await assert.rejects(()=>t.value.getInternshipRisks(),e=>e.message.includes('批次'));assert.equal(t.calls.length,0)
  await t.value.getInternshipRisks({batchId:BIG,page:2,pageSize:20,status:'PROCESSING'})
  await t.value.handleInternshipRisk(RISK,{comment:'原受理意见',expectedVersion:0});await t.value.followInternshipRisk(RISK,{note:'原跟进说明',expectedVersion:1});await t.value.closeInternshipRisk(RISK,{result:'RESOLVED',comment:'原关闭说明',expectedVersion:2});await t.value.computeInternshipScore({internshipId:RISK,batchId:BIG,expectedVersion:0})
  assert.deepEqual(t.calls.map(x=>new URL(x.url,'http://local.invalid').pathname),['/internship/risks',`/internship/risks/${RISK}/handle`,`/internship/risks/${RISK}/follow`,`/internship/risks/${RISK}/close`,'/internship/scores/compute'])
  const query=new URL(t.calls[0].url,'http://local.invalid').searchParams;assert.equal(query.get('batchId'),BIG);assert.equal(query.get('page'),'2');assert.equal(query.get('pageSize'),'20');assert.equal(query.get('status'),'PROCESSING')
  assert.deepEqual(t.calls.slice(1).map(x=>x.method),['POST','POST','POST','POST']);assert.equal(t.calls[1].data.expectedVersion,0);assert.deepEqual(t.calls[4].data,{internshipId:RISK,batchId:BIG,expectedVersion:0})
})

test('风险实际分类组件点击传合同key，分页请求保持批次大编号',async()=>{
  const p=fixture('risk',()=>({items:[{id:RISK,status:'PENDING_HANDLE'}],total:41}));await p.vm.load();await p.vm.loadPage(2);assert.equal(p.vm.page,2);assert.equal(p.vm.list[0].id,RISK)
  const seg=nodes(await renderPage(p).tree(),n=>n.type==='MobileSegmented')[0],loaded=component('components/MobileSegmented.vue')
  const template=loaded.source.slice(loaded.source.indexOf('<template>')+10,loaded.source.indexOf('<script>')).replace(/<\/template>\s*$/,'')
  const render=compile(template,{isCustomElement:t=>['scroll-view','view','text'].includes(t)})
  const values=[],vm={items:seg.props.items,modelValue:p.vm.status,$emit:(event,value)=>{values.push(value);return seg.props['onUpdate:modelValue'](value)}}
  for(const index of [0,1,2]){const tree=render(vm,[]);nodes(tree,n=>n.type==='button')[index].props.onClick();await settled()}
  assert.deepEqual(values,['PENDING_HANDLE','PROCESSING','']);assert.equal(p.vm.page,1)
  assert.equal(new URL(p.transport.calls.at(-1).url,'http://local.invalid').searchParams.get('status'),'')
})

test('风险缺批次或无查看权限不读取，403归为无权而非系统失败',async()=>{
  const p=fixture();p.context.selectedBatchId='';await p.vm.load();assert.equal(p.transport.calls.length,0);assert.deepEqual(p.vm.list,[])
  p.context.selectedBatchId=BIG;p.permissions.delete('internship.risk.view');await p.vm.load();assert.equal(p.vm.state,'forbidden');assert.equal(p.transport.calls.length,0)
  const denied=fixture('risk',()=>{throw {httpStatus:403,bizCode:'NO_PERMISSION',message:'denied'}});await denied.vm.load();assert.equal(denied.vm.state,'forbidden')
})

test('风险切换批次后的旧异步列表不能覆盖新批次',async()=>{
  const old=deferred(),started=deferred();const p=fixture('risk',call=>{if(new URL(call.url,'http://local.invalid').searchParams.get('batchId')===BIG){started.resolve();return old.promise}return {items:[{id:'new'}],total:1}})
  const first=p.vm.load();await started.promise;await p.vm.onBatch({detail:{value:1}});old.resolve({items:[{id:'old'}],total:99});await first
  assert.equal(p.vm.batchId,'22');assert.deepEqual(p.vm.list,[{id:'new'}]);assert.equal(p.vm.total,1)
})

test('风险失去办理权限和明确关闭阻断均不能开启写入',async()=>{
  const p=fixture();await p.vm.load();p.permissions.delete('internship.risk.handle')
  p.vm.doHandle({id:RISK,status:'PENDING_HANDLE',version:0});p.vm.doFollow({id:RISK,status:'PROCESSING',version:0});p.vm.doClose({id:RISK,status:'PROCESSING',version:0});assert.equal(p.modals.length,0)
  p.permissions.add('internship.risk.handle');p.vm.doClose({id:RISK,status:'PROCESSING',closeAllowed:false,version:0});assert.equal(p.modals.length,0)
  p.vm.doHandle({id:RISK,status:'PENDING_HANDLE',version:0});p.permissions.delete('internship.risk.handle');p.modals[0].success({confirm:true,content:'明确原受理意见'});await settled();assert.equal(p.transport.calls.filter(x=>x.method==='POST').length,0)
})

test('风险原弹窗在上下文批次变化后不发送旧对象命令',async()=>{
  for(const [method,status]of [['doHandle','PENDING_HANDLE'],['doFollow','PROCESSING'],['doClose','PROCESSING']]){
    const p=fixture();await p.vm.load();p.vm[method]({id:RISK,status,version:0,closeAllowed:true});assert.equal(p.modals.length,1)
    p.context.selectedBatchId='22';p.modals[0].success({confirm:true,content:'上下文切换前的原说明'});await settled()
    assert.equal(p.transport.calls.filter(x=>x.method==='POST').length,0,method)
  }
})

test('风险未知状态中文兜底且来源中文，关闭理由保留',async()=>{
  const p=fixture();p.vm.state='ready';p.vm.list=[{id:RISK,studentName:'合成学生',riskTitle:'原风险事项',riskLevel:'INTERNAL_LEVEL',status:'INTERNAL_STATUS',sourceType:'INCIDENT',closeAllowed:false,closeBlockers:['缺少调查结论']}]
  const html=await renderPage(p).html();for(const text of ['原风险事项','风险等级待确认','状态待确认','实习事件','缺少调查结论'])assert.ok(html.includes(text),text);assert.doesNotMatch(html,/INTERNAL_LEVEL|INTERNAL_STATUS/)
  assert.equal(p.vm.sourceText({sourceType:'LEAVE'}),'请假与销假')
})

test('成绩真实模板分别呈现零分缺项和待审核，不生成手工评分输入',async()=>{
  const p=fixture('score');Object.assign(p.vm,{state:'ready',batches:[{id:BIG,name:'原批次'}],batchId:BIG,list:[{id:'1',studentName:'合成学生',status:'PENDING_REVIEW',statusLabel:'待学校复核',totalScore:0,checkinScore:0,weeklyScore:null,monthlyScore:null,enterpriseScore:null,schoolScore:0,incomplete:true,incompleteReason:'企业评价未审核'}]})
  assert.equal(p.vm.scoreText(0),0);assert.equal(p.vm.scoreText(null),'—');let html=await renderPage(p).html();for(const text of ['加权总分','0','—','待审核','企业评价未审核'])assert.ok(html.includes(text),text)
  p.vm.list[0].incomplete=false;html=await renderPage(p).html();assert.match(html,/已提交学校复核/);assert.match(html,/教师端不能直接发布/)
  p.vm.tab='compute';p.vm.students=[{id:RISK,name:'合成学生'}];html=await renderPage(p).html();assert.doesNotMatch(html,/<input|<textarea/);assert.match(html,/已审核的企业评价/)
})

test('岗位详情保留零名额零报酬否值完整事实和原筛选返回',async()=>{
  const p=fixture('position');p.vm.state='ready';p.vm.scope=positionQuery({batchId:BIG,status:'RISK',keyword:'原关键字',page:'3'});p.vm.detail={id:RISK,batchId:BIG,title:'原岗位',batchName:'原批次',companyName:'原企业',statusLabel:'已发布',remaining:0,headcount:0,remunerationAmount:0,nightShift:false,overtimeAllowed:false,accommodationProvided:false,mealProvided:false,hazardousFlag:false,campaignId:'7',workContent:'原岗位工作全文'}
  let html=await renderPage(p).html();for(const text of ['0 / 0 人','0 元','否','原岗位工作全文','志愿投递需符合招聘范围和学生资格'])assert.ok(html.includes(text),text)
  p.vm.returnToList();const url=new URL(p.navigations[0],'http://local.invalid');assert.equal(url.searchParams.get('batchId'),BIG);assert.equal(url.searchParams.get('status'),'RISK');assert.equal(url.searchParams.get('keyword'),'原关键字');assert.equal(url.searchParams.get('page'),'3')
})

test('风险写入旧回包不能覆盖切批次后的回执和当前读取',async()=>{
  const response=deferred(),started=deferred();const p=fixture('risk',call=>{if(call.method==='POST'){started.resolve();return response.promise}return {items:[],total:0}});await p.vm.load()
  p.vm.doHandle({id:RISK,status:'PENDING_HANDLE',version:0,riskTitle:'旧批次事项'});p.modals[0].success({confirm:true,content:'原风险受理说明'});await started.promise
  p.context.selectBatch('22');p.vm.acting=false;await p.vm.load();const currentReceipt={object:'新批次回执'};p.vm.lastReceipt=currentReceipt
  response.resolve({id:RISK,status:'PROCESSING',version:1});await settled()
  assert.equal(p.vm.lastReceipt,currentReceipt);assert.equal(p.vm.batchId,'22')
})

test('成绩核算界面失权后缓存学生不能继续发送核算命令',async()=>{
  const p=fixture('score',()=>{throw {httpStatus:403,bizCode:'NO_PERMISSION'}});Object.assign(p.vm,{state:'ready',tab:'compute',batchId:BIG,students:[{id:RISK,name:'合成学生'}],list:[]});p.permissions.delete('internship.score.manage')
  assert.equal(p.vm.canCompute,false);p.vm.submit();await settled();assert.equal(p.transport.calls.filter(x=>x.method==='POST').length,0);assert.doesNotMatch(await renderPage(p).html(),/提交核算|按当前版本重新核算/)
})

test('风险新会话或隐藏后的原弹窗不能发送受理跟进关闭命令',async()=>{
  for(const stop of ['identity','hide'])for(const [method,status]of [['doHandle','PENDING_HANDLE'],['doFollow','PROCESSING'],['doClose','PROCESSING']]){
    const p=fixture();await p.vm.load();p.vm[method]({id:RISK,status,version:0,closeAllowed:true});assert.equal(p.modals.length,1)
    if(stop==='identity')p.switchIdentity();else p.component.onHide.call(p.vm)
    p.modals[0].success({confirm:true,content:'原身份原页面说明'});await settled();assert.equal(p.transport.calls.filter(x=>x.method==='POST').length,0,`${stop}:${method}`)
  }
})

test('风险读取期间切换会话不回填旧身份的列表',async()=>{
  const late=deferred(),started=deferred();const p=fixture('risk',()=>{started.resolve();return late.promise});const reading=p.vm.load();await started.promise;p.switchIdentity();late.resolve({items:[{id:'old-private'}],total:1});await reading
  assert.equal(p.vm.list,null);assert.notEqual(p.vm.state,'ready')
})

test('风险首次加载不重复请求，加载途中隐藏返回会重新读取而不永久等待',async()=>{
  const late=deferred(),started=deferred();let reads=0;const p=fixture('risk',()=>{reads++;if(reads===1){started.resolve();return late.promise}return {items:[{id:'fresh'}],total:1}})
  const reading=p.vm.load();p.component.onShow.call(p.vm);await started.promise;assert.equal(reads,1)
  p.component.onHide.call(p.vm);late.resolve({items:[{id:'old'}],total:1});await reading;assert.equal(p.vm.list,null)
  p.component.onShow.call(p.vm);await settled();assert.equal(reads,2);assert.equal(p.vm.state,'ready');assert.deepEqual(p.vm.list,[{id:'fresh'}])
})
