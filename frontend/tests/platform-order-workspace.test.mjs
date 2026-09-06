import test from 'node:test'
import assert from 'node:assert/strict'
import * as contracts from '../src/modules/platform/utils/orderWorkspace.mjs'
import { optionsInstance, deferred, plain } from './platform-workspace-test-support.mjs'

const path = '../src/modules/platform/views/control/PlatformControlOrders.vue'
const tid = '1000000000000000003'
const school = { tenantId: tid, tenantName: '业务验收学校', tenantCode: 'SCHOOL-A' }
const plan = { packageCode: 'standard', packageName: '标准版', price: 12345.67, durationDays: 30, enabled: true }
const row = (patch = {}) => ({ ...school, orderId: '99', orderNo: 'PO-EXACT-1', packageCode: 'standard', amount: 12345.67, status: 'unpaid', version: 1, activationState: 'NOT_APPLICABLE', repairTaskRequired: false, ...patch })
function make(api = {}, state = {}, deps = {}) {
  return optionsInstance(path, state, { ...contracts, platformControlApi: api, ...deps })
}
function prepareAction(state, action = 'mark-paid', value = row()) {
  state.rows = [value]; state.openAction(value, action); state.reason = '已核验实际收款依据'; state.review(); state.confirmation = value.orderNo
}
const paid = (extra = {}) => ({ code: 0, data: { orderNo: row().orderNo, status: 'paid', version: 3, tenantActivated: true, repairTaskRequired: false, ...extra } })

