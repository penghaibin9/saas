import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const api = fs.readFileSync(new URL('../src/modules/platform/api/moduleCommerce.api.js', import.meta.url), 'utf8')
const workspace = fs.readFileSync(new URL('../src/modules/platform/views/control/ModuleFinanceWorkspace.vue', import.meta.url), 'utf8')
const control = fs.readFileSync(new URL('../src/modules/platform/views/control/PlatformCommercialControlView.vue', import.meta.url), 'utf8')

test('M8 finance stays in the existing commercial control workspace', () => {
  assert.match(control, /ModuleFinanceWorkspace/)
  assert.match(control, /:tenant-id="selectedTenantId"/)
  assert.match(workspace, /应收、退款与发票/)
  assert.doesNotMatch(workspace, /新增学校|切换学校/)
})

test('frontend wires all isolated M8 finance endpoints without altering M1-M5 paths', () => {
  for (const marker of ['/finance-orders','/refunds','/approve','/reject','/settle','/invoices','/issue','/void']) {
    assert.match(api, new RegExp(marker.replace('/', '\\/')))
  }
  assert.match(api, /Idempotency-Key/)
  assert.match(api, /requestRefund/)
  assert.match(api, /requestInvoice/)
  assert.match(api, /listFinanceOrders/)
})

test('receivable UI keeps PlatformOrder authority and never guesses currency', () => {
  assert.match(workspace, /没有第二张“应收余额表”/)
  assert.match(workspace, /订单实时资金投影/)
  assert.match(workspace, /未收应收/)
  assert.match(workspace, /availableFinanceCapacity/)
  assert.match(workspace, /币种待核/)
  assert.match(workspace, /currencyState==='CONFLICT'/)
  assert.match(workspace, /!row\.financeActionAllowed/)
  assert.match(workspace, /row\.orderCurrency\|\|''/)
  assert.doesNotMatch(workspace, /¥/)
  assert.doesNotMatch(workspace, /currency:'CNY'/)
})

test('refund and invoice creation preserve one pending idempotent command per school and subject', () => {
  assert.match(workspace, /gx_module_finance_pending_v1/)
  assert.match(workspace, /pendingCommand/)
  assert.match(workspace, /重试原请求/)
  assert.match(workspace, /sessionStorage\.setItem/)
  assert.match(workspace, /isDefinitiveRejection/)
  assert.match(workspace, /ensurePlatformAccessContext\(\{force:true\}\)/)
})

test('refund settlement never claims to mutate payment truth or entitlement', () => {
  assert.match(workspace, /系统未执行资金退款，也未改变模块授权/)
  assert.match(workspace, /订单支付真值未自动修改/)
  assert.match(workspace, /仍存在有效模块来源/)
  assert.match(workspace, /不得把退款等同于停权/)
  // Safety copy such as “不会自动停权” is required. Reject only text that falsely
  // claims an automatic entitlement mutation actually completed.
  assert.doesNotMatch(workspace, /已自动停权|自动停权完成|已自动取消授权|自动取消授权完成/)
})

test('invoice workflow records external evidence without asking operators for database file ids', () => {
  assert.match(workspace, /系统不会调用税控或第三方开票服务/)
  assert.match(workspace, /外部发票凭据/)
  assert.match(workspace, /不要求手填数据库文件 ID/)
  assert.doesNotMatch(workspace, /invoiceFileId|文件 ID<input|数据库文件ID/)
})

test('money-affecting transitions carry optimistic versions and are role-gated', () => {
  assert.match(workspace, /expectedVersion:row\.version/)
  assert.match(workspace, /order\.manage/)
  assert.match(workspace, /canManage/)
  assert.match(workspace, /recheckAccess/)
})
