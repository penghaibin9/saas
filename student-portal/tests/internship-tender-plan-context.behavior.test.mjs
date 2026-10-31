import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const view=fs.readFileSync(new URL('../src/views/internship/InternshipView.vue',import.meta.url),'utf8')
const code=view.slice(view.indexOf('async function fetchTabSource('),view.indexOf('\nasync function loadTab('))

function insuranceEntry(draft={}){
  const base={policyNo:'合成保单',insurerName:'虚构机构',coverageType:'实习险',effectiveDate:'2026-10-01',expiryDate:'2026-12-31',fileId:'42'},form={...base,...draft},calls=[]
  const start=view.indexOf('function insuranceHasDraft('),entry=view.indexOf('function selectTab(')
  const source=(start>=0?view.slice(start,entry):'')+view.slice(entry,view.indexOf('\nwatch(() => route.query.view',entry))+'\nreturn selectTab'
  const select=new Function('insuranceMeta','insForm','pendingInsuranceFile','insuranceConflict','tabs','router','route','my','tab','loadTab',source)(
    {value:{...base,status:'PENDING_VERIFY'}},form,{value:null},{value:false},[{key:'insurance'}],{replace(){}},{query:{}},{value:{hasData:true}},{value:'agreement'},(...args)=>calls.push(args))
  return {select,form,calls}
}
test('学生返回无改动的保险页重新读取学校核验结果',()=>{
  const p=insuranceEntry();p.select('insurance');assert.deepEqual(p.calls,[['insurance',true]])
})
test('学生返回有未提交保单修改的保险页保留草稿和已选凭证',()=>{
  const p=insuranceEntry({insurerName:'未提交机构修改',fileId:'43'});p.select('insurance')
  assert.deepEqual(p.calls,[['insurance',false]]);assert.equal(p.form.insurerName,'未提交机构修改');assert.equal(p.form.fileId,'43')
})
test('从办理页返回我的实习重新读取当前进度，重复选择当前页不刷新',()=>{
  let callback, reads=0
  const watcher=view.slice(view.indexOf('watch(tab,'),view.indexOf('watch(() => route.query.batchId'))
  new Function('watch','tab','refreshProgress',watcher)((_tab,cb)=>callback=cb,{},()=>{reads++})
  callback('overview','plan');assert.equal(reads,1)
  callback('overview','overview');assert.equal(reads,1)
})

function progressPage(read){
  let generation=1;const context={batchId:'18',internshipId:'19'},my={value:{hasData:true,batchId:'18',recordId:'19',status:'READY',weeklyReports:[{id:'week'}],processReports:[{id:'summary'}]}}
  const deps={my,changeEpoch:1,currentInternshipContext:()=>({...context}),currentSessionGeneration:()=>generation,
    changeCurrent:(_epoch,gen,ctx)=>gen===generation && ctx.batchId===context.batchId && ctx.internshipId===context.internshipId,
    tab:{value:'overview'},overviewLoading:{value:false},overviewError:{value:''},portalApi:{internshipMy:read}}
  const code=view.slice(view.indexOf('async function refreshProgress('),view.indexOf('async function load()'))
  const refresh=new Function(...Object.keys(deps),'let overviewSequence=0;'+code+';return refreshProgress')(...Object.values(deps))
  return{refresh,...deps,change:()=>{generation++;context.batchId='20';context.internshipId='21';my.value={hasData:true,batchId:'20',recordId:'21',status:'PREPARING'}}}
}
test('回到首页只更新本单进度，保留已加载的报告与其他工作区数据',async()=>{
  const p=progressPage(async id=>({hasData:true,batchId:id,recordId:'19',status:'ONBOARD',weeklyReports:[],processReports:[]}))
  await p.refresh();assert.equal(p.my.value.status,'ONBOARD');assert.deepEqual(p.my.value.weeklyReports,[{id:'week'}]);assert.deepEqual(p.my.value.processReports,[{id:'summary'}])
})
test('首页进度旧账号回包不回填，范围错误或失败明确显示上次读取结果',async()=>{
  let resolve;const p=progressPage(()=>new Promise(r=>resolve=r));const old=p.refresh();p.change();resolve({hasData:true,batchId:'18',recordId:'19',status:'ONBOARD'});await old
  assert.equal(p.my.value.status,'PREPARING')
  const q=progressPage(async()=>({hasData:true,batchId:'other',recordId:'other',status:'ARCHIVED'}));await q.refresh();assert.equal(q.my.value.status,'READY');assert.match(q.overviewError.value,/上次读取/)
})
function page(overrides={}){
  let context={batchId:'9007199254741001',internshipId:'9007199254741002'}
  const calls=[],ctx=()=>({...context}),ref=value=>({value})
  const deps={changeAlive:true,changeEpoch:1,currentSessionGeneration:()=>1,currentInternshipContext:ctx,rowsFrom:data=>Array.isArray(data)?data:data?.items||[],planSourceSequence:0,planAssignments:ref([]),selectedPlanId:ref(''),planMeta:ref(null),planTasks:ref([]),planTaskSummary:ref({}),planTaskMinimumWords:ref(10),internshipCoreApi:{plans:async c=>{calls.push(['plans',c]);return{context:ctx(),items:[{planId:'61',isPrimary:true}]}},plan:async(id,c)=>{calls.push(['plan',id,c]);return{id,context:ctx(),version:2}},planTasks:async(id,c)=>{calls.push(['tasks',id,c]);return{planId:id,context:ctx(),planVersion:2,tasks:[]}},...overrides}}
  const load=new Function(...Object.keys(deps),code+';return fetchTabSource')(...Object.values(deps))
  return{load,deps,calls,change:()=>context={batchId:'19',internshipId:'20'}}
}
test('电脑计划三个读取沿当前本人实习记录传参，大编号不损精度',async()=>{
  const p=page();assert.equal(await p.load('plan'),true)
  const context={batchId:'9007199254741001',internshipId:'9007199254741002'}
  assert.deepEqual(p.calls,[['plans',context],['plan','61',context],['tasks','61',context]])
})
test('电脑计划切批次后迟到列表不得覆盖新选择或继续读取旧正文',async()=>{
  let resolve;const p=page({plans:()=>new Promise(r=>resolve=r)});const pending=p.load('plan');p.change();resolve({context:{batchId:'18',internshipId:'18'},items:[{planId:'old'}]});await pending;assert.equal(p.deps.selectedPlanId.value,'');assert.equal(p.deps.planMeta.value,null);assert.deepEqual(p.calls,[])
})
test('电脑计划客户端实际请求保留本人上下文和计划编号',async()=>{
  const source=fs.readFileSync(new URL('../src/services/internshipCoreApi.js',import.meta.url),'utf8').replace(/^import[^\n]+/gm,'').replace('export const internshipCoreApi','const internshipCoreApi').replace(/export default[^\n]+/g,'')
  const urls=[],api=new Function('request','uploadFile',source+';return internshipCoreApi')(url=>urls.push(url),()=>{})
  const context={batchId:'9007199254741001',internshipId:'9007199254741002'}
  await api.plans(context);await api.plan('61',context);await api.planTasks('61',context);await api.agreements(context)
  for(const url of urls){const parsed=new URL(url,'http://test');assert.equal(parsed.searchParams.get('batchId'),context.batchId);assert.equal(parsed.searchParams.get('internshipId'),context.internshipId)}
  assert.equal(new URL(urls[1],'http://test').searchParams.get('planId'),'61')
})

