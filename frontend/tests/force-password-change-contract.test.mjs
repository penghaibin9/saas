import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const login = readFileSync(new URL('../src/views/LoginView.vue', import.meta.url), 'utf8')
const platformLogin = readFileSync(new URL('../src/views/PlatformLoginView.vue', import.meta.url), 'utf8')
const force = readFileSync(new URL('../src/views/ForcePasswordChangeView.vue', import.meta.url), 'utf8')

test('school PC login consumes backend mustChangePassword before entering workbench', () => {
  assert.match(login, /data\?\.user\?\.mustChangePassword/)
  assert.match(login, /forcePasswordChange:\s*'1'/)
  const forcePos = login.indexOf('data?.user?.mustChangePassword')
  const workbenchPos = login.indexOf("redirect || '/workbench'")
  assert.ok(forcePos >= 0 && workbenchPos > forcePos)
})

test('platform PC login consumes backend mustChangePassword before control plane', () => {
  assert.match(platformLogin, /data\?\.user\?\.mustChangePassword/)
  assert.match(platformLogin, /forcePasswordChange:\s*'1'/)
  assert.match(platformLogin, /login-route="\/platform-login"/)
  const forcePos = platformLogin.indexOf('data?.user?.mustChangePassword')
  const overviewPos = platformLogin.indexOf("'/admin/platform/overview'")
  assert.ok(forcePos >= 0 && overviewPos > forcePos)
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
