import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const pamApi = read('src/modules/platform/api/platformPam.api.js')
const access = read('src/modules/platform/views/control/PlatformAccessView.vue')
const customer = read('src/modules/platform/views/control/PlatformCustomerSuccessView.vue')
const tenantProfile = read('src/modules/platform/components/TenantProfileEditor.vue')
const platformLayout = read('src/modules/platform/views/AdminPlatformLayout.vue')
const systemPanel = read('src/modules/system/components/SystemP1ClosurePanel.vue')
const systemLayout = read('src/modules/system/views/AdminSystemLayout.vue')
const systemClosureApi = read('src/modules/system/api/systemP1Closure.api.js')

test('controlled support session can enter a real scoped workspace', () => {
  assert.match(pamApi, /getSupportTenantContext/)
  assert.match(pamApi, /getSupportTenantAudit/)
  assert.match(access, /进入协助/)
  assert.match(access, /supportWorkspace/)
  assert.match(access, /tenant\.context\.read/)
  assert.match(access, /tenant\.audit\.read/)
  assert.match(access, /stepUpMfa/)
  assert.match(pamApi, /auth:\s*false/)
  assert.match(pamApi, /Authorization:\s*`Bearer \$\{mfaAccessToken\}`/)
})

test('customer success consumes training and renewal write APIs', () => {
  assert.match(customer, /listTrainings/)
  assert.match(customer, /createTraining/)
  assert.match(customer, /completeTraining/)
  assert.match(customer, /listRenewalTasks/)
  assert.match(customer, /createRenewalTask/)
  assert.match(customer, /transitionRenewalTask/)
  assert.match(customer, /培训计划与完成记录/)
  assert.match(customer, /续费跟进任务/)
})

test('tenant detail route exposes real base profile maintenance without a new menu', () => {
  assert.match(platformLayout, /TenantProfileEditor/)
  assert.match(platformLayout, /platform-tenant-detail/)
  assert.match(tenantProfile, /updateTenant/)
  assert.match(tenantProfile, /contactWechat/)
  assert.match(tenantProfile, /schoolType/)
})

test('role assignment route can create a governed role grant', () => {
  assert.match(systemLayout, /SystemP1ClosurePanel/)
  assert.match(systemPanel, /grantRoleAssignment/)
  assert.match(systemPanel, /effectiveAt/)
  assert.match(systemPanel, /expiresAt/)
  assert.match(systemPanel, /正式角色授权/)
})

test('security config can revoke an active override and restore inheritance', () => {
  assert.match(systemClosureApi, /effective-config-overrides/)
  assert.match(systemPanel, /revokeConfigOverride/)
  assert.match(systemPanel, /恢复继承/)
  assert.match(systemPanel, /expectedVersion/)
})

test('account exception route can resolve and revoke stable identity bindings', () => {
  assert.match(systemPanel, /getEffectiveIdentity/)
  assert.match(systemPanel, /unbindIdentity/)
  assert.match(systemPanel, /identitySource/)
  assert.match(systemPanel, /错误绑定已解除/)
})

test('organization deprecation is guarded by same-node impact preview', () => {
  assert.match(systemPanel, /getOrgNodeImpact/)
  assert.match(systemPanel, /permitStore/)
  assert.match(systemPanel, /systemApi\.deprecateOrgNode\s*=\s*async/)
  assert.match(systemPanel, /5 \* 60 \* 1000/)
  assert.match(systemPanel, /组织作废前必须先在页面顶部执行真实影响预演/)
})