function planActions(overrides={}){
  let generation=1,loads=0
  const task={sortOrder:1,progressVersion:2,_note:'保留本方案未提交的任务草稿',_evidenceFileId:''}
  const deps={busy:{value:false},selectedPlanId:{value:'61'},planMeta:{value:{id:'61',version:2,ackVersion:0}},
    planTasks:{value:[task]},planHasDraft:{value:false},planTaskMinimumWords:{value:10},tab:{value:'plan'},changeEpoch:1,
    currentInternshipContext:()=>({batchId:'18',internshipId:'19'}),currentSessionGeneration:()=>generation,
    changeCurrent:(_epoch,gen)=>gen===generation,loadTab:async()=>{loads++},ui:{notify:()=>{}},internshipCoreApi:overrides,
    fetchFileBlob:overrides.fetchFileBlob}
  const code=view.slice(view.indexOf('async function changePlan()'),view.indexOf('async function submitHelp()'))
  const actions=new Function(...Object.keys(deps),code+';return {changePlan,uploadPlanTaskEvidence,submitPlanTask,ackPlan,openPlanAttachment}')(...Object.values(deps))
  return{actions,deps,task,change:()=>{generation++},loads:()=>loads}
}
test('未提交任务填写保留在原方案，不能通过切方案丢弃',async()=>{
  const p=planActions();p.deps.selectedPlanId.value='62';p.deps.planHasDraft.value=true
  await p.actions.changePlan();assert.equal(p.deps.selectedPlanId.value,'61');assert.equal(p.loads(),0)
  assert.equal(p.task._note,'保留本方案未提交的任务草稿')
})
test('任务附件选择后的迟到上传结果不能回填另一账号或计划',async()=>{
  let resolve;const p=planActions({uploadPlanTaskEvidence:()=>new Promise(r=>resolve=r)})
  const work=p.actions.uploadPlanTaskEvidence({target:{files:[{size:100}],value:'file'}},p.task)
  p.change();resolve({fileId:'999',fileName:'旧身份文件'});await work
  assert.equal(p.task._evidenceFileId,'');assert.equal(p.loads(),0)
})
test('任务提交沿捕获的原计划，切账号后不清输入或继续刷新旧结果',async()=>{
  let resolve,sent;const p=planActions({submitPlanTask:(_sort,body)=>{sent=body;return new Promise(r=>resolve=r)}})
  const work=p.actions.submitPlanTask(p.task);p.change();resolve({});await work
  assert.equal(sent.planId,'61');assert.equal(sent.expectedVersion,2);assert.equal(sent.internshipId,'19')
  assert.equal(p.loads(),0);assert.equal(p.task._note,'保留本方案未提交的任务草稿')
})
test('计划确认拒绝重复点击，离开原计划后不刷新旧确认',async()=>{
  let resolve,calls=0;const p=planActions({acknowledgePlan:()=>{calls++;return new Promise(r=>resolve=r)}})
  const work=p.actions.ackPlan();await p.actions.ackPlan();assert.equal(calls,1)
  p.deps.selectedPlanId.value='62';resolve({});await work;assert.equal(p.loads(),0)
})
test('计划附件下载沿当前计划，迟到文件不会在新身份页面触发保存',async()=>{
  let resolve,path;const p=planActions({fetchFileBlob:url=>{path=url;return new Promise(r=>resolve=r)}})
  const work=p.actions.openPlanAttachment({fileId:'777',fileName:'计划安排.xlsx'});p.change();resolve({});await work
  assert.equal(path,'/files/download/777')
})
