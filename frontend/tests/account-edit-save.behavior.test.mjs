import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { accountDetailsChanged, roleAssignmentSignature } from '../src/modules/system/utils/accountEditChanges.js'

const source = fs.readFileSync(new URL('../src/modules/system/views/SystemUserListView.vue', import.meta.url), 'utf8')
const body = source.slice(source.indexOf('    async submitForm() {') + '    async submitForm() {'.length, source.indexOf('    async openDetail(')).replace(/\},\s*$/, '')
const createSubmit = new Function('systemApi', 'toast', 'FormFields', 'accountDetailsChanged', 'roleAssignmentSignature', `return async function () {${body}}`)

function fixture({ profile = false, role = false, denied = false } = {}) {
  const calls = [], messages = []
  const original = [{ roleCode: 'SCHOOL_ADMIN', scopeType: 'SCHOOL', scopeIds: [] }]
  const ctx = {
    form: { id: '13', open: true, value: { name: profile ? '测试修改' : '测试管理员' }, originalValue: { name: '测试管理员' },
      roleAssignments: structuredClone(original), originalRoleAssignments: structuredClone(original) },
    can: () => true, load: async () => {}, formFields: []
  }
  if (role) ctx.form.roleAssignments.push({ roleCode: 'ACADEMIC_TEACHER', scopeMode: 'AUTO', scopeType: 'ASSIGNED', scopeIds: [] })
  const api = {
    updateUser: async () => { calls.push('profile'); return { code: 0 } },
    assignUserRoles: async () => { calls.push('roles'); return denied ? { code: 1, message: '授权范围不允许' } : { code: 0 } }
  }
  const toast = Object.fromEntries(['info', 'error', 'success'].map(k => [k, text => messages.push(text)]))
  return { ctx, api, calls, messages, submit: createSubmit(api, toast, { validateRequired: () => ({}) }, accountDetailsChanged, roleAssignmentSignature) }
}

test('saving unchanged administrator never rewrites the account or grants roles', async () => {
  const f = fixture(); await f.submit.call(f.ctx)
  assert.deepEqual(f.calls, []); assert.match(f.messages[0], /未修改/)
})
test('profile-only editing never reauthorizes existing administrator role', async () => {
  const f = fixture({ profile: true }); await f.submit.call(f.ctx)
  assert.deepEqual(f.calls, ['profile']); assert.equal(f.ctx.form.open, false)
})
test('role-only editing avoids changing the account version before role assignment', async () => {
  const f = fixture({ role: true }); await f.submit.call(f.ctx)
  assert.deepEqual(f.calls, ['roles'])
})
test('retry after partial save preserves input and does not replay committed profile', async () => {
  const f = fixture({ profile: true, role: true, denied: true }); await f.submit.call(f.ctx)
  assert.equal(f.ctx.form.open, true); assert.equal(f.ctx.form.value.name, '测试修改')
  await f.submit.call(f.ctx)
  assert.deepEqual(f.calls, ['profile', 'roles', 'roles']); assert.equal(f.ctx.form.submitting, false)
})
test('in-flight save cannot be submitted twice', async () => {
  const f = fixture({ profile: true }); f.ctx.form.submitting = true
  await f.submit.call(f.ctx); assert.deepEqual(f.calls, [])
})
test('role order and scope ID representation are not authorization changes', () => {
  assert.equal(roleAssignmentSignature([{ roleCode: 'A', scopeType: 'CLASS', scopeIds: [2, 1] }]),
    roleAssignmentSignature([{ roleCode: 'A', scopeType: 'CLASS', scopeIds: ['1', '2'], roleName: '老师' }]))
})
