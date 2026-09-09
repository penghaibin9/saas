import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const api = fs.readFileSync(new URL('../src/modules/platform/api/moduleCommerce.api.js', import.meta.url), 'utf8')
const renewal = fs.readFileSync(new URL('../src/modules/platform/views/control/ModuleRenewalWorkspace.vue', import.meta.url), 'utf8')
const parent = fs.readFileSync(new URL('../src/modules/platform/views/control/PlatformCommercialControlView.vue', import.meta.url), 'utf8')

test('renewal workspace uses the same school and existing commercial control page', () => {
  assert.match(parent, /ModuleRenewalWorkspace/)
  assert.match(parent, /:tenant-id="selectedTenantId"/)
  assert.match(parent, /@focus-sales="focusSalesRenewal"/)
  assert.match(renewal, /模块续费治理工作区/)
  assert.doesNotMatch(renewal, /新增学校|切换学校/)
})

test('renewal APIs are additive and do not create a second sales writer', () => {
  assert.match(api, /listRenewalCandidates/)
  assert.match(api, /createRenewalFollowup/)
  assert.match(api, /renewal-candidates/)
  assert.match(api, /renewal-followup/)
  assert.doesNotMatch(renewal, /createSalesOrder|previewSalesOrder|markOrderPaid|paymentGateway/)
})

test('customer success handoff and sales order duties stay separate', () => {
  assert.match(renewal, /customerSuccess\.manage/)
  assert.match(renewal, /order\.manage/)
  assert.match(renewal, /处理 RenewalTask/)
  assert.match(renewal, /定位原分项续费/)
  assert.match(renewal, /不会自动创建续费订单/)
  assert.match(renewal, /不会扣款/)
})

test('renewal handoff never invents next price or service end date', () => {
  assert.match(renewal, /已付服务截止/)
  assert.match(renewal, /新商品版本、成交价和新的服务截止必须在销售工作区重新明确确认/)
  assert.doesNotMatch(renewal, /unitPrice\s*:/)
  assert.doesNotMatch(renewal, /endAt\s*:/)
})

test('stop-renew and backend blockers remain visible rather than bypassed', () => {
  assert.match(renewal, /row\.blocker/)
  assert.match(renewal, /sourceStatus/)
  assert.doesNotMatch(renewal, /resumeRenewal\(/)
})
