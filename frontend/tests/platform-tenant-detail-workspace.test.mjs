import test from 'node:test'
import assert from 'node:assert/strict'
import { optionsInstance, deferred, plain, tenant } from './platform-workspace-test-support.mjs'
const path='../src/modules/platform/views/control/PlatformControlTenantDetail.vue'
const route=(id='1000000000000000003')=>({path:'/admin/platform/tenants/'+id,params:{tenantId:id},query:{}})
const make=(api={},extra={},deps={})=>optionsInstance(path,{$route:route(),...extra},{platformControlApi:api,...deps})

test('detail verifies top-level and nested school identity before showing data',async()=>{
  for (const data of [null,tenant('7'),{...tenant(),tenant360:{tenantId:'7'}}]) {
    const {state}=make({getTenant:async()=>({code:0,data})});await state.load();assert.equal(state.tenant,null);assert.ok(state.error);assert.equal(state.loading,false)
  }
})
test('detail read exception clears stale school and one-time credentials',async()=>{
  const {state}=make({getTenant:async()=>{throw new Error('offline')}});state.tenant=tenant();state.oneTimeSecret='old credential';await state.load()
  assert.equal(state.tenant,null);assert.equal(state.oneTimeSecret,'');assert.equal(state.loading,false);assert.equal(state.error,'offline')
})
test('late tenant A response cannot replace tenant B',async()=>{
  const a=deferred(),b=deferred();let reads=0
  const {state}=make({getTenant:()=>++reads===1?a.promise:b.promise})
  const first=state.load();state.$route=route('7');state.resetTenantState();const second=state.load()
  b.resolve({code:0,data:tenant('7')});await second;a.resolve({code:0,data:tenant()});await first;assert.equal(state.tenant.tenantId,'7')
})
test('a failed tab is an error, not an empty accounts list',async()=>{
  const {state}=make({listUsers:async()=>({code:403,message:'无查看权限'})},{tab:'users',users:[{userId:'1'}]})
  await state.loadTab('users');assert.equal(state.users.length,0);assert.equal(state.tabError,'无查看权限');assert.equal(state.tabLoading,false)
})
test('null successful tab payload cannot masquerade as configured-empty',async()=>{
  for (const [key,method] of [['features','getFeatures'],['rules','getRules'],['workflows','getWorkflows'],['brand','getBrand'],['users','listUsers']]) {
    const {state}=make({[method]:async()=>({code:0,data:null})},{tab:key});await state.loadTab(key);assert.ok(state.tabError);assert.equal(state.tabLoading,false)
  }
})
test('brand consumes canonical school fields and canonical version',async()=>{
  const {state,source}=make({getBrand:async()=>({code:0,data:{tenantId:tenant().tenantId,authority:'TENANT_BRAND_CONFIG',brand:{schoolShortName:'学校简称',brandColor:'#123456'},version:7,overrideVersion:99}})},{tab:'brand'})
  await state.loadTab('brand');assert.equal(state.brandVersion,7);assert.equal(state.brand.schoolShortName,'学校简称');assert.equal(state.tabError,'')
  assert.doesNotMatch(source,/saveBrand|putBrand|v-model="brand\[/)
  assert.match(source,/品牌由学校系统管理维护/)
})
test('brand refuses old platform projection as current school truth',async()=>{
  const {state}=make({getBrand:async()=>({code:0,data:{brand:{platformName:'legacy'},overrideVersion:7}})},{tab:'brand'});await state.loadTab('brand');assert.ok(state.tabError);assert.deepEqual(plain(state.brand),{})
})
test('old tab reply cannot change the new tab or stop its loading state',async()=>{
  const a=deferred(),b=deferred();const {state}=make({listUsers:()=>a.promise,getBrand:()=>b.promise},{tab:'users'})
  const first=state.loadTab('users');state.tab='brand';const second=state.loadTab('brand');a.resolve({code:0,data:{list:[{userId:'1'}]}});await first;assert.equal(state.users.length,0);assert.equal(state.tabLoading,true)
  b.resolve({code:0,data:{authority:'TENANT_BRAND_CONFIG',brand:{},version:0}});await second;assert.equal(state.tabLoading,false)
})
test('late initial credential response never appears in another school',async()=>{
  const pending=deferred();const {state}=make({createUser:()=>pending.promise},{tab:'users',newUser:{loginName:'newadmin',realName:'新管理员'}})
  const request=state.createUser();state.$route=route('7');state.resetTenantState();pending.resolve({code:0,data:{loginName:'newadmin',initialPassword:'must-not-leak'}});await request
  assert.equal(state.oneTimeSecret,'');assert.equal(state.users.length,0)
})
test('double create click sends one command and duplicate user identity is not invented',async()=>{
  const pending=deferred();let writes=0
  const {state}=make({createUser:()=>{writes++;return pending.promise},listUsers:async()=>({code:0,data:{list:[]}})},{tab:'users',newUser:{loginName:'admin',realName:'管理员'}})
  const a=state.createUser(),b=state.createUser();assert.equal(writes,1);pending.resolve({code:0,data:{loginName:'admin',initialPassword:'test-only'}});await Promise.all([a,b]);assert.equal(state.saving,false)
})
test('rule save freezes school, sparse payload and OCC version before awaiting',async()=>{
  // The same behavior now belongs to the dedicated rule workspace, not the parent.
  const pending=deferred();let args
  const projection={tenantId:tenant().tenantId,rules:{limits:{n:1,unchanged:2}},override:{},overrideVersion:9}
  const {state,definition}=optionsInstance('../src/modules/platform/components/TenantRulesWorkspace.vue', {tenant:tenant(),projection},{platformControlHardeningApi:{putRules:(...values)=>{args=values;return pending.promise}}})
  state.initialize();state.draft.limits.n='5';state.reason='真实操作原因';state.review()
  const request=state.submit();state.draft.limits.n='10';assert.deepEqual(plain(args),[tenant().tenantId,{limits:{n:5}},9,'真实操作原因'])
  state.tenant=tenant('7');state.projection={...projection,tenantId:'7'};definition.watch['tenant.tenantId'].call(state)
  pending.resolve({code:0,data:{tenantId:tenant().tenantId,rules:{limits:{n:5,unchanged:2}},override:{limits:{n:5}},overrideVersion:10}});await request
  assert.equal(state.base.tenantId,'7');assert.equal(state.base.overrideVersion,9);assert.equal(state.prepared,null)
})
test('unknown user row cannot be used as a cross-object action',async()=>{
  let writes=0;const {state}=make({userAction:async()=>{writes++}},{tab:'users',users:[{userId:'1'}]})
  await state.userAct({userId:'7'},'disable');assert.equal(writes,0)
})
test('tab switch and unmount clear one-time secrets',()=>{
  const {state,definition}=make();state.oneTimeSecret='secret';state.switchTab('info');assert.equal(state.oneTimeSecret,'');state.oneTimeSecret='again';definition.beforeUnmount.call(state);assert.equal(state.oneTimeSecret,'')
})
test('return navigation is restricted and carries list filters',()=>{
  const {state,calls}=make();state.$route.query={returnTo:'/admin/platform/brands',listKeyword:'学校',listStatus:'trial',listPage:'2',listPageSize:'50'};state.backToList()
  assert.deepEqual(plain(calls.at(-1)),['push',{path:'/admin/platform/brands',query:{keyword:'学校',status:'trial',page:'2',pageSize:'50'}}])
})
