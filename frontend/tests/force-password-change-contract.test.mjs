import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const login = readFileSync(new URL('../src/views/LoginView.vue', import.meta.url), 'utf8')
const platformLogin = readFileSync(new URL('../src/views/PlatformLoginView.vue', import.meta.url), 'utf8')
const platformGate = readFileSync(new URL('../src/security/platformAccessGate.js', import.meta.url), 'utf8')
const force = readFileSync(new URL('../src/views/ForcePasswordChangeView.vue', import.meta.url), 'utf8')

test('school PC login consumes backend mustChangePassword before entering workbench', () => {
  assert.match(login, /data\?\.user\?\.mustChangePassword/)
  assert.match(login, /forcePasswordChange:\s*'1'/)
  const forcePos = login.indexOf('data?.user?.mustChangePassword')
  const workbenchPos = login.indexOf("redirect || '/workbench'")
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
