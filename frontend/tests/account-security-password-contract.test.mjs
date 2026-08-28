import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const chip = readFileSync(new URL('../src/components/common/AppUserChip.vue', import.meta.url), 'utf8')
const dialog = readFileSync(new URL('../src/components/auth/AccountSecurityDialog.vue', import.meta.url), 'utf8')
const help = readFileSync(new URL('../src/config/help/foundationHelpCards.js', import.meta.url), 'utf8')

test('authenticated staff menu exposes account security password entry', () => {
  assert.match(chip, />账号安全</)
  assert.match(chip, />修改登录密码</)
  assert.match(chip, /<AccountSecurityDialog/)
  assert.match(chip, /@changed="passwordChanged"/)
})

test('password dialog validates all three password fields before calling the real API', () => {
  assert.match(dialog, /autocomplete="current-password"/)
  assert.equal((dialog.match(/autocomplete="new-password"/g) || []).length, 2)
  assert.match(dialog, /form\.newPassword\.length < 8/)
  assert.match(dialog, /form\.newPassword === form\.oldPassword/)
  assert.match(dialog, /form\.newPassword !== form\.confirmPassword/)
  assert.match(dialog, /request\('\/auth\/change-password'/)
  assert.match(dialog, /oldPassword: form\.oldPassword/)
  assert.match(dialog, /newPassword: form\.newPassword/)
})

test('successful password change clears the old session and returns to teacher login', () => {
  assert.match(chip, /clearAuthSession\(\)/)
  assert.match(chip, /router\.replace\('\/login'\)/)
  assert.match(chip, /密码已修改，请使用新密码重新登录/)
})

test('teacher help explains both signed-in password change and no-phone recovery boundary', () => {
  assert.match(help, /右上角「账号安全」修改密码/)
  assert.match(help, /未绑定账号由本校管理员重置/)
  assert.doesNotMatch(help, /不存在尚未交付的自助短信找回流程/)
})
