import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { buildRenewalHandoff, exitReviewScope, validateExitReview, blockerGroup, COMMERCIAL_DESTINATIONS } from '../src/modules/platform/lib/moduleCommerceWorkbench.mjs'
import * as money from '../src/modules/platform/lib/moduleCommerceSales.mjs'

const TID = '1000000000000000001'
const candidate = () => ({tenantId:TID,moduleKey:'internship',moduleGeneration:2,sourceId:'77',sourceEndsAt:'2026-09-01T00:00:00Z',canStartRenewalOrder:true,blocker:null})
const context = () => ({tenantId:TID,tenantStatus:'ACTIVE',tenantName:'测试学校',states:{internship:{generation:2,dataState:'AVAILABLE'}},paidThrough:{internship:'2026-10-01T00:00:00.000001Z'}})
const job = () => ({tenantId:TID,jobId:'9',moduleKey:'internship',moduleGeneration:2,version:0})
const review = () => ({tenantId:TID,jobId:'9',moduleKey:'internship',moduleGeneration:2,jobVersion:0,
  dryRunOnly:true,destructiveExecutionAvailable:false,physicalPurgeAuthorized:false,deletionAuthorized:false,
  canExecutePhysicalPurge:false,fullResourceClosureComplete:false,destructiveStatements:[],
  blockers:['M0_FULL_RESOURCE_CLOSURE_REQUIRED','MODULE_PURGE_EXECUTION_DISABLED','BACKUP_DISPOSITION_POLICY_REQUIRED'].map(code=>({code,message:code})),
  moduleTableInventory:{candidateTables:[]},preflightDigest:'a'.repeat(64)})
const deferred = () => {let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no});return {promise,resolve,reject}}
function script(name) {
  const text=fs.readFileSync(new URL(`../src/modules/platform/views/control/${name}.vue`,import.meta.url),'utf8')
  return text.match(/<script(?: setup)?>([\s\S]*?)<\/script>/)[1].replace(/^import .*\n/gm,'')
}
function harness(name, overrides = {}) {
  const watches=[],unmount=[]
  const calls=[]
  const api={
    getSalesContext:async(tid)=>{calls.push(['context',tid]);return context()},
    listSaleSkus:async(params)=>{calls.push(['catalog',params]);return {items:[],modules:[],total:0}},
    createSalesOrder:async()=>{calls.push(['create']);throw new Error('unexpected creation')},
    getExitReview:async(...args)=>{calls.push(['review',...args]);return review()},
    ...overrides.api
  }
  const props=overrides.props || {tenantId:TID,locked:false,job:job()}
  const env={
    ref:value=>({value}),computed:fn=>({get value(){return fn()}}),
    watch:(getter,callback)=>watches.push(callback), onMounted:()=>{}, onBeforeUnmount:callback=>unmount.push(callback),
    onBeforeRouteLeave:()=>{},defineProps:()=>props,defineEmits:()=>()=>{},defineExpose:()=>{},
    api,...money,buildRenewalHandoff,exitReviewScope,validateExitReview,blockerGroup,
    window:{confirm:()=>true,addEventListener:()=>{},removeEventListener:()=>{}},
    sessionStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},
    downloadXlsxFromApi:()=>{},ensurePlatformAccessContext:async()=>({subjectId:'42',duties:['order.manage']}),
    ...overrides.env
  }
  const names=name==='ModuleSalesWorkspace'
    ? 'prepareRenewal,addSku,submitOrder,rows,remark,quote,confirmed,orderType,tab,attempt,access,renewalHandoff,handoffLoading,error'
    : 'loadReview,report,loading,error,page'
  const values=new Function(...Object.keys(env),script(name)+`\nreturn {${names}}`)(...Object.values(env))
  if(values.access)values.access.value={subjectId:'42',duties:['order.manage']}
  return {...values,props,calls,watches,unmount,api}
}

