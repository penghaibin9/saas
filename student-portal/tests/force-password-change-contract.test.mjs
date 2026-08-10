import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const session = readFileSync(new URL('../src/stores/session.js', import.meta.url), 'utf8')
const cfg = readFileSync(new URL('../src/stores/portalConfig.js', import.meta.url), 'utf8')
const router = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const guard = readFileSync(new URL('../src/platform/permissionGuard.js', import.meta.url), 'utf8')
const force = readFileSync(new URL('../src/views/login/ForcePasswordChangeView.vue', import.meta.url), 'utf8')

test('student login keeps backend mustChangePassword in reactive session', () => {
  assert.match(session, /mustChangePassword:\s*!!u\.mustChangePassword/)
})

test('student portal does not call business config before required password change', () => {
  assert.match(cfg, /session\.user\?\.mustChangePassword/)
  const lockPos = cfg.indexOf('session.user?.mustChangePassword')
  const apiPos = cfg.indexOf('portalApi.portalConfig()')
  assert.ok(lockPos >= 0 && apiPos > lockPos)
})

test('student router forces all authenticated business navigation into recovery page', () => {
  assert.match(router, /path:\s*'\/force-password-change'/)
  assert.match(guard, /session\.user\?\.mustChangePassword/)
  assert.match(guard, /name:\s*'force-password-change'/)
  const passwordGate = guard.indexOf('session.user?.mustChangePassword')
  const configLoad = guard.indexOf('await cfg.load()')
  assert.ok(passwordGate >= 0 && configLoad > passwordGate)
})

test('student forced-password page uses real API then destroys old session', () => {
  assert.match(force, /request\('\/auth\/change-password'/)
  assert.match(force, /session\.logout\(\)/)
  assert.match(force, /router\.replace\('\/login'\)/)
  assert.doesNotMatch(force, /mock/i)
})
