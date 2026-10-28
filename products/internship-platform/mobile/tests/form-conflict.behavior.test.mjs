import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { normalizeError } from './request-module.mjs'
import { formatDateTime } from '../src/utils/format.js'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { loadReportMedia, releasePreview } from '../src/services/reportMedia.mjs'

const conflict={code:1,bizCode:'DATA_CONFLICT',httpStatus:400}
const context={batchId:'18',internshipId:'21'}
const dashboard={batchId:'18',recordId:'21',statusText:'READY',destinationType:'NONE'}
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function page(path,api={}) {
  const source=fs.readFileSync(new URL('../src/pages/'+path,import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
  const names=[...source.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"];?\s*/gm)]
    .flatMap(([,bindings])=>bindings.replace(/[{}]/g,'').split(',').map(name=>name.trim()))
  names.push('uni')
  let generation=0,modal
  const store={can:()=>true,selectedBatchId:'18',batches:[{id:'18'}],restore(){},load:async()=>{}}
  const notices=[],deps={formatDateTime,normalizeError,currentSessionGeneration:()=>generation,toast:text=>notices.push(text),
    useInternshipContextStore:()=>store,studentApi:{getInternship:async()=>dashboard,getInternshipApplicationPositions:async()=>({batchId:'18',internshipId:'21',hasMore:false,items:[]})},
    uni:{showModal:options=>{modal=options}},...api}
  const component=new Function(...names,source.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return'))(...names.map(name=>deps[name]??{}))
  const vm={...component.data(),$refs:{}}
  for(const [name,method] of Object.entries(component.methods))vm[name]=method.bind(vm)
  for(const [name,getter] of Object.entries(component.computed||{}))Object.defineProperty(vm,name,{get:getter.bind(vm)})
  if(!component.computed?.context)vm.context={...context}
  vm.batchId='18';vm.state='ready';vm.pageState='ready'
  return {vm,component,notices,modal:()=>modal,switchAccount:()=>generation++}
}
function application(api={}) {
  const p=page('student-internship/application/index.vue',api)
  p.vm.recordStatus='READY';p.vm.destinationType='NONE'
  p.vm.selectedPositionId='31';p.vm.positions=[{id:'31',remaining:1,canSelect:true,title:'合成岗位'}];p.vm.editableApplication={id:'41',version:3,status:'DRAFT'}
  Object.assign(p.vm.form,{applicationNote:'本人申请岗位的合成说明',evidenceFileId:'51',agreementFileIds:['52']})
  p.vm.evidenceFileName='合成证明';return p
}

function applicationMaterialPreview(sdk) {
  const source=fs.readFileSync(new URL('../src/components/ReportFilePreview.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
  const script=source.replace(/^import[^\n]+\r?\n/gm,'').replace('export default','return')
  const component=new Function('fileSdk','normalizeError','currentSessionGeneration','loadReportMedia','releasePreview',script)(sdk,normalizeError,()=>0,loadReportMedia,releasePreview)
  const vm={...component.data()};for(const [key,method] of Object.entries(component.methods))vm[key]=method.bind(vm)
  return vm
}

function applicationView(p) {
  const source=fs.readFileSync(new URL('../src/pages/student-internship/application/index.vue',import.meta.url),'utf8')
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const shell={setup:(_,{slots})=>()=>h('div',slots.default?.())}
  const components={MobileGlobalState:shell,MobileSafeAreaBar:shell,MobilePrivacyGate:{render:()=>null},ReportFilePreview:{render:()=>null},
    MobileInlineAlert:{props:['title','description'],setup:props=>()=>h('p',props.title+' '+props.description)},
    MobileNavBar:{props:['title','fallbackUrl'],setup:props=>()=>h('nav',{'data-return':props.fallbackUrl},props.title)},
    MobileStatusTag:{props:['status','label'],setup:props=>()=>h('span',props.label||props.status)}}
  const render=compile(template,{isCustomElement:tag=>['view','text','picker'].includes(tag)})
  const eventTree=compile(template,{isCustomElement:tag=>['view','text','picker'].includes(tag)||/^[A-Z]/.test(tag)})
  return {html:()=>renderToString(createSSRApp({components,render:()=>render(p.vm,[])})),tree:()=>eventTree(p.vm,[])}
}
function applicationNode(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;for(const child of Array.isArray(node.children)?node.children:[]){const found=applicationNode(child,predicate);if(found)return found}return null}

test('申请结果首屏精简并保留零薪资材料，展开可读完整原单且换原单自动收起',async()=>{
  const p=application(),original={id:'71',recordId:'21',applicationType:'SELF_ARRANGED',status:'APPROVED',version:8,companyName:'已落实企业',positionName:'已落实岗位',internshipStartDate:'2026-09-01',internshipEndDate:'2026-12-31',agreedSalary:0,majorMatch:false,companyCreditCode:'完整原单信用代码',contactName:'原联系人',workAddress:'原岗位详细地址',evidenceFileId:'501',agreementFileIds:['502'],reviewComment:'审核通过意见'}
  p.vm.history=[original,{id:'40',status:'WITHDRAWN',version:2,companyName:'旧申请企业'}];p.vm.editableApplication=null;p.vm.destinationType='SELF_ARRANGED'
  const view=applicationView(p);let html=await view.html();assert.match(html,/实习申请/);assert.match(html,/pages\/student-internship\/index\?batchId=18/)
  for(const value of ['已通过','已落实企业','已落实岗位','2026-09-01','2026-12-31','0 元\/月','审核通过意见','第8版','申请详情','旧申请企业'])assert.match(html,new RegExp(value))
  assert.doesNotMatch(html,/完整原单信用代码|原联系人|原岗位详细地址|选择学校已发布岗位，或填写/)
  assert.equal((html.match(/查看材料/g)||[]).length,2);assert.equal((html.match(/审核通过意见/g)||[]).length,1)
  applicationNode(view.tree(),node=>node.type==='button'&&node.props?.['aria-expanded']===false).props.onClick()
  html=await view.html();for(const value of ['完整原单信用代码','原联系人','原岗位详细地址','专业是否对口','否'])assert.ok(html.includes(value),value)
  p.vm.context={batchId:'19',internshipId:'22'};assert.doesNotMatch(await view.html(),/完整原单信用代码/)
  assert.equal(original.version,8);assert.equal(original.majorMatch,false);assert.equal(original.agreedSalary,0)
})

test('申请待审原单撤回入口保留且退回编辑字段与冲突核对不折叠',async()=>{
  const p=application();p.vm.editableApplication=null;p.vm.history=[{id:'71',recordId:'21',applicationType:'SELF_ARRANGED',status:'PENDING_REVIEW',version:8,companyName:'待审企业',positionName:'待审岗位',agreedSalary:0}]
  let withdrawn; p.vm.withdraw=row=>{withdrawn=row};let view=applicationView(p),html=await view.html();assert.equal((html.match(/撤回申请/g)||[]).length,1)
  applicationNode(view.tree(),node=>node.type==='button'&&node.children==='撤回申请').props.onClick();assert.equal(withdrawn,p.vm.history[0])
  const rejected={...p.vm.history[0],status:'REJECTED',reviewComment:'请补正注册地址'};p.vm.history=[rejected];p.vm.editableApplication=rejected;p.vm.typeIndex=1
  html=await view.html();assert.match(html,/请补正注册地址/);assert.match(html,/请输入企业全称/);assert.match(html,/请输入详细注册地址/);assert.match(html,/提交审核/)
  p.vm.conflict={error:'版本已变化，请核对原单',latest:{id:'71',version:9,statusLabel:'已退回',companyName:'最新企业',applicationNote:'最新说明',reviewComment:'新审核意见'}}
  html=await view.html();assert.match(html,/读取最新原单/);assert.match(html,/第9版/);assert.match(html,/已核对原单，保留填写内容继续/)
})

test('移动申请原单材料通过真实预览组件校验编号扫描权限，拒绝外来材料且不改原单',async()=>{
  const original={id:'71',recordId:'21',version:8,status:'APPROVED',evidenceFileId:'221',agreementFileIds:['222','221'],majorMatch:false,agreedSalary:0}
  let downloaded=0,mode='ready'
  const sdk={metadata:async id=>({fileId:mode==='wrong'?'999':id,fileName:'合成证明.pdf',status:'AVAILABLE',scanStatus:mode==='pending'?'PENDING':'CLEAN',readyForBusiness:mode!=='pending',allowedActions:mode==='denied'?[]:['download']}),download:async()=>{downloaded++;return {tempFilePath:'/authorized-material'}}}
  const p=application(),preview=applicationMaterialPreview(sdk)
  p.vm.history=[original];p.vm.editableApplication=null;p.vm.$refs.applicationMaterialPreview=preview
  assert.deepEqual(p.vm.applicationMaterials.map(file=>file.fileId),['221','222'])
  await p.vm.openApplicationMaterial('999');assert.equal(downloaded,0);assert.match(p.vm.materialError,/不属于当前原单/)
  for(mode of ['pending','denied','wrong']){await p.vm.openApplicationMaterial('221');assert.equal(downloaded,0);assert.equal(preview.state,'error');assert.ok(preview.errorText);assert.match(p.vm.materialError,/查看权限.*安全扫描/)}
  mode='ready';await p.vm.openApplicationMaterial('221');assert.equal(downloaded,1);assert.equal(preview.state,'ready');assert.equal(preview.name,'合成证明.pdf')
  assert.equal(p.vm.displayApplication,original);assert.equal(original.version,8);assert.equal(original.agreedSalary,0);assert.equal(original.majorMatch,false)
})

test('移动申请材料离页卸载或换原单批次账号取消迟到预览',async()=>{
  for(const action of ['hide','unload','scope','account']){
    const wait=deferred();let downloads=0
    const p=application(),preview=applicationMaterialPreview({metadata:()=>wait.promise,download:async()=>{downloads++;return {tempFilePath:'/old-material'}}})
    p.vm.history=[{id:'71',recordId:'21',version:8,status:'APPROVED',evidenceFileId:'221'}];p.vm.editableApplication=null;p.vm.$refs.applicationMaterialPreview=preview
    const pending=p.vm.openApplicationMaterial('221')
    if(action==='hide')p.component.onHide.call(p.vm)
    else if(action==='unload')p.component.onUnload.call(p.vm)
    else if(action==='scope'){p.vm.context={batchId:'19',internshipId:'22'};p.component.watch.applicationFileScope.call(p.vm)}
    else {p.switchAccount();p.vm.load=()=>{};p.component.onShow.call(p.vm)}
    wait.resolve({fileId:'221',fileName:'旧证明.pdf',status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true,allowedActions:['download']})
    await pending;assert.equal(downloads,0,action);assert.equal(preview.visible,false,action);assert.equal(preview.url,'',action)
  }
})

test('申请初始加载先解析指定批次，再用精确本人上下文读取原单和真实岗位库',async()=>{
  const calls=[],p=page('student-internship/application/index.vue',{
    studentApi:{getInternship:async batch=>{calls.push(['dashboard',batch]);return {...dashboard,hasBatch:true}},
      getInternshipApplicationPositions:async(batch,record)=>{calls.push(['positions',batch,record]);return {items:[],total:0,page:1,hasMore:false,batchId:batch,internshipId:record}}},
    studentInternshipApplications:async(batch,record)=>{calls.push(['applications',batch,record]);return [{id:'41',recordId:'21',applicationType:'SELF_ARRANGED',status:'DRAFT',version:3,companyName:'电脑原单'}]}
  })
  p.vm.requestedBatchId='18';await p.vm.load()
  assert.deepEqual(calls[0],['dashboard','18']);assert.deepEqual(calls.find(x=>x[0]==='applications'),['applications','18','21']);assert.deepEqual(calls.find(x=>x[0]==='positions'),['positions','18','21'])
  assert.equal(p.vm.pageState,'ready');assert.equal(p.vm.editableApplication.id,'41');assert.equal(p.vm.form.companyName,'电脑原单')
})

test('移动申请已通过及已落实去向只能读取原单，不显示新申请也不发送写请求',async()=>{
  let writes=0
  const original={id:'71',recordId:'21',applicationType:'SELF_ARRANGED',status:'APPROVED',version:8,companyName:'已落实企业',positionName:'已落实岗位',agreedSalary:0,majorMatch:false,evidenceFileId:'501',agreementFileIds:['502'],applicationNote:'完整原申请说明',reviewComment:'审核通过意见'}
  const p=page('student-internship/application/index.vue',{studentApi:{getInternship:async()=>({...dashboard,statusText:'READY',destinationType:'SELF_ARRANGED'}),getInternshipApplicationPositions:async()=>({batchId:'18',internshipId:'21',items:[],total:0,hasMore:false})},studentInternshipApplications:async()=>[original],studentInternshipApplicationSave:async()=>{writes++;return original},studentInternshipApplicationSubmit:async()=>{writes++},studentInternshipApplicationWithdraw:async()=>{writes++}})
  await p.vm.load();await p.vm.saveDraft();await p.vm.submit();p.vm.withdraw(original)
  assert.equal(writes,0);assert.equal(p.vm.canWriteApplication,false)
  assert.equal(p.vm.displayApplication.id,'71');assert.equal(p.vm.displayApplication.version,8);assert.equal(p.vm.displayApplication.agreedSalary,0);assert.equal(p.vm.displayApplication.majorMatch,false)
  assert.deepEqual(p.vm.displayApplication.agreementFileIds,['502']);assert.equal(p.vm.displayApplication.evidenceFileId,'501');assert.equal(p.vm.displayApplication.reviewComment,'审核通过意见')
  assert.match(p.vm.readOnlyNextStep,/去向已落实/)
  assert.equal(p.vm.readOnlyItems.find(item=>item.label==='约定实习薪资').value,'0 元/月')
  assert.equal(p.vm.readOnlyItems.find(item=>item.label==='专业是否对口').value,'否')
  const html=await applicationView(p).html()
  assert.ok(html.includes('原申请及办理结果'));assert.ok(html.includes('第8版'));assert.ok(html.includes('0 元/月'));assert.ok(html.includes('审核通过意见'))
  assert.equal((html.match(/查看材料/g)||[]).length,2);assert.ok(html.includes('申请佐证材料'));assert.ok(html.includes('三方协议材料 1'))
  assert.ok(!html.includes('保存草稿') && !html.includes('提交审核'))
})

test('移动申请写入口按真实实习状态和去向收敛，待审与历史不创建新单',async()=>{
  for(const facts of [{recordStatus:'READY',destinationType:'SELF_ARRANGED'}, {recordStatus:'ONBOARD',destinationType:'NONE'}, {recordStatus:'READY',destinationType:'NONE',historyMode:true}, {recordStatus:'READY',destinationType:'NONE',pending:true}]){
    let writes=0;const p=application({studentInternshipApplicationSave:async()=>{writes++},studentInternshipApplicationSubmit:async()=>{writes++}})
    Object.assign(p.vm,facts);if(facts.pending)p.vm.history=[{id:'41',status:'PENDING_REVIEW'}]
    await p.vm.saveDraft();await p.vm.submit();assert.equal(writes,0);assert.equal(p.vm.canWriteApplication,false)
  }
  const writable=application();assert.equal(writable.vm.canWriteApplication,true)
})

test('申请岗位读取失败明确错误，隐藏或换账号的迟到目录不能进入页面',async()=>{
  const failed=page('student-internship/application/index.vue',{studentInternshipApplications:async()=>[],studentApi:{getInternship:async()=>dashboard,getInternshipApplicationPositions:async()=>{throw new Error('岗位目录读取失败')}}})
  await failed.vm.load();assert.equal(failed.vm.pageState,'error');assert.equal(failed.vm.loadError,'岗位目录读取失败')
  for(const change of ['hide','account']){
    const wait=deferred(),p=page('student-internship/application/index.vue',{studentApi:{getInternship:()=>wait.promise,getInternshipApplicationPositions:async()=>{throw new Error('不得读取旧岗位')}},studentInternshipApplications:async()=>{throw new Error('不得读取旧原单')}})
    p.vm.history=[];p.vm.positions=[];const pending=p.vm.load()
    if(change==='hide')p.component.onHide.call(p.vm);else p.switchAccount()
    wait.resolve(dashboard);await pending;assert.deepEqual(p.vm.history,[]);assert.deepEqual(p.vm.positions,[]);assert.notEqual(p.vm.pageState,'ready')
  }
})

test('申请岗位后续页失败保留选择和页码，成功追加不把首屏当全集',async()=>{
  let fail=true;const p=application({studentApi:{getInternshipApplicationPositions:async(batch,record,page)=>{assert.deepEqual([batch,record,page],['18','21',2]);if(fail)throw new Error('后续读取失败');return {batchId:batch,internshipId:record,items:[{id:'32',remaining:2,canSelect:true}],total:2,hasMore:false}}}})
  p.vm.positionsMore=true;p.vm.positionsTotal=2;await p.vm.loadMorePositions()
  assert.equal(p.vm.positionsPage,1);assert.equal(p.vm.selectedPosition.id,'31');assert.match(p.vm.loadError,/后续读取失败/)
  fail=false;await p.vm.loadMorePositions();assert.equal(p.vm.positionsPage,2);assert.equal(p.vm.positions.length,2);assert.equal(p.vm.positionsMore,false);assert.equal(p.vm.selectedPosition.id,'31')
})
function plan(api={}) {
  const p=page('student-internship/plan/index.vue',api)
  p.vm.plan={id:'61',version:3,ackId:'71',ackVersion:2,ackStatus:'ACKNOWLEDGED'};p.vm.minimumWords=1
  p.vm.tasks=[1,2].map(sortOrder=>({sortOrder,progressId:String(80+sortOrder),progressVersion:3,progressStatus:'NOT_STARTED',
    _note:'合成任务说明'+sortOrder,_evidenceFileId:String(90+sortOrder),_evidenceFileName:'合成凭证'+sortOrder}))
  return p
}

test('申请保存冲突保留完整草稿和旧版本，按原编号回读且岗位重排按编号采用',async()=>{
  let writes=0;const latest={id:'41',recordId:'21',version:9,status:'DRAFT',applicationNote:'服务端旧说明'}
  const {vm}=application({studentInternshipApplicationSave:async()=>{writes++;throw conflict},studentInternshipApplications:async(batch,record)=>{
    assert.deepEqual([batch,record],['18','21']);return [latest]
  },studentApi:{getInternship:async()=>dashboard,getInternshipApplicationPositions:async()=>({batchId:'18',internshipId:'21',hasMore:false,items:[{id:'other',remaining:2,canSelect:true},{id:'31',remaining:1,canSelect:true}]})}})
  const original=structuredClone(vm.form),positions=vm.positions
  await vm.saveDraft();await vm.saveDraft();assert.equal(writes,1);assert.deepEqual(vm.form,original);assert.equal(vm.editableApplication.version,3)
  await vm.rereadConflict();assert.equal(vm.conflict.latest.version,9);assert.deepEqual(vm.form,original);assert.equal(vm.positions,positions)
  vm.adoptLatestApplication();assert.equal(vm.editableApplication.version,9);assert.equal(vm.selectedPosition.id,'31')
  assert.deepEqual(vm.form,original);assert.equal(vm.evidenceFileName,'合成证明');assert.equal(vm.conflict,null)
})

test('申请保存成功后提交冲突回读保存返回的原单，采用前禁止重复写且成功后解锁',async()=>{
  const writes=[];let fail=true
  const {vm}=application({studentInternshipApplicationSave:async body=>{writes.push(body);return {id:'saved',version:4}},
    studentInternshipApplicationSubmit:async()=>{if(fail)throw conflict},studentInternshipApplications:async()=>[
      {id:'wrong',recordId:'21',version:99,status:'DRAFT'},{id:'saved',recordId:'21',version:9,status:'DRAFT'}],
    studentApi:{getInternship:async()=>dashboard,getInternshipApplicationPositions:async()=>({batchId:'18',internshipId:'21',hasMore:false,items:[{id:'31',remaining:1,canSelect:true}]})}})
  vm.validate=()=>'';await vm.submit();assert.equal(vm.conflict.base.id,'saved');assert.equal(vm.editableApplication.id,'41')
  await vm.submit();assert.equal(writes.length,1);await vm.rereadConflict();vm.adoptLatestApplication()
  fail=false;vm.load=async()=>{vm.context={...context};vm.form={...vm.form}}
  await vm.submit();assert.equal(writes[1].id,'saved');assert.equal(writes[1].expectedVersion,9);assert.equal(vm.submitting,false)
})

test('申请终态、缺岗位和历史只读均不解开冲突，不丢原草稿',async()=>{
  for(const mode of ['terminal','missing-position','history']) {
    const {vm}=application({studentInternshipApplicationSave:async()=>{throw conflict},
      studentInternshipApplications:async()=>[{id:'41',recordId:'21',version:9,status:mode==='terminal'?'APPROVED':'DRAFT'}],
      studentApi:{getInternship:async()=>({...dashboard,historyMode:mode==='history'}),getInternshipApplicationPositions:async()=>({batchId:'18',internshipId:'21',hasMore:false,items:[]})}})
    const input=structuredClone(vm.form);await vm.saveDraft();await vm.rereadConflict();vm.adoptLatestApplication()
    assert.ok(vm.conflict);assert.equal(vm.editableApplication.version,3);assert.deepEqual(vm.form,input)
  }
})

test('计划与任务冲突保留所有草稿，回读不采用版本，明确采用后才人工提交新版',async()=>{
  const writes=[];let fail=true
  const freshPlan={id:'61',version:9,ackId:'71',ackVersion:5,ackStatus:'ACKNOWLEDGED',ackStatusLabel:'已确认'}
  const {vm}=plan({studentInternshipPlanTaskSubmit:async(order,body)=>{writes.push([order,body]);if(fail)throw conflict},
    studentInternshipPlan:async()=>freshPlan,studentInternshipPlanTasks:async()=>({planId:'61',planVersion:9,
      ackId:'71',ackVersion:5,ackStatus:'ACKNOWLEDGED',minimumWords:1,tasks:[1,2].map(sortOrder=>({sortOrder,progressId:String(80+sortOrder),progressVersion:9,progressStatus:'NOT_STARTED'}))})})
  const original=structuredClone(vm.tasks);await vm.submitTask(vm.tasks[0]);await vm.submitTask(vm.tasks[0]);assert.equal(writes.length,1)
  await vm.rereadConflict();assert.deepEqual(vm.tasks,original);assert.equal(vm.plan.version,3)
  vm.adoptLatestPlan();assert.equal(vm.tasks[0].progressVersion,9);assert.equal(vm.tasks[1]._note,original[1]._note)
  assert.equal(vm.tasks[0]._evidenceFileId,original[0]._evidenceFileId);assert.equal(vm.plan.ackStatusLabel,'已确认')
  fail=false;vm.load=async()=>{vm.plan={...vm.plan};vm.context={...context}}
  await vm.submitTask(vm.tasks[0]);assert.equal(writes[1][1].expectedVersion,9);assert.equal(vm.submitting,false)
})

test('计划确认冲突、回执混合快照和删除任务均保留草稿且不自动解锁',async()=>{
  for(const mode of ['ack','removed','mismatch','history']) {
    const {vm}=plan({studentInternshipPlanAcknowledge:async()=>{throw conflict},
      studentInternshipPlan:async()=>({id:'61',version:9,ackId:'71',ackVersion:5,ackStatus:'ACKNOWLEDGED'}),
      studentInternshipPlanTasks:async()=>({planId:'61',planVersion:9,ackId:'71',ackVersion:mode==='mismatch'?6:5,ackStatus:'ACKNOWLEDGED',
        tasks:mode==='removed'?[]:[1,2].map(sortOrder=>({sortOrder,progressId:String(80+sortOrder),progressVersion:9,progressStatus:'NOT_STARTED'}))}),
      studentApi:{getInternship:async()=>({...dashboard,historyMode:mode==='history'})}})
    const original=structuredClone(vm.tasks);await vm.ack();await vm.rereadConflict()
    assert.deepEqual(vm.tasks,original);assert.equal(vm.plan.version,3)
    if(mode!=='ack'){vm.adoptLatestPlan();assert.ok(vm.conflict);assert.deepEqual(vm.tasks,original)}
  }
})

test('隐藏再进入后旧写入和冲突回读不能污染新操作或解除新锁',async()=>{
  for(const kind of ['application','plan']) {
    const old=deferred(),next=deferred();let calls=0
    const p=kind==='application'?application({studentInternshipApplicationSave:()=> (++calls===1?old:next).promise}):
      plan({studentInternshipPlanTaskSubmit:()=> (++calls===1?old:next).promise})
    const write=()=>kind==='application'?p.vm.saveDraft():p.vm.submitTask(p.vm.tasks[0])
    const first=write();p.component.onHide.call(p.vm);p.component.onShow.call(p.vm);const second=write()
    old.reject(conflict);await first;assert.equal(p.vm.conflict,null);assert.notEqual(p.vm.submitting,false)
    next.reject(conflict);await second;assert.ok(p.vm.conflict);assert.equal(p.vm.submitting,false)
  }
})

test('教师任务审核冲突保存意见和旧版本，重新核对才能采用新版',async()=>{
  const writes=[];const {vm,modal}=page('teacher-internship/plan-task-review/index.vue',{
    teacherInternshipPlanTaskReview:async(id,batch,body)=>{writes.push(body);throw conflict}})
  vm.load=async()=>{vm.loadSeq++};const task={id:'2',version:3}
  vm.review(task,'REJECT');await modal().success({confirm:true,content:'请补充合成任务凭证'})
  assert.equal(vm.drafts['18:2'].version,3);assert.equal(vm.drafts['18:2'].comment,'请补充合成任务凭证')
  vm.review(task,'REJECT');assert.equal(writes.length,1)
  vm.review({...task,version:9},'REJECT');modal().success({confirm:true})
  assert.equal(modal().content,'请补充合成任务凭证');await modal().success({confirm:true,content:modal().content})
  assert.equal(writes[1].expectedVersion,9)
})

test('教师任务隐藏后的旧确认框不写入，旧命令回执也不解除新命令锁',async()=>{
  const old=deferred(),next=deferred();let writes=0
  const {vm,modal,component}=page('teacher-internship/plan-task-review/index.vue',{
    teacherInternshipPlanTaskReview:()=> (++writes===1?old:next).promise})
  vm.load=async()=>{vm.loadSeq++;vm.state='ready'};const row={id:'2',version:3}
  vm.review(row,'REJECT');const staleModal=modal();component.onHide.call(vm)
  await staleModal.success({confirm:true,content:'隐藏后的旧确认'});assert.equal(writes,0)
  component.onShow.call(vm);vm.review(row,'REJECT');const first=modal().success({confirm:true,content:'第一条合成意见'})
  component.onHide.call(vm);component.onShow.call(vm);vm.review(row,'REJECT');const second=modal().success({confirm:true,content:'第二条合成意见'})
  old.reject(conflict);await first;assert.equal(vm.actingId,'2');assert.equal(vm.drafts['18:2'].comment,'第二条合成意见')
  next.reject(conflict);await second;assert.equal(vm.actingId,'');assert.equal(vm.drafts['18:2'].conflicted,true)
})

test('教师鉴定指导意见和学校审核意见冲突保留旧依据，采用前不能重写',async()=>{
  for(const kind of ['advisor','review']) {
    const writes=[],latest={id:'2',batchId:'18',version:9,submitStatus:'SUBMITTED',reviewStatus:'PENDING',selfSummary:'最新自评',advisorOpinion:'最新指导'}
    const {vm,modal}=page('teacher-internship/student-eval/index.vue',{
      teacherInternshipStudentEvalDetail:async()=>latest,
      teacherInternshipStudentEvalAdvisorComment:async(id,batch,body)=>{writes.push(body);throw conflict},
      teacherInternshipStudentEvalReview:async(id,batch,body)=>{writes.push(body);throw conflict}})
    const item={...latest,version:3};vm.list=[item];vm.details['2']=item
    vm.drafts={'2':{version:3,advisorOpinion:'原指导意见保留',mentorOpinion:'原企业反馈'},other:{advisorOpinion:'另一份未提交'}}
    if(kind==='advisor')await vm.saveOpinion(item)
    else {vm.review(item,'RETURN');await modal().success({confirm:true,content:'学校退回的原意见'})}
    assert.equal(vm.details['2'].version,3);assert.equal(vm.conflicts['2'].latest.version,9)
    assert.equal(vm.drafts.other.advisorOpinion,'另一份未提交')
    if(kind==='advisor')await vm.saveOpinion(item);else vm.review(item,'RETURN')
    assert.equal(writes.length,1);vm.adoptEvaluation(item);assert.equal(vm.drafts['2'].version,9)
    if(kind==='review')assert.equal(vm.reviewDrafts['2'].comment,'学校退回的原意见')
    assert.equal(vm.acting,false)
  }
})

test('教师鉴定正常审核自身刷新后解锁，迟到读取不能跨账号回填',async()=>{
  const old=deferred(),{vm,modal,component,switchAccount}=page('teacher-internship/student-eval/index.vue',{
    teacherInternshipStudentEvalReview:async()=>({}),teacherInternshipStudentEvalDetail:()=>old.promise})
  const item={id:'2',batchId:'18',version:3};vm.details['2']=item;vm.list=[item]
  vm.load=async()=>{vm.loadSeq++};vm.review(item,'APPROVE');await modal().success({confirm:true,content:'已核对'})
  assert.equal(vm.acting,false)
  delete vm.details['2'];const read=vm.toggle(item);switchAccount();component.onHide.call(vm)
  old.resolve({...item,version:9});await read;assert.equal(vm.details['2'],undefined)
})

test('保险双方真实冲突均保留原输入及凭证，学生回读不换版本、教师重开回填意见',async()=>{
  let studentWrites=0,teacherWrites=0
  const student=page('student-internship/insurance/index.vue',{studentApi:{
    getInternship:async()=>dashboard,getInternshipInsurance:async()=>({id:'2',version:9,status:'PENDING_VERIFY',policyNo:'服务端保单'}),
    submitInternshipInsurance:async()=>{studentWrites++;throw conflict}}})
  student.vm.info={id:'2',version:3,status:'REJECTED'}
  Object.assign(student.vm.form,{insurerName:'合成保险公司',policyNo:'原输入',effectiveDate:'2026-10-01',expiryDate:'2027-10-01',fileId:'file'})
  student.vm.attachment={fileId:'file',readyForBusiness:true};const form=structuredClone(student.vm.form),attachment=student.vm.attachment
  await student.vm.submit();await student.vm.submit();assert.equal(studentWrites,1);assert.equal(student.vm.info.version,3)
  await student.vm.load();assert.equal(student.vm.latestInfo.version,9);assert.deepEqual(student.vm.form,form);assert.equal(student.vm.attachment,attachment)
  student.vm.adoptLatestInsurance();assert.equal(student.vm.info.version,9);assert.deepEqual(student.vm.form,form)
  const teacher=page('teacher-internship/insurance-verify/index.vue',{teacherInternshipInsuranceVerify:async()=>{teacherWrites++;throw conflict}})
  const row={id:'2',version:3,fileId:'file'};teacher.vm.verify(row,'REJECT');teacher.vm.review.comment='请补充合成保单证明'
  await teacher.vm.submitReview();await teacher.vm.submitReview();assert.equal(teacherWrites,1);assert.equal(teacher.vm.review.version,3)
  teacher.vm.closeReview();teacher.vm.verify({...row,version:9},'REJECT');assert.equal(teacher.vm.review.comment,'请补充合成保单证明')
  teacher.vm.closeReview();teacher.vm.evidence['2']={fileId:'file',version:9}
  teacher.vm.verify({...row,version:9},'APPROVE');assert.equal(teacher.vm.review.comment,'')
  teacher.vm.review.comment='核对后的合成通过意见';teacher.vm.closeReview()
  teacher.vm.verify({...row,version:9},'REJECT');assert.equal(teacher.vm.review.comment,'请补充合成保单证明')
  teacher.vm.closeReview();teacher.vm.verify({...row,version:9},'APPROVE');assert.equal(teacher.vm.review.comment,'核对后的合成通过意见')
})

test('首次保单提交离页后的未知回执只回读当前实习，明确采用保留输入且不自动重放',async()=>{
  for(const mode of ['created','not-created','wrong-record']) {
    const pending=deferred();let writes=0
    const latest=mode==='not-created'?{status:'NOT_SUBMITTED',version:0}:
      {id:'2',internshipId:mode==='wrong-record'?'other':'21',version:9,status:'PENDING_VERIFY'}
    const {vm,component}=page('student-internship/insurance/index.vue',{studentApi:{
      getInternship:async()=>dashboard,getInternshipInsurance:async(batch,record)=>{
        assert.deepEqual([batch,record],['18','21']);return latest
      },submitInternshipInsurance:()=>{writes++;return pending.promise}}})
    vm.info={status:'NOT_SUBMITTED',version:0}
    Object.assign(vm.form,{insurerName:'合成保险公司',policyNo:'首次原输入',effectiveDate:'2026-10-01',expiryDate:'2027-10-01',fileId:'file'})
    vm.attachment={fileId:'file',readyForBusiness:true};const original=structuredClone(vm.form),attachment=vm.attachment
    const write=vm.submit();component.onHide.call(vm);component.onShow.call(vm)
    pending.reject(conflict);await write;await vm.submit();assert.equal(writes,1);assert.equal(vm.conflict,true)
    await vm.load();assert.equal(vm.info.version,0);assert.deepEqual(vm.form,original);assert.equal(vm.attachment,attachment)
    vm.adoptLatestInsurance();assert.equal(writes,1);assert.deepEqual(vm.form,original)
    if(mode==='wrong-record'){assert.equal(vm.latestInfo,null);assert.equal(vm.conflict,true);assert.equal(vm.info.id,undefined)}
    else {assert.equal(vm.conflict,false);assert.equal(vm.info,latest)}
  }
})

test('学生自评冲突保存旧版本和全文，教师风险冲突保留原说明后才回读',async()=>{
  let writes=0,reads=0
  const student=page('student-internship/self-eval/index.vue',{studentApi:{submitInternshipSelfEval:async()=>{writes++;throw conflict}}})
  student.vm.loaded=true;student.vm.dashboard=dashboard;student.vm.evalData={id:'2',version:3,reviewStatus:'RETURNED'}
  student.vm.form.selfSummary='合成实习总结保留全文'.repeat(3);const form=structuredClone(student.vm.form)
  await student.vm.submit();await student.vm.submit();assert.equal(writes,1);assert.deepEqual(student.vm.form,form);assert.equal(student.vm.evalData.version,3)
  const teacher=page('teacher-internship/internship-risk/index.vue');teacher.vm.load=()=>{reads++;assert.equal(teacher.vm.drafts['2'].text,'原风险核实说明')}
  teacher.vm.handleWriteError(conflict,{id:'2'},'handle','原风险核实说明');assert.equal(reads,1)
})
