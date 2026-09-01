import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

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
  assert.match(orders, /修复订单授权激活/)
  assert.match(orders, /:min="0\.01"/)
})

test('running Provisioning jobs cannot be cancelled or resumed from the UI', () => {
  assert.match(provisioning, /\['SUCCEEDED', 'CANCELLED', 'RUNNING'\]\.includes\(selected\.status\)/)
  assert.match(provisioning, /@click\.stop="retryStep\(row\)"/)
})
