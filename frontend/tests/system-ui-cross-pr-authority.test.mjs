import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8')
const bridge = read('../src/modules/system/api/systemAuthorityCompatibility.js')
const layout = read('../src/modules/system/views/AdminSystemLayout.vue')
const moduleFeature = read('../src/modules/system/views/SystemModuleFeatureView.vue')

test('system layout installs the authority bridge without replacing the shared portal shell', () => {
  assert.match(layout, /import BasePortalLayout from '@\/layouts\/BasePortalLayout\.vue'/)
  assert.match(layout, /installSystemAuthorityCompatibility\(systemApi\)/)
  assert.equal((layout.match(/<BasePortalLayout\b/g) || []).length, 1)
  assert.doesNotMatch(layout, /import .*navPlan|from ['\"]@\/config\/navPlan['\"]|import .*main\.js|base-portal-theme-controls/)
})

test('compatibility bridge carries object versions on all cross-authority mutations', () => {
  for (const fragment of [
    "body: { action: 'DISABLE', reason, expectedVersion: version }",
    'expectedVersion: version',
    "body: { reason, expectedVersion: version }",
    "original.setUserStatus(id, { ...options, expectedVersion: version })",
    "original.resetUserPassword(id, { ...options, expectedVersion: version })",
    "original.updateUser(id, { ...payload, expectedVersion: version })"
  ]) assert.ok(bridge.includes(fragment), `missing versioned authority contract: ${fragment}`)

  assert.match(bridge, /未取得账号版本，已阻止无乐观锁/)
  assert.match(bridge, /未取得角色版本，已阻止无乐观锁/)
  assert.match(bridge, /未取得品牌版本，已阻止无乐观锁/)
})

test('versions are learned from list and detail reads, including direct role deep links', () => {
  assert.match(bridge, /systemApi\.getUsers = async/)
  assert.match(bridge, /systemApi\.getUserDetail = async/)
  assert.match(bridge, /systemApi\.getRoles = async/)
  assert.match(bridge, /systemApi\.getRoleDetail = async/)
  assert.match(bridge, /systemApi\.getBrandConfig = async/)
  assert.match(bridge, /rememberVersion\(state\.userVersions/)
  assert.match(bridge, /rememberVersion\(state\.roleVersions/)
})

test('authority version caches are invalidated when tenant, subject or active context changes', () => {
  assert.match(bridge, /systemApi\.getContext = async/)
  assert.match(bridge, /function rememberContext/)
  assert.match(bridge, /state\.brandVersion = null/)
  assert.match(bridge, /state\.userVersions\.clear\(\)/)
  assert.match(bridge, /state\.roleVersions\.clear\(\)/)
  assert.match(bridge, /access\.tenantId/)
  assert.match(bridge, /access\.subjectId/)
  assert.match(bridge, /access\.activeContextId/)
})

test('post-commit cache failure uses recovery-only endpoints and never replays the write', () => {
  assert.match(bridge, /cacheRecoveryRequired !== true/)
  assert.match(bridge, /\/auth-cache\/recover/)
  assert.match(bridge, /\/system\/auth-cache\/recover/)
  assert.match(bridge, /原业务操作没有重放/)
  assert.match(bridge, /请不要重复提交原操作/)

  const settle = bridge.slice(bridge.indexOf('async function settleCommittedReceipt'), bridge.indexOf('function expectedVersion'))
  assert.doesNotMatch(settle, /setUserStatus|resetUserPassword|assignUserRoles|deprecateRole|resetBrandConfig/)
})

test('retired bulk module-feature writer is not reintroduced', () => {
  assert.match(moduleFeature, /listCapabilitySettings/)
  assert.match(moduleFeature, /setCapabilitySetting/)
  assert.match(moduleFeature, /expectedVersion:\s*this\.pending\.version/)
  assert.doesNotMatch(moduleFeature, /setModuleFeatures|module-features.*method:\s*['\"]PUT/)
})

test('bridge stays inside the system module and does not import platform or global navigation writers', () => {
  assert.doesNotMatch(bridge, /platform\/|navPlan|BasePortalLayout|main\.js/)
  assert.match(bridge, /systemApi\.resetBrandConfig = async/)
  assert.match(bridge, /systemApi\.deprecateRole = async/)
  assert.match(bridge, /systemApi\.assignUserRoles = async/)
})