for (const value of [null, undefined, '', ' ', false, NaN, Infinity, -1, '1e3', '0.001', '10000000000']) {
  test(`money does not fabricate zero for ${String(value)}`, () => assert.equal(contracts.cents(value), null))
}
test('money keeps cents, valid zero, and the backend decimal ceiling', () => {
  assert.equal(contracts.cents('0'), 0); assert.equal(contracts.cents('0.01'), 1)
  assert.equal(contracts.cents('9999999999.99'), 999999999999)
  assert.equal(contracts.moneyLabel('12.50'), '￥12.50')
})
test('invalid school scope never falls back to an all-school query', () => {
  for (const query of [{tenantId:['1']}, {tenantId:Number(tid)}, {tenantId:'../1'}, {status:'new_status'}, {keyword:['bad']}]) assert.throws(() => contracts.orderScope(query))
  assert.equal(contracts.orderScope({tenantId:tid}).tenantId,tid)
})
test('list rejects missing, duplicated or foreign-scope orders', () => {
  for (const data of [null, {}, {list:[row(),row()]}, {list:[row({tenantId:'7'})]}, {list:[row()],total:2}]) assert.throws(() => contracts.orderRows(data,{tenantId:tid}))
  assert.deepEqual(contracts.orderRows({list:[]}),[])
})
test('paid status alone is not proof of activation', () => {
  assert.equal(contracts.orderStatus(row({status:'paid',activationState:undefined,repairTaskRequired:undefined})).tone,'warning')
  assert.equal(contracts.orderStatus(row({status:'paid',activationState:'ACTIVE'})).tone,'success')
  assert.equal(contracts.orderActions(row({version:undefined})).length,0)
  assert.equal(contracts.orderActions(row({status:'paid',repairTaskRequired:true}))[0],'repair-activation')
})
test('create validates catalog and tenant membership and freezes exact decimal amount', () => {
  const form={tenantId:tid,packageCode:'standard',orderType:'RENEW',durationDays:'30',amount:'12345.67',remark:'合同核验'}
  const draft=contracts.createOrderDraft(form,[school],[plan])
  assert.equal(draft.amount,'12345.67');assert.ok(Object.isFrozen(draft))
  for (const patch of [{amount:''},{amount:'0'},{amount:'12.001'},{durationDays:'0'},{durationDays:'1.5'},{tenantId:'7'},{packageCode:'trial'},{orderType:'ADDON'}]) assert.throws(()=>contracts.createOrderDraft({...form,...patch},[school],[plan]))
})
test('viewing school orders scopes the read and never starts a new order',async()=>{
  let params,tenants=0
  const {state}=make({listOrders:async p=>{params=p;return {code:0,data:{list:[row()]}}},listTenants:async()=>{tenants++}},{$route:{path:'/admin/platform/orders',query:{tenantId:tid},params:{}}})
  await state.load();assert.deepEqual(plain(params),{tenantId:tid});assert.equal(state.work,null);assert.equal(tenants,0)
})
test('order read failure clears stale data and shows error instead of empty success',async()=>{
  const {state}=make({listOrders:async()=>({code:403,message:'无订单查看权限'})})
  state.rows=[row()];state.loadedAt='old';await state.load();assert.equal(state.rows.length,0);assert.equal(state.loadedAt,'');assert.equal(state.error,'无订单查看权限');assert.equal(state.loading,false)
})
test('malformed query blocks the read before any request',async()=>{
  let reads=0;const {state}=make({listOrders:async()=>{reads++}},{$route:{query:{tenantId:'bad'}}})
  await state.load();assert.equal(reads,0);assert.ok(state.error)
})
test('late reads do not overwrite newer school results',async()=>{
  const a=deferred(),b=deferred();let reads=0
  const {state}=make({listOrders:()=>++reads===1?a.promise:b.promise})
  const first=state.load(),second=state.load();b.resolve({code:0,data:{list:[row({orderNo:'PO-NEW'})]}});await second;a.resolve({code:0,data:{list:[row()]}});await first;assert.equal(state.rows[0].orderNo,'PO-NEW')
})
test('search and page rendering preserve complete-list totals without sending unsupported keyword',async()=>{
  let params
  const rows=Array.from({length:25},(_,i)=>row({orderNo:`PO-${i}`,tenantName:i<22?'匹配学校':'其他学校'}))
  const {state}=make({listOrders:async p=>{params=p;return {code:0,data:{list:rows}}}},{$route:{query:{keyword:'匹配学校'}}})
  await state.load();assert.deepEqual(plain(params),{});assert.equal(state.filteredRows.length,22);assert.equal(state.visibleRows.length,20);state.page=2;assert.equal(state.visibleRows.length,2)
})
test('permission loss after review prevents the actual order command',async()=>{
  let allowed=true,writes=0
  const {state}=make({orderAction:async()=>{writes++}}, {}, {canEnterRoute:()=>allowed})
  prepareAction(state);allowed=false;await state.submitPrepared();assert.equal(writes,0)
})
test('reason and order version must be supplied, never replaced with one',async()=>{
  let writes=0;const {state}=make({orderAction:async()=>{writes++}})
  state.rows=[row({version:undefined})];state.openAction(state.rows[0],'mark-paid');assert.equal(state.work,null)
  prepareAction(state);state.reason='短';state.phase='edit';state.review();assert.equal(state.phase,'edit');await state.submitPrepared();assert.equal(writes,0)
})
test('typed order number and frozen review are required',async()=>{
  let writes=0;const {state}=make({orderAction:async()=>{writes++;return paid()}})
  prepareAction(state);state.confirmation='PO-OTHER';await state.submitPrepared();assert.equal(writes,0)
  state.confirmation=row().orderNo;state.reason='核对后修改了原因';await state.submitPrepared();assert.equal(writes,0);assert.equal(state.phase,'edit')
})
test('double click sends exactly one payment command with the original version',async()=>{
  const pending=deferred();let calls=[]
  const {state}=make({orderAction:(...args)=>{calls.push(args);return pending.promise}})
  prepareAction(state);const a=state.submitPrepared(),b=state.submitPrepared();assert.equal(calls.length,1)
  assert.deepEqual(plain(calls[0]),[row().orderNo,'mark-paid',{expectedVersion:1,reason:'已核验实际收款依据'}])
  pending.resolve(paid());await Promise.all([a,b]);await state.submitPrepared();assert.equal(calls.length,1);assert.equal(state.receipt.result,'activated')
})
test('payment recorded but activation failed remains a distinct durable outcome',async()=>{
  const {state}=make({orderAction:async()=>paid({version:2,tenantActivated:false,repairTaskRequired:true})})
  prepareAction(state);await state.submitPrepared();assert.equal(state.receipt.result,'paid-pending');assert.equal(state.phase,'saved');assert.match(state.receiptLabel,/激活待修复/)
})
test('repair uses only repair-activation and advances its exact version',async()=>{
  let args;const {state}=make({orderAction:async(...values)=>{args=values;return paid()}})
  prepareAction(state,'repair-activation',row({status:'paid',version:2,repairTaskRequired:true,activationState:'REPAIR_REQUIRED'}))
  await state.submitPrepared();assert.equal(args[1],'repair-activation');assert.equal(args[2].expectedVersion,2);assert.equal(state.receipt.result,'activated')
})
test('cancel validates cancelled state rather than assuming a generic success',async()=>{
  const {state}=make({orderAction:async()=>({code:0,data:{orderNo:row().orderNo,status:'cancelled',version:2}})})
  prepareAction(state,'cancel');await state.submitPrepared();assert.equal(state.receipt.result,'cancelled')
})
for (const data of [null,{}, {orderNo:'PO-OTHER',status:'paid',version:3,tenantActivated:true,repairTaskRequired:false}, {orderNo:row().orderNo,status:'paid',version:1,tenantActivated:true,repairTaskRequired:false}, {orderNo:row().orderNo,status:'paid',version:3}]) {
  test(`incomplete receipt stays uncertain: ${JSON.stringify(data)}`,async()=>{
    const {state}=make({orderAction:async()=>({code:0,data})});prepareAction(state);await state.submitPrepared();assert.equal(state.receipt,null);assert.equal(state.phase,'uncertain')
  })
}
test('timeout permits readback but cannot replay the original mutation',async()=>{
  let writes=0,reads=0
  const {state}=make({orderAction:async()=>{writes++;throw new Error('timeout')},listOrders:async()=>{reads++;return {code:0,data:{list:[row({status:'paid',version:3,activationState:'ACTIVE'})]}}}})
  prepareAction(state);await state.submitPrepared();await state.inspectOutcome();await state.submitPrepared();assert.equal(writes,1);assert.equal(reads,1);assert.equal(state.phase,'uncertain');assert.equal(state.receipt,null);assert.ok(state.readback)
})
test('cross-school readback is not accepted as evidence',async()=>{
  const {state}=make({orderAction:async()=>({code:409,bizCode:'DATA_CONFLICT'}),listOrders:async()=>({code:0,data:{list:[row({tenantId:'7'})]}})})
  prepareAction(state);await state.submitPrepared();await state.inspectOutcome();assert.equal(state.phase,'conflict');assert.equal(state.readback,'');assert.ok(state.workError)
})
test('create uses live catalog values only after selection and verifies returned school ownership',async()=>{
  let created
  const {state}=make({listTenants:async()=>({code:0,data:{list:[school]}}),listPackages:async()=>({code:0,data:{list:[plan]}}),createOrder:async request=>{created=request;return {code:0,data:{orderNo:row().orderNo,orderId:'99',status:'unpaid',version:1}}},listOrders:async()=>({code:0,data:{list:[row()]}})})
  await state.startCreate();assert.equal(state.form.amount,'');state.form.tenantId=tid;state.form.packageCode='standard';state.choosePackage();assert.equal(state.form.amount,'12345.67');state.review();state.confirmation=school.tenantCode;await state.submitPrepared()
  assert.equal(created.amount,'12345.67');assert.equal(state.receipt.result,'created')
})
test('unverified creation cannot be reported successful or automatically repeated',async()=>{
  let writes=0
  const {state}=make({listTenants:async()=>({code:0,data:{list:[school]}}),listPackages:async()=>({code:0,data:{list:[plan]}}),createOrder:async()=>{writes++;return {code:0,data:{orderNo:row().orderNo,orderId:'99',status:'unpaid',version:1}}},listOrders:async()=>({code:0,data:{list:[]}})})
  await state.startCreate();Object.assign(state.form,{tenantId:tid,packageCode:'standard',amount:'1',durationDays:'30'});state.review();state.confirmation=school.tenantCode;await state.submitPrepared();await state.submitPrepared();assert.equal(writes,1);assert.equal(state.phase,'uncertain')
})
test('unmount invalidates a late payment response',async()=>{
  const pending=deferred();const {state,definition}=make({orderAction:()=>pending.promise});prepareAction(state);const writing=state.submitPrepared();definition.beforeUnmount.call(state);pending.resolve(paid());await writing;assert.equal(state.receipt,null)
})
test('navigation protects the active work area and cannot leave during a write',async()=>{
  const {state,calls}=make();prepareAction(state);assert.equal(state.guardNavigation('/admin/platform/tenants'),false);state.busy=true;await state.leave();assert.equal(calls.length,0)
})
test('unknown permission context never displays mutation controls',()=>{
  const {state,source}=make({}, {}, {getPermissionPatterns:()=>null});assert.equal(state.can('platform.order.manage'),false)
  assert.doesNotMatch(source,/AppDrawer|window\.(prompt|confirm)|row\.version\s*\|\|\s*1/)
})


test('failed leave retains the in-memory work and reports the navigation error', async () => {
  const { state } = make()
  state.work = { kind: 'create' }; state.pendingNavigation = '/admin/platform/tenants'
  state.$router.push = async () => { throw new Error('navigation interrupted') }
  await state.leave()
  assert.equal(state.work.kind, 'create'); assert.equal(state.pendingNavigation, '/admin/platform/tenants')
  assert.equal(state.leaving, false); assert.equal(state.workError, 'navigation interrupted')
})
