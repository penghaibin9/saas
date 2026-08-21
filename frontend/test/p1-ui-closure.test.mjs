import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const pamApi = read('src/modules/platform/api/platformPam.api.js')
const access = read('src/modules/platform/views/control/PlatformAccessView.vue')
const customer = read('src/modules/platform/views/control/PlatformCustomerSuccessView.vue')
const tenantProfile = read('src/modules/platform/components/TenantProfileEditor.vue')
const platformP1Api = read('src/modules/platform/api/platformP1Closure.api.js')
const platformLayout = read('src/modules/platform/views/AdminPlatformLayout.vue')
const systemPanel = read('src/modules/system/components/SystemP1ClosurePanel.vue')
const systemLayout = read('src/modules/system/views/AdminSystemLayout.vue')
const systemClosureApi = read('src/modules/system/api/systemP1Closure.api.js')

test('controlled support workspace uses scoped reads and actively expires volatile MFA grants', () => {
  assert.match(pamApi, /getSupportTenantContext/)
  assert.match(pamApi, /getSupportTenantAudit/)
  assert.match(access, /进入协助/)
  assert.match(access, /tenant\.context\.read/)
  assert.match(access, /tenant\.audit\.read/)
  assert.match(access, /stepUpMfa/)
  assert.match(access, /mfaExpiryTimer/)
  assert.match(access, /token\.expiresIn/)
  assert.match(access, /beforeUnmount\(\)\s*{\s*this\.closeSupportWorkspace\(\)/)
  assert.match(access, /serverUtcEpoch/)
  assert.match(pamApi, /auth:\s*false/)
  assert.match(pamApi, /Authorization:\s*`Bearer \$\{mfaAccessToken\}`/)
  assert.doesNotMatch(access, /localStorage|sessionStorage|indexedDB/i)
})

test('customer success sends aware UTC timestamps and mirrors terminal state-machine actions', () => {
  assert.match(customer, /listTrainings/)
  assert.match(customer, /createTraining/)
  assert.match(customer, /completeTraining/)
  assert.match(customer, /listRenewalTasks/)
  assert.match(customer, /createRenewalTask/)
  assert.match(customer, /transitionRenewalTask/)
  assert.match(customer, /const toUtcIso = \(value\) => value \? new Date\(value\)\.toISOString\(\)/)
  assert.match(customer, /displayServerUtc/)
  assert.match(customer, /\['OPEN','RESOLVED'\]\.includes\(row\.status\)/)
  assert.match(customer, /\['OPEN','IN_PROGRESS'\]\.includes\(row\.status\)/)
  assert.match(customer, /!\['RENEWED','CHURNED'\]\.includes\(row\.status\)/)
})

test('tenant detail profile uses a dedicated optimistic audited API and keeps environment read-only', () => {
  assert.match(platformLayout, /TenantProfileEditor/)
  assert.match(platformLayout, /platform-tenant-detail/)
  assert.match(platformP1Api, /\/profile/)
  assert.match(tenantProfile, /updateTenantProfile/)
  assert.match(tenantProfile, /expectedVersion:\s*this\.tenant\.version/)
  assert.match(tenantProfile, /变更原因（必填）/)
  assert.match(tenantProfile, /运行环境（只读）/)
  assert.doesNotMatch(tenantProfile, /v-model="form\.environment"/)
})

test('formal role UI is immediate-only and hides writes without grant authority', () => {
  assert.match(systemLayout, /SystemP1ClosurePanel/)
  assert.match(systemPanel, /grantRoleAssignment/)
  assert.match(systemPanel, /未来排期暂不开放/)
  assert.match(systemPanel, /canGrantRole/)
  assert.match(systemPanel, /systemAdmin\.user\.assign/)
  assert.match(systemPanel, /systemAdmin\.role\.config/)
  assert.match(systemPanel, /expiresAt/)
  assert.doesNotMatch(systemPanel, /roleForm\.effectiveAt/)
})

test('security config restores the complete tenant override chain atomically', () => {
  assert.match(systemClosureApi, /effective-config-overrides/)
  assert.match(systemClosureApi, /restoreConfigInheritance/)
  assert.match(systemPanel, /overrideChain/)
  assert.match(systemPanel, /restoreConfigInheritance/)
  assert.match(systemPanel, /恢复继承/)
  assert.match(systemClosureApi, /expectedVersion:\s*item\.version/)
  assert.match(systemPanel, /canRestoreConfig/)
})

test('identity exception view separates read authority from destructive unbind authority', () => {
  assert.match(systemPanel, /getEffectiveIdentity/)
  assert.match(systemPanel, /unbindIdentity/)
  assert.match(systemPanel, /identitySource/)
  assert.match(systemPanel, /canUnbindIdentity/)
  assert.match(systemPanel, /systemAdmin\.user\.bind/)
  assert.match(systemPanel, /错误绑定已解除/)
})

test('organization deprecation carries a signed preview receipt to the server write boundary', () => {
  assert.match(systemPanel, /getOrgNodeImpact/)
  assert.match(systemPanel, /previewToken/)
  assert.match(systemPanel, /expectedVersion:\s*this\.orgImpact\.nodeVersion/)
  assert.match(systemClosureApi, /deprecateOrgNodeWithPreview/)
  assert.match(systemClosureApi, /previewToken/)
  assert.match(systemClosureApi, /expectedVersion/)
  assert.match(systemPanel, /systemApi\.deprecateOrgNode\s*=\s*async/)
  assert.match(systemPanel, /服务端签名预演凭证/)
})