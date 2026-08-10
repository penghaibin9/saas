import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const session = readFileSync(new URL('../src/stores/session.js', import.meta.url), 'utf8')
const nav = readFileSync(new URL('../src/utils/nav.js', import.meta.url), 'utf8')
const gate = readFileSync(new URL('../src/security/passwordChangeGate.js', import.meta.url), 'utf8')
const change = readFileSync(new URL('../src/pages/common/change-password/index.vue', import.meta.url), 'utf8')

test('real miniapp login persists backend mustChangePassword as navigation lock', () => {
  assert.match(session, /d\.user\s*&&\s*d\.user\.mustChangePassword/)
  assert.match(session, /setForcePasswordChange\(this\.mustChangePassword\)/)
  assert.match(session, /mustChangePassword:\s*this\.mustChangePassword/)
})

test('all shared miniapp navigation is forced into change-password while locked', () => {
  assert.match(gate, /gx_force_password_change_v1/)
  assert.match(gate, /pages\/common\/change-password\/index\?forced=1/)
  assert.match(nav, /forcePasswordChangeRequired\(\)/)
  assert.match(nav, /return FORCE_PASSWORD_CHANGE_ROUTE/)
  assert.match(nav, /url:\s*secureTarget\(url\)/)
})

test('miniapp password change clears old session and requires re-login', () => {
  assert.match(change, /changePassword\(this\.form\.oldPassword,\s*this\.form\.newPassword\)/)
  assert.match(change, /session\.logout\(\)/)
  assert.match(change, /密码修改成功，请重新登录/)
  assert.match(change, /:show-back="!forced"/)
  assert.doesNotMatch(change, /当前登录仍然有效/)
})
