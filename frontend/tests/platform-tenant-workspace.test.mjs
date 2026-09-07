import test from 'node:test'
import assert from 'node:assert/strict'
import * as w from '../src/modules/platform/utils/tenantWorkspace.mjs'
import { optionsInstance, deferred, plain, tenant } from './platform-workspace-test-support.mjs'
const path = '../src/modules/platform/views/control/PlatformControlTenants.vue'

for (const value of [null, undefined, '', ' ', false, {}, [], '1.5', 1.5, -1, NaN, Infinity, 9007199254740992]) {
  test(`counts preserve unavailable values: ${String(value)}`, () => { assert.equal(w.countLabel(value), '未取得') })
}
test('zero is real, unknown environment is not production', () => {
  assert.equal(w.countLabel(0), '0'); assert.equal(w.usagePercent(0, 100), 0); assert.equal(w.usagePercent(100, 0), null)
  assert.equal(w.usagePercent(110, 100), 100); assert.equal(w.environmentLabel(null), '环境未取得')
  assert.equal(w.authorityLabel({ commercialAuthorityVerified: null }), '需在详情核验')
})
test('query parser accepts only supported filters and page sizes', () => {
  assert.deepEqual(w.parseListQuery({keyword: ['bad'],status:'unknown',page:'-2',pageSize:'999'}), {keyword:'',status:'',page:1,pageSize:20})
})
test('detail and return preserve BIGINT identity, source picker, query and page', () => {
  const route = { path: '/admin/platform/brands', query: {keyword:'职业', status:'trial', page:'3',pageSize:'50'} }
  const link = w.tenantLocation('1000000000000000003','brand',route)
  assert.equal(link.path, '/admin/platform/tenants/1000000000000000003')
  assert.deepEqual(w.returnLocation(link.query), route)
})
test('return route rejects external or unrelated destinations', () => {
  for (const value of ['//evil.example', 'https://evil.example', '/admin/system', '/admin/platform/tenants/3']) assert.equal(w.returnLocation({returnTo:value}).path, '/admin/platform/tenants')
  // Deliberately simulate a caller coercing a BIGINT; keep the source literal exact.
  assert.equal(w.tenantLocation(Number('1000000000000000003')), null)
  assert.equal(w.tenantLocation('../3'), null)
})
test('unread or incomplete list is never an empty success', () => {
  for (const value of [null, {}, {list:null}, {list:[tenant()], total:10}, {list:[tenant(),tenant()]}, {list:[{}]}]) assert.throws(() => w.validateTenantList(value))
  assert.deepEqual(w.validateTenantList({list:[],total:0}), [])
})
test('list failure clears old rows and exposes retry state', async () => {
  const {state} = optionsInstance(path, {}, {platformControlApi:{listTenants:async()=>({code:403,message:'无查看权限'})}})
  state.rows=[tenant()]; state.loadedAt='old'; await state.load()
  assert.deepEqual(plain(state.rows), []); assert.equal(state.error,'无查看权限'); assert.equal(state.loadedAt,''); assert.equal(state.loading,false)
})
test('network rejection exits loading and never claims no schools', async () => {
  const {state} = optionsInstance(path, {}, {platformControlApi:{listTenants:async()=>{throw new Error('network unavailable')}}})
  await state.load(); assert.equal(state.error,'network unavailable'); assert.equal(state.loading,false)
})
test('latest list request wins and late failure is ignored', async () => {
  const a=deferred(),b=deferred(); let n=0
  const {state} = optionsInstance(path, {}, {platformControlApi:{listTenants:()=> ++n===1?a.promise:b.promise}})
  const first=state.load(),second=state.load(); b.resolve({code:0,data:{list:[tenant('1007')],total:1}}); await second
  a.reject(new Error('old')); await first
  assert.equal(state.rows[0].tenantId,'1007'); assert.equal(state.error,'')
})
test('old result cannot clear latest request loading state', async () => {
  const a=deferred(),b=deferred(); let n=0
  const {state}=optionsInstance(path, {}, {platformControlApi:{listTenants:()=>++n===1?a.promise:b.promise}})
  const first=state.load(),second=state.load(); a.resolve({code:0,data:{list:[],total:0}}); await first; assert.equal(state.loading,true)
  b.resolve({code:0,data:{list:[],total:0}}); await second; assert.equal(state.loading,false)
})
test('unmount invalidates the pending list', async () => {
  const a=deferred(); const {state,definition}=optionsInstance(path,{}, {platformControlApi:{listTenants:()=>a.promise}})
  const request=state.load(); definition.beforeUnmount.call(state); a.resolve({code:0,data:{list:[tenant()],total:1}}); await request; assert.equal(state.rows.length,0)
})
test('local pagination renders at most one page, without extra read on page changes', async () => {
  let reads=0
  const rows=Array.from({length:45},(_,i)=>tenant(String(i+1)))
  const {state}=optionsInstance(path,{}, {platformControlApi:{listTenants:async()=>{reads++;return {code:0,data:{list:rows,total:45}}}}})
  await state.syncRoute(); assert.equal(state.visibleRows.length,20); assert.equal(state.pageCount,3)
  state.$route.query={page:'3'}; await state.syncRoute(); assert.equal(reads,1); assert.equal(state.visibleRows.length,5); assert.equal(state.rangeStart,41); assert.equal(state.rangeEnd,45)
})
test('deep linked trial filter is sent to the existing real endpoint', async () => {
  let filters
  const {state}=optionsInstance(path,{$route:{path:'/admin/platform/tenants',query:{status:'trial',keyword:'学校'},params:{}}},{platformControlApi:{listTenants:async f=>{filters=f;return {code:0,data:{list:[],total:0}}}}})
  await state.syncRoute(); assert.deepEqual(plain(filters),{status:'trial',keyword:'学校'})
})
test('out of range page is clamped and rewritten', async () => {
  const {state,calls}=optionsInstance(path,{$route:{path:'/admin/platform/tenants',query:{page:'999'},params:{}}},{platformControlApi:{listTenants:async()=>({code:0,data:{list:[tenant()],total:1}})}})
  await state.syncRoute(); assert.equal(state.page,1); assert.equal(calls.at(-1)[0],'replace'); assert.deepEqual(plain(calls.at(-1)[1].query),{})
})
test('list has no business mutation surface and has native keyboard search', () => {
  const {source,state}=optionsInstance(path)
  assert.doesNotMatch(source, /window\.(prompt|confirm)|applyTenantTransition|tenantAction|resetSandboxData/)
  assert.match(source, /<button type="submit" class="pct__query">查询/)
  assert.match(source, /v-else-if="error"/); assert.match(source, /:rows="visibleRows"/)
  state.targetTab='brand'; assert.ok(state.pickerHint.includes('品牌'))
})
test('unknown permission context does not show privileged entry', () => {
  const {state}=optionsInstance(path,{}, {getPermissionPatterns:()=>null,canEnterRoute:()=>true})
  assert.equal(state.can('platform.provision.run.view'),false)
})
