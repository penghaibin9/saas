import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { actionDraft, createOrderDraft, orderActions } from '../src/modules/platform/utils/orderWorkspace.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const read = (p) => fs.readFileSync(path.join(root, p), 'utf8')

const tenants = read('src/modules/platform/views/control/PlatformControlTenants.vue')
const provisioning = read('src/modules/platform/views/control/PlatformProvisioningView.vue')
const orders = read('src/modules/platform/views/control/PlatformControlOrders.vue')
const onboarding = read('src/modules/platform/views/PlatformOnboardingCheckView.vue')
const routes = read('src/modules/platform/platform.routes.js')
const api = read('src/modules/platform/api/platformControl.api.js')

test('formal opening starts in Provisioning and cannot directly grant a paid package', () => {
  assert.match(tenants, /\/admin\/platform\/provisioning\?create=1/)
  assert.doesNotMatch(tenants, /createTenant/)
  assert.doesNotMatch(tenants, /convert-to-paid/)
  assert.match(routes, /path: 'tenants\/create'[\s\S]*redirect: '\/admin\/platform\/provisioning\?create=1'/)
  assert.match(provisioning, /targetPackageCode/)
  assert.match(provisioning, /正式授权必须由已支付订单生效/)
})

test('Provisioning stops at bootstrap readiness and protects reveal-once credentials', () => {
  assert.match(provisioning, /基础开户已完成/)
  assert.match(provisioning, /credentialRevealed/)
  assert.match(provisioning, /clearCredential/)
  assert.match(provisioning, /••••••••••••••••/)
  assert.doesNotMatch(provisioning, /initialPassword\s*\}\}/)
})

test('platform acceptance reads canonical delivery evidence without count fallbacks', () => {
  assert.match(onboarding, /listDeliveryReadModels/)
  assert.match(onboarding, /acceptDelivery/)
  assert.match(onboarding, /readModelDigest/)
  assert.match(onboarding, /acceptanceDigest/)
  assert.match(onboarding, /consumerSmokeState/)
  assert.doesNotMatch(onboarding, /studentCount|userCount|readyForAcceptance/)
  assert.match(api, /\/platform\/deliveries/)
  assert.match(api, /consumer-smoke/)
  assert.match(api, /delivery-acceptance/)
})

test('paid-order activation failures expose a real audited repair action', () => {
  assert.match(orders, /repairTaskRequired/)
  assert.match(orders, /repair-activation/)
  assert.match(orders, /@click="openAction\(row, action\)"/)
  assert.match(orders, /platformControlApi\.orderAction\(request\.orderNo, request\.action/)
  assert.match(orders, /expectedVersion: request\.expectedVersion, reason: request\.reason/)
  const paid = { tenantId: '1000000000000000003', orderNo: 'PO-REPAIR-1', version: 3, status: 'paid', repairTaskRequired: true }
  assert.deepEqual(orderActions(paid), ['repair-activation'])
  assert.deepEqual(actionDraft(paid, 'repair-activation', '核对原支付事实后修复'), {
    orderNo: paid.orderNo, tenantId: paid.tenantId, action: 'repair-activation', expectedVersion: 3, reason: '核对原支付事实后修复'
  })
  assert.throws(() => actionDraft(paid, 'mark-paid', '不得重复登记收款'))
  assert.throws(() => actionDraft(paid, 'repair-activation', ''))
})

test('order amount validation rejects zero and malformed values through the actual draft contract', () => {
  assert.match(orders, /createOrderDraft\(this\.form, this\.tenants, this\.packages\)/)
  const tenantId = '1000000000000000003'
  const schools = [{ tenantId }], plans = [{ packageCode: 'standard', enabled: true }]
  const form = { tenantId, packageCode: 'standard', orderType: 'NEW', durationDays: '365', amount: '0.01', remark: '' }
  assert.equal(createOrderDraft(form, schools, plans).amount, '0.01')
  for (const amount of ['0', '', '-1', '1.001', 'NaN']) {
    assert.throws(() => createOrderDraft({ ...form, amount }, schools, plans))
  }
})

test('running Provisioning jobs cannot be cancelled or resumed from the UI', () => {
  assert.match(provisioning, /\['SUCCEEDED', 'CANCELLED', 'RUNNING'\]\.includes\(selected\.status\)/)
  assert.match(provisioning, /@click\.stop="retryStep\(row\)"/)
})
