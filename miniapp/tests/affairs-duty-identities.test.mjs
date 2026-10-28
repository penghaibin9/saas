import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const roleSource = readFileSync(new URL('../src/config/roles.config.js', import.meta.url), 'utf8')
const roles = await import('data:text/javascript;base64,' + Buffer.from(roleSource).toString('base64'))
const sessionSource = readFileSync(new URL('../src/stores/session.js', import.meta.url), 'utf8')
  .replace(/^import .+$/gm, '').replace('export const useSessionStore =', 'const useSessionStore =')
  .replace('export default useSessionStore', '')

function fixture(switchResponse) {
  let cleared = 0
  const options = new Function('defineStore', 'getRoleConfig', 'hasAction', 'roleKeyFromBackendRole', 'ROLE',
    'switchRoleReal', 'realRequest', 'getToken', 'getRefreshToken', 'clearTokens', 'registerForceLogoutHandler',
    'shouldTryReal', 'ENV', 'setForcePasswordChange', 'useInternshipContextStore', 'clearSensitiveLocalDrafts', 'uni',
    sessionSource + '; return useSessionStore')(
    (_name, value) => value, roles.getRoleConfig, roles.hasAction, roles.roleKeyFromBackendRole, roles.ROLE,
    switchResponse, async () => ({}), () => 'test-access', () => '', () => { cleared++ }, () => {},
    () => true, { allowMockFallback: false }, () => {}, () => ({ clear() {} }), () => {},
    { removeStorageSync() {}, setStorageSync() {}, getStorageSync() { return '' } },
  )
  const vm = { ...options.state() }
  for (const [key, method] of Object.entries(options.actions)) vm[key] = method.bind(vm)
  return { vm, cleared: () => cleared }
}

const identity = code => ({ userId: '42', tenantId: '1', realName: '测试老师',
  currentRole: { roleCode: code, contextId: `role:${code}` },
  availableContexts: [{ roleCode: code, contextId: `role:${code}` }], user: {} })

test('all three basic positions and five standalone duties have explicit mobile identities', () => {
  const codes = ['STUDENT_AFFAIRS_ADMIN', 'STUDENT_AFFAIRS_COLLEGE', 'COUNSELOR', 'FUNDING_TEACHER',
    'PSYCHOLOGY_TEACHER', 'DORM_MANAGER', 'YOUTH_LEAGUE', 'ORG_PERSONNEL']
  const keys = codes.map(roles.roleKeyFromBackendRole)
  assert.equal(new Set(keys).size, 8)
  for (const key of keys) {
    assert.ok(key)
    assert.equal(roles.getRoleConfig(key).side, 'teacher')
    assert.equal(roles.getRoleConfig(key).homeRoute, '/pages/teacher/workbench/index')
  }
  assert.notEqual(roles.roleKeyFromBackendRole('STUDENT_AFFAIRS'), roles.roleKeyFromBackendRole('STUDENT_AFFAIRS_ADMIN'))
})

for (const code of ['FUNDING_TEACHER', 'PSYCHOLOGY_TEACHER', 'DORM_MANAGER', 'YOUTH_LEAGUE', 'ORG_PERSONNEL']) {
  test(`standalone ${code} does not require an extra basic position`, () => {
    const { vm } = fixture()
    vm.applyRealUser(identity(code))
    assert.equal(vm.currentRole, roles.roleKeyFromBackendRole(code))
    assert.deepEqual(vm.availableRoles, [roles.roleKeyFromBackendRole(code)])
    assert.equal(vm.identity.roleCode, code)
  })
}

test('an unsupported server identity cannot inherit the previous role or user projection', () => {
  const { vm, cleared } = fixture()
  vm.logged = true
  vm.applyRealUser(identity('COUNSELOR'))
  assert.throws(() => vm.applyRealUser(identity('UNSUPPORTED_ROLE')), error => error.code === 'UNSUPPORTED_CONTEXT')
  assert.equal(vm.logged, false)
  assert.equal(vm.identity.userId, null)
  assert.equal(vm.realUser, null)
  assert.ok(cleared() > 0)
})

test('a confirmed server switch followed by an invalid identity never restores old sensitive identity', async () => {
  const { vm } = fixture(async () => identity('UNSUPPORTED_ROLE'))
  vm.logged = true
  vm.applyRealUser(identity('COUNSELOR'))
  vm.availableContexts.push(identity('FUNDING_TEACHER').currentRole)
  await assert.rejects(vm.switchRole(roles.ROLE.FUNDING_TEACHER))
  assert.equal(vm.logged, false)
  assert.equal(vm.identity.roleCode, null)
})

test('a rejected server switch preserves the existing valid identity', async () => {
  const { vm, cleared } = fixture(async () => { throw new Error('request failed') })
  vm.logged = true
  vm.applyRealUser(identity('COUNSELOR'))
  vm.availableContexts.push(identity('FUNDING_TEACHER').currentRole)
  await assert.rejects(vm.switchRole(roles.ROLE.FUNDING_TEACHER))
  assert.equal(vm.currentRole, roles.ROLE.COUNSELOR)
  assert.equal(vm.identity.roleCode, 'COUNSELOR')
  assert.equal(cleared(), 0)
})
