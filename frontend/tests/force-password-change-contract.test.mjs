import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

const login = readFileSync(new URL('../src/views/LoginView.vue', import.meta.url), 'utf8')
const platformLogin = readFileSync(new URL('../src/views/PlatformLoginView.vue', import.meta.url), 'utf8')
const platformGate = readFileSync(new URL('../src/security/platformAccessGate.js', import.meta.url), 'utf8')
const force = readFileSync(new URL('../src/views/ForcePasswordChangeView.vue', import.meta.url), 'utf8')

test('school PC login consumes backend mustChangePassword before entering workbench', () => {
  assert.match(login, /data\?\.user\?\.mustChangePassword/)
  assert.match(login, /forcePasswordChange:\s*'1'/)
  const forcePos = login.indexOf('data?.user?.mustChangePassword')
  const workbenchPos = login.indexOf('this.$router.push(')
  assert.ok(forcePos >= 0 && workbenchPos > forcePos)
})

test('platform PC login consumes backend mustChangePassword before capability-routed control plane', () => {
  assert.match(platformLogin, /data\?\.user\?\.mustChangePassword/)
  assert.match(platformLogin, /forcePasswordChange:\s*'1'/)
  assert.match(platformLogin, /login-route="\/platform-login"/)
  assert.match(platformLogin, /ensurePlatformAccessContext\(\{ force: true \}\)/)
  assert.match(platformLogin, /resolvePlatformHome\(context\)/)

  const forcePos = platformLogin.indexOf('data?.user?.mustChangePassword')
  const contextPos = platformLogin.indexOf('ensurePlatformAccessContext({ force: true })')
  const homePos = platformLogin.indexOf('resolvePlatformHome(context)')
  assert.ok(forcePos >= 0 && contextPos > forcePos && homePos > contextPos)

  // Root keeps the historical overview landing, while delegated operators land
  // only on a page their server-authoritative duties permit.
  assert.match(platformGate, /if \(isPlatformRoot\(\)\) return '\/admin\/platform\/overview'/)
  assert.match(platformGate, /duties\.has\('access\.review'\).*'\/admin\/platform\/access'/)
  assert.match(platformGate, /duties\.has\('commercial\.view'\).*'\/admin\/platform\/orders'/)
  assert.match(platformGate, /return '\/security\/403'/)
})

test('forced password screen calls real change-password then clears old session', () => {
  assert.match(force, /request\('\/auth\/change-password'/)
  assert.match(force, /oldPassword:/)
  assert.match(force, /newPassword:/)
  assert.match(force, /clearAuthSession\(\)/)
  assert.match(force, /router\.replace\(this\.loginRoute\)/)
  assert.match(force, /loginRoute:\s*\{\s*type:\s*String,\s*default:\s*'\/login'/)
  assert.doesNotMatch(force, /mock/i)
})
test('学院教务按本次登录岗位进入教学首页，保留返回地址和首次改密门禁', async () => {
  let response, platform = false
  const script = login.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]/g, (_, binding) => {
      const value = binding.trim().replace(/\s+as\s+/g, ': ')
      return `const ${value} = dependencies${value.startsWith('{') ? '' : '.' + value}`
    }).replace('export default', 'component =')
  const sandbox = { dependencies: {
    loginWithPassword: async () => response,
    isPlatformSuperAdmin: () => platform,
    toast: { success() {}, info() {} }
  } }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component, pushed = [], replaced = []
  const state = { ...component.data(), ...component.methods, agree: true,
    form: { loginName: 'school-admin-old', password: 'test-only', tenantCode: '', identifierType: 'ACCOUNT' },
    captchaFlow: { ensureNonce: async () => {} },
    $route: { query: {} },
    $router: { push: path => pushed.push(path), replace: path => replaced.push(path) }
  }
  const successfulResponse = role => ({ displayName: '测试岗位', currentRole: { roleCode: role, roleName: '测试岗位' }, user: { mustChangePassword: false } })
  for (const [role, redirect, expected] of [
    ['COLLEGE_ADMIN', undefined, '/admin/academic-affairs'],
    ['COLLEGE_ADMIN', '/admin/academic-affairs/grade-entry', '/admin/academic-affairs/grade-entry'],
    ['ACADEMIC_ADMIN', undefined, '/workbench'],
    ['ACADEMIC_TEACHER', undefined, '/workbench'],
    ['COUNSELOR', undefined, '/workbench'],
    ['', undefined, '/workbench']
  ]) {
    response = successfulResponse(role); state.$route.query = { redirect }
    await state.doLogin()
    assert.equal(state.error, ''); assert.equal(pushed.at(-1), expected, role)
  }
  platform = true; response = successfulResponse('PLATFORM_SUPER_ADMIN')
  await state.doLogin(); assert.equal(pushed.at(-1), '/admin/platform/overview'); platform = false
  const before = pushed.length
  response = { ...successfulResponse('COLLEGE_ADMIN'), user: { mustChangePassword: true } }
  state.$route.query = {}; await state.doLogin()
  assert.equal(pushed.length, before); assert.equal(replaced.at(-1).path, '/login')
  assert.equal(replaced.at(-1).query.forcePasswordChange, '1')
  response = successfulResponse('COLLEGE_ADMIN'); state.$route.query = {}; await state.doLogin()
  assert.equal(pushed.at(-1), '/admin/academic-affairs', '改密后重新登录仍按服务端本次岗位进入')
})
