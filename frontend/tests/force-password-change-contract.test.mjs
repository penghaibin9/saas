import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const login = readFileSync(new URL('../src/views/LoginView.vue', import.meta.url), 'utf8')
const force = readFileSync(new URL('../src/views/ForcePasswordChangeView.vue', import.meta.url), 'utf8')

test('PC login consumes backend mustChangePassword and never enters workbench first', () => {
  assert.match(login, /data\?\.user\?\.mustChangePassword/)
  assert.match(login, /forcePasswordChange:\s*'1'/)
  const forcePos = login.indexOf('data?.user?.mustChangePassword')
  const workbenchPos = login.indexOf("redirect || '/workbench'")
  assert.ok(forcePos >= 0 && workbenchPos > forcePos)
})

test('forced password screen calls real change-password then clears the old session', () => {
  assert.match(force, /request\('\/auth\/change-password'/)
  assert.match(force, /oldPassword:/)
  assert.match(force, /newPassword:/)
  assert.match(force, /clearAuthSession\(\)/)
  assert.match(force, /router\.replace\('\/login'\)/)
  assert.doesNotMatch(force, /mock/i)
})