test('handoff re-reads current paid end, keeps bigint school and no old pricing',()=>{
  const result=buildRenewalHandoff(candidate(),context(),TID)
  assert.equal(result.startLocal,'2026-10-01T08:00:01')
  assert.equal(result.orderType,'RENEW');assert.equal(result.tenantId,TID)
  assert.equal(result.priceMustBeReconfirmed,true);assert.equal(result.endAtMustBeExplicit,true)
  assert.equal('unitPrice' in result,false);assert.equal('endAt' in result,false)
})
test('handoff rejects foreign school, blockers, invalid module and changed generation',()=>{
  for(const mutate of [c=>c.tenantId='43',c=>c.moduleKey='employment',c=>c.canStartRenewalOrder=false,
    c=>c.blocker={code:'STOP_RENEW_SCHEDULED'},c=>c.moduleGeneration=1]){
    const c=candidate();mutate(c);assert.throws(()=>buildRenewalHandoff(c,context(),TID))
  }
  for(const state of ['FROZEN','RETAINED','PURGED','UNKNOWN']){
    const ctx=context();ctx.states.internship.dataState=state;assert.throws(()=>buildRenewalHandoff(candidate(),ctx,TID))
  }
})
test('missing paid time, naive time and disabled school never become a renewal draft',()=>{
  for(const value of [null,'','2026-10-01T00:00:00','not-a-timeZ']){
    const ctx=context();ctx.paidThrough.internship=value;assert.throws(()=>buildRenewalHandoff(candidate(),ctx,TID))
  }
  const ctx=context();ctx.tenantStatus='SUSPENDED';assert.throws(()=>buildRenewalHandoff(candidate(),ctx,TID))
})
test('sale component handoff selects actual RENEW tab and module without creating an order',async()=>{
  const h=harness('ModuleSalesWorkspace');h.rows.value=[{moduleKey:'graduationDesign'}];h.remark.value='old contract'
  assert.equal(await h.prepareRenewal(candidate()),true)
  assert.equal(h.orderType.value,'RENEW');assert.equal(h.tab.value,'order');assert.equal(h.rows.value.length,0)
  assert.equal(h.remark.value,'');assert.equal(h.quote.value,null);assert.equal(h.confirmed.value,false)
  assert.deepEqual(h.calls.map(c=>c[0]),['context','catalog'])
  assert.equal(h.calls[1][1].moduleKey,'internship')
})
test('choosing a new SKU after handoff uses current catalogue price and only suggests start',async()=>{
  const h=harness('ModuleSalesWorkspace');await h.prepareRenewal(candidate())
  h.addSku({moduleKey:'internship',skuCode:'NEW',revision:5,contentHash:'f'.repeat(64),pricePolicy:{unitPrice:'200.00',currency:'CNY'}})
  assert.equal(h.rows.value[0].unitPrice,'200.00');assert.equal(h.rows.value[0].skuRevision,5)
  assert.equal(h.rows.value[0].startLocal,'2026-10-01T08:00:01');assert.equal(h.rows.value[0].endLocal,'')
})
test('pending original order prevents handoff and any context fetch',async()=>{
  const h=harness('ModuleSalesWorkspace');h.attempt.value={key:'original'}
  assert.equal(await h.prepareRenewal(candidate()),false);assert.deepEqual(h.calls,[])
  assert.equal(h.attempt.value.key,'original')
})
test('declined confirmation retains existing draft without requests',async()=>{
  const h=harness('ModuleSalesWorkspace',{env:{window:{confirm:()=>false}}});h.rows.value=[{moduleKey:'graduationDesign'}]
  assert.equal(await h.prepareRenewal(candidate()),false);assert.equal(h.rows.value[0].moduleKey,'graduationDesign')
  assert.deepEqual(h.calls,[])
})
test('context outage leaves original draft untouched',async()=>{
  const h=harness('ModuleSalesWorkspace',{api:{getSalesContext:async()=>{throw new Error('context outage')}}})
  h.rows.value=[{moduleKey:'graduationDesign'}];h.remark.value='original'
  assert.equal(await h.prepareRenewal(candidate()),false);assert.equal(h.rows.value.length,1)
  assert.equal(h.remark.value,'original');assert.equal(h.handoffLoading.value,false);assert.match(h.error.value,/outage/)
})
test('school switch during handoff does not consume stale response or load old catalogue',async()=>{
  const d=deferred(),h=harness('ModuleSalesWorkspace',{api:{getSalesContext:()=>d.promise}})
  const pending=h.prepareRenewal(candidate());h.props.tenantId='43';d.resolve(context())
  assert.equal(await pending,false);assert.equal(h.renewalHandoff.value,null)
  assert.equal(h.calls.some(c=>c[0]==='catalog'),false)
})
test('editing the draft during a delayed handoff preserves the newer draft',async()=>{
  const d=deferred(),h=harness('ModuleSalesWorkspace',{api:{getSalesContext:()=>d.promise}})
  const pending=h.prepareRenewal(candidate());h.remark.value='newer edit';d.resolve(context())
  assert.equal(await pending,false);assert.equal(h.remark.value,'newer edit')
})
test('school change during identity recheck cannot submit a sales command',async()=>{
  const d=deferred(),h=harness('ModuleSalesWorkspace',{env:{ensurePlatformAccessContext:()=>d.promise}})
  h.quote.value={order:{tenantId:TID,items:[]}};h.confirmed.value=true
  const pending=h.submitOrder();h.props.tenantId='43';d.resolve({subjectId:'42',duties:['order.manage']});await pending
  assert.equal(h.calls.some(c=>c[0]==='create'),false)
})
test('exit scope rejects school mismatch and incomplete or unsafe context',()=>{
  const scope=exitReviewScope(TID,job());assert.equal(scope.expectedVersion,0)
  for(const mutate of [j=>j.tenantId='43',j=>j.jobId=9,j=>j.moduleGeneration=true,j=>j.version=-1,j=>j.moduleKey='unknown']){
    const j=job();mutate(j);assert.throws(()=>exitReviewScope(TID,j))
  }
})
test('exit report binds version, module and school and retains exact false flags',()=>{
  const scope=exitReviewScope(TID,job());assert.equal(validateExitReview(review(),scope).dryRunOnly,true)
  for(const field of ['tenantId','jobId','moduleKey','moduleGeneration','jobVersion']){
    const data=review();data[field]='changed';assert.throws(()=>validateExitReview(data,scope))
  }
  for(const field of ['destructiveExecutionAvailable','physicalPurgeAuthorized','deletionAuthorized','canExecutePhysicalPurge','fullResourceClosureComplete']){
    const data=review();data[field]=true;assert.throws(()=>validateExitReview(data,scope))
  }
})
test('missing blocker, malformed report or destructive statement cannot display a result',()=>{
  const scope=exitReviewScope(TID,job())
  for(const mutate of [d=>d.blockers=[],d=>d.blockers[0]={code:'bad'},d=>d.destructiveStatements=['DELETE'],d=>d.dryRunOnly='true']){
    const data=review();mutate(data);assert.throws(()=>validateExitReview(data,scope))
  }
})
test('real panel method sends read-only scope and displays returned evidence',async()=>{
  const h=harness('ModuleExitReviewPanel');await h.loadReview()
  assert.deepEqual(h.calls[0],['review',TID,'9',{expectedGeneration:2,expectedVersion:0}])
  assert.equal(h.report.value.jobVersion,0);assert.equal(h.loading.value,false)
})
test('panel clears prior evidence before loading and never displays another school response',async()=>{
  const d=deferred(),h=harness('ModuleExitReviewPanel',{api:{getExitReview:()=>d.promise}})
  h.report.value=review();const pending=h.loadReview();assert.equal(h.report.value,null)
  h.props.tenantId='43';h.watches.forEach(callback=>callback());d.resolve(review());await pending
  assert.equal(h.report.value,null);assert.equal(h.error.value,'')
})
test('late failed request cannot erase a newer successful exit report',async()=>{
  const first=deferred(),second=deferred();let n=0
  const h=harness('ModuleExitReviewPanel',{api:{getExitReview:()=>++n===1?first.promise:second.promise}})
  const a=h.loadReview(),b=h.loadReview();second.resolve(review());await b;first.reject(new Error('old failure'));await a
  assert.equal(h.report.value.jobId,'9');assert.equal(h.error.value,'')
})
test('unsafe exit payload produces error and no report',async()=>{
  const h=harness('ModuleExitReviewPanel',{api:{getExitReview:async()=>({...review(),deletionAuthorized:true})}})
  await h.loadReview();assert.equal(h.report.value,null);assert.match(h.error.value,/只读/)
})
test('unmounted exit panel ignores response',async()=>{
  const d=deferred(),h=harness('ModuleExitReviewPanel',{api:{getExitReview:()=>d.promise}})
  const pending=h.loadReview();h.unmount.forEach(callback=>callback());d.resolve(review());await pending
  assert.equal(h.report.value,null)
})
test('no task or invalid scope does not fetch an exit report',async()=>{
  const h=harness('ModuleExitReviewPanel');h.props.job=null;await h.loadReview();assert.deepEqual(h.calls,[])
  h.props.job={...job(),tenantId:'43'};await h.loadReview();assert.deepEqual(h.calls,[]);assert.ok(h.error.value)
})
test('seven destinations are explicit, unique and do not grant approval',()=>{
  assert.equal(COMMERCIAL_DESTINATIONS.length,7);assert.equal(new Set(COMMERCIAL_DESTINATIONS.map(d=>d.key)).size,7)
  assert.match(COMMERCIAL_DESTINATIONS.find(d=>d.key==='review').description,/只读/)
  assert.equal(blockerGroup('LEGAL_HOLD_ACTIVE'),'文件与共享引用')
  assert.equal(blockerGroup('NEW_UNKNOWN_BLOCKER'),'任务、模块与消费者')
})
test('parent uses real exposed sales method and mounts exit panel without inventing a route',()=>{
  const text=fs.readFileSync(new URL('../src/modules/platform/views/control/PlatformCommercialControlView.vue',import.meta.url),'utf8')
  assert.ok(text.includes('ref="salesWorkspace"'));assert.ok(text.includes('await this.$refs.salesWorkspace?.prepareRenewal?.(candidate)'))
  assert.ok(text.includes('<ModuleExitReviewPanel'));assert.ok(text.includes('aria-label="商业办理区导航"'))
  assert.ok(!text.includes("retentionPolicyVersion: 'SCHOOL-CONTRACT'"))
})

