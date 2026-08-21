import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const api = read('src/modules/platform/api/platformSecurityOps.api.js')
const mfa = read('src/modules/platform/components/PlatformMfaPanel.vue')
const offboarding = read('src/modules/platform/components/TenantOffboardingPanel.vue')
const securityView = read('src/modules/platform/views/control/PlatformControlSecurity.vue')
const tenantView = read('src/modules/platform/views/control/PlatformControlTenantDetail.vue')

test('destructive purge uses request-scoped MFA bearer token only', () => {
  assert.match(api, /approveTenantPurge/)
  assert.match(api, /auth:\s*false/)
  assert.match(api, /Authorization:\s*`Bearer \$\{mfaAccessToken\}`/)
  assert.doesNotMatch(api, /setToken\s*\(/)
  assert.doesNotMatch(api, /applyAuthSession\s*\(/)
  assert.doesNotMatch(api, /localStorage|sessionStorage|indexedDB/i)
})

test('offboarding UI keeps the irreversible confirmation and volatile MFA boundary', () => {
  assert.match(offboarding, /永久销毁租户数据/)
  assert.match(offboarding, /confirmText === '永久销毁租户数据'/)
  assert.match(offboarding, /beforeUnmount\(\)\s*{\s*this\.clearMfaGrant\(\)/)
  assert.match(offboarding, /mfaExpiryTimer/)
  assert.match(offboarding, /auth.*MFA|MFA.*二次认证/i)
  assert.doesNotMatch(offboarding, /localStorage|sessionStorage|indexedDB/i)
})

test('retention UI interprets backend naive timestamps as UTC', () => {
  assert.match(offboarding, /serverUtcEpoch/)
  assert.match(offboarding, /`\$\{raw\}Z`/)
})

test('native TOTP enrollment never claims a fake QR scanner', () => {
  assert.match(mfa, /当前前端不伪造二维码/)
  assert.match(mfa, /provisioningUri/)
  assert.match(mfa, /6 位动态码/)
  assert.doesNotMatch(mfa, /<AppQRCode\b/)
  assert.doesNotMatch(mfa, /localStorage|sessionStorage|indexedDB/i)
})

test('MFA and offboarding controls are mounted in existing platform workspaces', () => {
  assert.match(securityView, /<PlatformMfaPanel\s*\/>/)
  assert.match(tenantView, /key:\s*'offboarding',\s*label:\s*'退租与数据销毁'/)
  assert.match(tenantView, /<TenantOffboardingPanel/)
  assert.match(tenantView, /v-else-if="tab === 'offboarding'"/)
})

test('effective login policy parameters are editable from platform security UI', () => {
  assert.match(securityView, /key:\s*'passwordMinLength'/)
  assert.match(securityView, /key:\s*'captchaAfterFailures'/)
  assert.match(securityView, /密码最小长度/)
  assert.match(securityView, /连续失败后启用验证码/)
})
