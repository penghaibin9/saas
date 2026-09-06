import test from 'node:test'
import assert from 'node:assert/strict'
import { optionsInstance, deferred, plain, tenant } from './platform-workspace-test-support.mjs'
const path='../src/modules/platform/components/TenantLifecycleWorkspace.vue'
const preview=(id='1000000000000000003',version=4)=>({code:0,data:{tenantId:id,action:'disable',fromStatus:'trial',toStatus:'disabled',expectedVersion:version,warnings:['登录将被拒绝']}})
const receipt=(extra={})=>({code:0,data:{tenantId:'1000000000000000003',version:5,runtimeMaterialized:true,cacheInvalidated:true,cacheRecoveryRequired:false,...extra}})
function make(api={}, deps={}) {
  const out=optionsInstance(path,{tenant:tenant(),tenant360:{version:4}}, {platformControlApi:api,...deps})
  out.state.choose('disable');out.state.reason='办理原因已经核对'
  return out
}
async function prepared(api={},deps={}) {
  const out=make({previewTenantTransition:async()=>preview(),...api},deps)
  await out.state.prepare();out.state.confirmation='SCHOOL-A';return out
}
test('lifecycle uses explicit version and reason; no fallback zero',async()=>{
  let calls=0;const {state}=make({previewTenantTransition:async()=>{calls++;return preview()}})
  state.tenant360={};state.tenant.version=null;await state.prepare();assert.equal(calls,0);assert.ok(state.error.includes('版本'))
  state.tenant.version=4;state.reason='短';await state.prepare();assert.equal(calls,0)
})
test('preview uses actual BIGINT id, selected action, and exact body',async()=>{
  let args;const {state}=make({previewTenantTransition:async(...values)=>{args=values;return preview()}})
  await state.prepare();assert.deepEqual(plain(args),['1000000000000000003','disable',{reason:'办理原因已经核对',expectedVersion:4}]);assert.equal(state.phase,'preview')
})
for (const mutation of [{tenantId:'7'},{action:'enable'},{expectedVersion:5},{fromStatus:null},{warnings:'not-an-array'}]) test('mismatched preview cannot unlock execution: '+JSON.stringify(mutation),async()=>{
  let calls=0;const {state}=make({previewTenantTransition:async()=>({code:0,data:{...preview().data,...mutation}}),applyTenantTransition:async()=>{calls++}})
  await state.prepare();state.confirmation='SCHOOL-A';await state.execute();assert.equal(calls,0);assert.equal(state.preview,null);assert.ok(state.error)
})
test('school code confirmation is mandatory',async()=>{
  let calls=0;const {state}=await prepared({applyTenantTransition:async()=>{calls++;return receipt()}})
  state.confirmation='OTHER-SCHOOL';await state.execute();assert.equal(calls,0)
})
test('edits after preview require a new preview',async()=>{
  let calls=0;const {state}=await prepared({applyTenantTransition:async()=>{calls++;return receipt()}})
  state.reason='修改了办理原因';await state.execute();assert.equal(calls,0);assert.equal(state.phase,'edit');assert.equal(state.preview,null)
})
test('updated version after preview never submits the old confirmation',async()=>{
  let calls=0;const {state}=await prepared({applyTenantTransition:async()=>{calls++;return receipt()}})
  state.tenant360.version=5;await state.execute();assert.equal(calls,0);assert.equal(state.phase,'edit')
})
test('double click issues exactly one business command',async()=>{
  const pending=deferred();let writes=0
  const {state}=await prepared({applyTenantTransition:()=>{writes++;return pending.promise}})
  const a=state.execute(),b=state.execute();assert.equal(writes,1);pending.resolve(receipt());await Promise.all([a,b]);assert.equal(state.phase,'receipt');await state.execute();assert.equal(writes,1)
})
test('timeout never triggers a business retry',async()=>{
  let writes=0;const {state}=await prepared({applyTenantTransition:async()=>{writes++;throw new Error('timeout')}})
  await state.execute();assert.equal(state.phase,'uncertain');await state.execute();await state.prepare();assert.equal(writes,1);assert.equal(state.attempted,true)
})
test('missing durable receipt is unknown, never green',async()=>{
  for(const data of [null,{}, {version:5}, {...receipt().data,tenantId:'7'}, {...receipt().data,cacheRecoveryRequired:true}]) {
    const {state}=await prepared({applyTenantTransition:async()=>({code:0,data})});await state.execute();assert.equal(state.phase,'uncertain');assert.equal(state.receipt,null)
  }
})
test('cache recovery uses only the existing recovery command',async()=>{
  let writes=0,recoveries=0
  const {state}=await prepared({applyTenantTransition:async()=>{writes++;return receipt({cacheInvalidated:false,cacheRecoveryRequired:true,warning:'缓存待恢复'})}}, {platformControlHardeningApi:{recoverTenantAuthCache:async(id)=>{recoveries++;assert.equal(id,tenant().tenantId);return receipt()}}})
  await state.execute();assert.equal(state.receipt.cacheRecoveryRequired,true);await state.recover();assert.equal(writes,1);assert.equal(recoveries,1);assert.equal(state.receipt.cacheRecoveryRequired,false)
})
test('failed cache recovery keeps degraded receipt',async()=>{
  const {state}=await prepared({applyTenantTransition:async()=>receipt({cacheInvalidated:false,cacheRecoveryRequired:true})},{platformControlHardeningApi:{recoverTenantAuthCache:async()=>({code:500,message:'cache unavailable'})}})
  await state.execute();await state.recover();assert.equal(state.receipt.cacheRecoveryRequired,true);assert.equal(state.error,'cache unavailable')
})
test('write permission is rechecked at execution, not just button render',async()=>{
  let allowed=true,writes=0
  const {state}=await prepared({applyTenantTransition:async()=>{writes++;return receipt()}},{canEnterRoute:()=>allowed})
  allowed=false;await state.execute();assert.equal(writes,0)
})
test('read-only duty cannot choose business mutation',()=>{
  const {state}=make({}, {canEnterRoute:()=>false,isPlatformRoot:()=>false})
  assert.equal(state.choices.length,0);assert.equal(state.action,'')
})
test('late preview from school A cannot render under school B',async()=>{
  const pending=deferred();const {state,definition}=make({previewTenantTransition:()=>pending.promise})
  const request=state.prepare();state.tenant=tenant('1007');definition.watch['tenant.tenantId'].call(state);pending.resolve(preview());await request
  assert.equal(state.preview,null);assert.equal(state.action,'')
})
test('late write receipt from school A cannot render under school B',async()=>{
  const pending=deferred();const {state,definition}=await prepared({applyTenantTransition:()=>pending.promise})
  const request=state.execute();state.tenant=tenant('1007');definition.watch['tenant.tenantId'].call(state);pending.resolve(receipt());await request;assert.equal(state.receipt,null)
})
test('unmount invalidates a pending mutation receipt',async()=>{
  const pending=deferred();const {state,definition}=await prepared({applyTenantTransition:()=>pending.promise})
  const request=state.execute();definition.beforeUnmount.call(state);pending.resolve(receipt());await request;assert.equal(state.receipt,null)
})
test('environment maintenance stays restricted to exact existing environment codes',()=>{
  const {state}=make();assert.ok(!state.choices.some(v=>v.key.startsWith('reset-')))
  state.tenant.tenantCode='sandbox-school';assert.ok(state.choices.some(v=>v.key==='reset-sandbox-data'))
  const nonroot=make({}, {isPlatformRoot:()=>false});nonroot.state.tenant.tenantCode='sandbox-school';assert.ok(!nonroot.state.choices.some(v=>v.key.startsWith('reset-')))
})
test('sandbox maintenance retains the original command, without fabricating server preview or OCC',async()=>{
  let writes=0;const row={...tenant(),tenantCode:'sandbox-school'}
  const {state}=optionsInstance(path,{tenant:row,tenant360:{version:4}}, {platformControlApi:{getTenant:async()=>({code:0,data:row}),resetSandboxData:async(id)=>{writes++;assert.equal(id,row.tenantId);return {code:0,data:{restored:true}}}}})
  state.choose('reset-sandbox-data');state.reason='现场环境维护确认';await state.prepare();assert.equal(state.phase,'preview');state.confirmation='sandbox-school';await state.execute();assert.equal(writes,1);assert.equal(state.phase,'receipt')
})
test('maintenance aborts when fresh identity/version differs',async()=>{
  let writes=0;const row={...tenant(),tenantCode:'sandbox-school'}
  const {state}=optionsInstance(path,{tenant:row,tenant360:{version:4}}, {platformControlApi:{getTenant:async()=>({code:0,data:{...row,version:9}}),resetSandboxData:async()=>{writes++}}})
  state.choose('reset-sandbox-data');state.reason='现场环境维护确认';await state.prepare();state.confirmation='sandbox-school';await state.execute();assert.equal(writes,0);assert.ok(state.error)
})
test('lifecycle form uses no native prompt or confirmation dialog',()=>{
  const {source}=make();assert.doesNotMatch(source,/window\.(prompt|confirm)/);assert.match(source,/仅恢复权限缓存/);assert.match(source,/接口不提供后端影响预览或版本锁/)
})