function parentComponent(api = {}) {
  const names=['ModulePageShell','ModuleSalesWorkspace','ModuleRenewalWorkspace','ModuleFinanceWorkspace','ModuleExitReviewPanel','COMMERCIAL_DESTINATIONS','platformControlApi','moduleCommerceApi']
  return new Function(...names,script('PlatformCommercialControlView').replace('export default','return'))({}, {}, {}, {}, {}, COMMERCIAL_DESTINATIONS, {}, api)
}
test('parent renewal bridge awaits actual draft preparation before changing selected module',async()=>{
  const component=parentComponent(),d=deferred(),events=[]
  const vm={$refs:{salesWorkspace:{prepareRenewal:()=>d.promise}},selectModule:async(key)=>events.push(['module',key]),notify:()=>{},jumpToWorkspace:key=>events.push(['jump',key])}
  const work=component.methods.focusSalesRenewal.call(vm,candidate());assert.deepEqual(events,[])
  d.resolve(true);await work;assert.deepEqual(events,[['module','internship'],['jump','sales']])
})
test('parent does not change module after rejected handoff',async()=>{
  const events=[],vm={$refs:{salesWorkspace:{prepareRenewal:async()=>false}},selectModule:async()=>events.push('module'),notify:()=>{},jumpToWorkspace:key=>events.push(key)}
  await parentComponent().methods.focusSalesRenewal.call(vm,candidate());assert.deepEqual(events,['sales'])
})


