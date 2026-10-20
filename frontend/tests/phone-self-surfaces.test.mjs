import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

test('staff, student PC and both-role mini security entry surfaces compile', () => {
  for (const file of ['frontend/src/components/auth/PhoneBindingPanel.vue', 'frontend/src/components/auth/AccountSecurityDialog.vue',
    'student-portal/src/views/profile/AccountSecurityView.vue', 'student-portal/src/views/profile/ProfileView.vue',
    'student-portal/src/layouts/PortalLayout.vue', 'miniapp/src/components/auth/PhoneBindingPanel.vue',
    'miniapp/src/pages/common/account-security/index.vue', 'miniapp/src/pages/login/reset/index.vue',
    'frontend/src/components/auth/PasswordResetDialog.vue', 'student-portal/src/components/auth/PasswordResetDialog.vue']) {
    const { descriptor, errors } = parse(readFileSync(new URL('../../' + file, import.meta.url), 'utf8'))
    assert.deepEqual(errors, [], file); compileScript(descriptor, { id: file })
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: file, id: file }).errors, [], file)
  }
})
