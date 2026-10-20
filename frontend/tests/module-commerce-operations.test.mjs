import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const api = fs.readFileSync(new URL('../src/modules/platform/api/moduleCommerce.api.js', import.meta.url), 'utf8')
const finance = fs.readFileSync(new URL('../src/modules/platform/views/control/ModuleFinanceWorkspace.vue', import.meta.url), 'utf8')
const operations = fs.readFileSync(new URL('../src/modules/platform/views/control/ModuleOperationsWorkspace.vue', import.meta.url), 'utf8')

test('settled refund continues into explicit existing customer-success ticket flow', () => {
  assert.match(finance, /selectedRefund\.status==='SETTLED'/)
  assert.match(finance, /工单优先级/)
  assert.match(finance, /请明确选择/)
  assert.match(finance, /createAfterSalesTicket/)
  assert.match(finance, /现有客户成功工单/)
  assert.match(finance, /不会自动停权|模块授权未自动修改/)
})

test('M8 operations APIs are additive and wired to the same selected school', () => {
  for (const marker of ['getOperationsOverview','listAfterSales','createAfterSalesTicket','listServiceCosts','recordServiceCost','getSlaPolicy','updateSlaPolicy','resetSlaPolicy']) {
    assert.match(api, new RegExp(marker))
  }
  assert.match(finance, /ModuleOperationsWorkspace/)
  assert.match(finance, /:tenant-id="tenantId"/)
})

test('SLA UI never manufactures a target when policy is absent', () => {
  assert.match(operations, /没有有效的商业 SLA 明确政策/)
  assert.match(operations, /不判“达标\/超时”/)
  assert.match(operations, /slaEditor/)
  assert.match(operations, /effective\?\.configured/)
  assert.match(operations, /系统不会补默认小时数/)
  assert.doesNotMatch(operations, /P0.{0,20}2小时|P1.{0,20}8小时|P2.{0,20}24小时/)
})

test('SLA editor requires all four explicit targets and optimistic version', () => {
  for (const severity of ['P0','P1','P2','P3']) assert.match(operations, new RegExp(severity))
  assert.match(operations, /severities\.every/)
  assert.match(operations, /expectedVersion:slaEditor\.value\?\.tenantOverride\?\.rowVersion\?\?0/)
  assert.match(operations, /commercial\.manage/)
  assert.match(operations, /recheckDuty\('commercial\.manage'/)
  assert.match(operations, /恢复平台默认 \/ 未评估/)
  assert.match(operations, /resetSlaPolicy/)
})

test('customer-success ticket remains the processing authority', () => {
  assert.match(operations, /退款后授权复核工单/)
  assert.match(operations, /SupportTicket/)
  assert.match(operations, /\/admin\/platform\/customer-success/)
  assert.doesNotMatch(operations, /关闭工单|解决工单|transitionSupportTicket/)
})

test('service cost records actual facts only and never converts currencies', () => {
  assert.match(operations, /实际服务成本/)
  assert.match(operations, /不同币种永不自动换算或合计/)
  assert.match(operations, /summaryByCurrency/)
  assert.match(operations, /currencyConverted/)
  assert.match(operations, /Idempotency-Key|recordServiceCost/)
  assert.match(operations, /gx_module_service_cost_pending_v1/)
  assert.doesNotMatch(operations, /汇率|exchangeRate|fxRate/)
})

test('actual cost requires traceability to at least one real business object', () => {
  assert.match(operations, /supportTicketId/)
  assert.match(operations, /refundCaseId/)
  assert.match(operations, /orderId/)
  assert.match(operations, /refsOk/)
  assert.match(operations, /至少关联订单\/退款\/工单一个对象/)
})