test('busy lifecycle operation prevents changing school or module',async()=>{
  const vm={busy:true,selectedTenantId:TID,selectedModuleKey:'internship',loadPortfolio:()=>assert.fail('unexpected reload'),afterModuleRefresh:()=>assert.fail('unexpected module change')}
  parentComponent().methods.changeSalesSchool.call(vm,'43')
  assert.equal(await parentComponent().methods.selectModule.call(vm,'graduationDesign'),false)
  assert.equal(vm.selectedTenantId,TID);assert.equal(vm.selectedModuleKey,'internship')
})
test('changing module clears stale acceptance, policy and confirmation',async()=>{
  const vm={busy:false,portfolio:{modules:[{moduleKey:'graduationDesign'}]},selectedModuleKey:'internship',preview:{},job:{},cancelReason:'old',deliveryForm:{acceptanceRef:'old'},exportForm:{acceptanceRef:'old'},offboardForm:{confirmed:true,retentionDays:30},afterModuleRefresh:async()=>{}}
  assert.equal(await parentComponent().methods.selectModule.call(vm,'graduationDesign'),true)
  assert.equal(vm.preview,null);assert.equal(vm.job,null);assert.equal(vm.deliveryForm.acceptanceRef,'')
  assert.equal(vm.offboardForm.retentionDays,null);assert.equal(vm.offboardForm.confirmed,false)
})
test('late offboarding preview cannot be shown under another module',async()=>{
  const d=deferred(),vm={busy:false,selectedTenantId:TID,selectedModuleKey:'internship',selectedModule:{moduleKey:'internship',generation:2},moduleSeq:1,preview:{},run:async fn=>fn(),notify:()=>{}}
  const component=parentComponent({previewOffboarding:()=>d.promise})
  const pending=component.methods.loadOffboardPreview.call(vm)
  vm.selectedModuleKey='graduationDesign';vm.moduleSeq++
  d.resolve({tenantId:TID,moduleKey:'internship',moduleGeneration:2,canRequest:true});await pending
  assert.equal(vm.preview,null)
})
test('mismatched preview response is rejected even without a local selection change',async()=>{
  const vm={busy:false,selectedTenantId:TID,selectedModuleKey:'internship',selectedModule:{moduleKey:'internship',generation:2},moduleSeq:1,preview:null,run:async fn=>fn(),notify:()=>{}}
  const component=parentComponent({previewOffboarding:async()=>({tenantId:'43',moduleKey:'internship',moduleGeneration:2,canRequest:true})})
  await component.methods.loadOffboardPreview.call(vm);assert.equal(vm.preview,null)
})
test('freeze command cannot consume a different module or generation preview',async()=>{
  for(const wrong of [{tenantId:'43',moduleKey:'internship',moduleGeneration:2},{tenantId:TID,moduleKey:'graduationDesign',moduleGeneration:2},{tenantId:TID,moduleKey:'internship',moduleGeneration:1}]){
    const vm={selectedTenantId:TID,selectedModule:{moduleKey:'internship',generation:2},preview:{...wrong,canRequest:true},notify:()=>{},run:()=>assert.fail('unsafe freeze dispatch')}
    await parentComponent().methods.requestOffboarding.call(vm);assert.equal(vm.preview,null)
  }
})

test('workspace navigation targets the real root ref and moves keyboard focus',()=>{
  const events=[],old=globalThis.window
  globalThis.window={matchMedia:()=>({matches:true})}
  try{
    const target={setAttribute:(...v)=>events.push(v),focus:()=>events.push('focus'),scrollIntoView:v=>events.push(v)}
    const vm={$refs:{commerceRoot:{querySelector:selector=>{assert.equal(selector,'[aria-label="商业财务工作区"]');return target}}},$nextTick:fn=>fn(),notify:()=>assert.fail('missing area')}
    parentComponent().methods.jumpToWorkspace.call(vm,'finance')
    assert.deepEqual(events,[['tabindex','-1'],'focus',{behavior:'auto',block:'start'}])
  }finally{globalThis.window=old}
})
