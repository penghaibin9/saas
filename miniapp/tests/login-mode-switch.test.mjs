import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/components/login/MiniLoginAuthPanel.vue', import.meta.url), 'utf8')
  .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
const component = new Function(source)()

test('forced password change skips forbidden business profile loading and navigates once', () => {
  for (const isTeacher of [false, true]) {
    const calls = []
    const session = { mustChangePassword: true, login() {}, applyRealUser() {} }
    const panel = new Function('roleKeyFromBackendRole', 'useSessionStore', 'commitNewSessionTokens',
      'currentSessionGeneration', 'relaunch', 'studentApi', source)(
      () => 'student', () => session, () => 7, () => 7,
      path => calls.push(['navigate', path]),
      { getProfile() { calls.push(['profile']); throw new Error('must not request business data') } }
    )
    panel.methods.completeLogin.call({ isTeacher, isLoginCurrent: () => true, assertEntryRole: () => true },
      { currentRole: { roleCode: 'STUDENT' }, accessToken: 'unit-test-token' })
    assert.deepEqual(calls, [['navigate', isTeacher ? '/pages/teacher/workbench/index' : '/pages/student/home/index']])
  }
})

test('login initialization does not query school business data before authentication', () => {
  for (const isTeacher of [false, true]) {
    const calls = []
    const panel = new Function('createIdentityCaptcha', 'studentApi', 'toast', source)(
      () => ({ dispose() {} }),
      { getOrientationBatchStatus() { calls.push('batch-status'); return Promise.resolve({ open: false }) } },
      () => {}
    )
    const state = { isTeacher, accountCaptcha: {}, account: {} }
    panel.created.call(state)
    assert.deepEqual(calls, [])
    assert.equal(state.loginAlive, true)
    assert.ok(state.accountCaptchaFlow)
  }
})

test('login mode rejects invalid values and switching while either login is pending', () => {
  for (const flags of [{ accLoading: true }, { wxLoading: true }, {}]) {
    const state = { account: { identifierType: 'ACCOUNT' }, identifierOptions: component.computed.identifierOptions(), ...flags }
    component.methods.onIdentifierTypeChange.call(state, 'INVALID')
    assert.equal(state.account.identifierType, 'ACCOUNT')
    component.methods.onIdentifierTypeChange.call(state, 'PHONE')
    assert.equal(state.account.identifierType, flags.accLoading || flags.wxLoading ? 'ACCOUNT' : 'PHONE')
  }
})

test('changing identity mode clears both credentials and invalidates the old captcha', () => {
  let invalidated = 0
  const state = { passwordVisible: true, account: { loginName: 'test-account', password: 'test-password' }, accountCaptchaFlow: { invalidate() { invalidated++ } } }
  component.watch['account.identifierType'].handler.call(state)
  assert.equal(state.account.loginName, '')
  assert.equal(state.account.password, '')
  assert.equal(state.passwordVisible, false)
  assert.equal(invalidated, 1)
})

test('leaving the login page clears the visible password and cancels binding', () => {
  let cancelled = 0
  const state = { account: { password: 'test-only' }, passwordVisible: true, loginAlive: true, loginAttempt: 2, cancelBind() { cancelled++ } }
  component.methods.invalidateLogin.call(state)
  assert.equal(state.account.password, '')
  assert.equal(state.passwordVisible, false)
  assert.equal(state.loginAlive, false)
  assert.equal(state.loginAttempt, 3)
  assert.equal(cancelled, 1)
})

test('native login content starts below either the capsule or navigation safe area', () => {
  // Use the same H5 conditional removal as the native compilation target.
  const nativeSource = source.replace(/\s*\/\/ #ifdef H5[\s\S]*?\/\/ #endif/g, '')
  for (const scenario of [
    { status: 47, capsule: 83, expected: 93 },
    { status: 24, capsule: 0, expected: 68 },
    { status: 20, throws: true, expected: 64 }
  ]) {
    const native = new Function('uni', 'getStatusBarHeight', nativeSource)(
      { getMenuButtonBoundingClientRect() { if (scenario.throws) throw new Error('unsupported'); return { bottom: scenario.capsule } } },
      () => scenario.status
    )
    const state = {}
    native.mounted.call(state)
    assert.equal(state.heroTop, scenario.expected)
  }
})
