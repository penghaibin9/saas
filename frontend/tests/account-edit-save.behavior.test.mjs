import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { accountDetailsChanged, roleAssignmentSignature } from '../src/modules/system/utils/accountEditChanges.js'

const source = fs.readFileSync(new URL('../src/modules/system/views/SystemUserListView.vue', import.meta.url), 'utf8')
const body = source.slice(source.indexOf('    async submitForm() {') + '    async submitForm() {'.length, source.indexOf('    async openDetail(')).replace(/\},\s*$/, '')
const createSubmit = new Function('systemApi', 'toast', 'FormFields', 'accountDetailsChanged', 'roleAssignmentSignature', `return async function () {${body}}`)
const editBody = source.slice(source.indexOf('    async openEdit(row) {') + '    async openEdit(row) {'.length, source.indexOf('    async submitForm() {')).replace(/\},\s*$/, '')
const createOpenEdit = new Function('systemApi', 'toast', `return async function (row) {${editBody}}`)
const compatibilitySource = fs.readFileSync(new URL('../src/modules/system/api/systemAuthorityCompatibility.js', import.meta.url), 'utf8')
  .replace(/^import .*\r?\n/gm, '').replace(/^export /gm, '')
const createCompatibility = new Function('request', 'toast', `${compatibilitySource}; return installSystemAuthorityCompatibility`)

function fixture({ profile = false, role = false, denied = false } = {}) {
  const calls = [], messages = []
  const original = [{ roleCode: 'SCHOOL_ADMIN', scopeType: 'SCHOOL', scopeIds: [] }]
  const ctx = {
    form: { id: '13', open: true, version: 4, value: { name: profile ? '测试修改' : '测试管理员' }, originalValue: { name: '测试管理员' },
      roleAssignments: structuredClone(original), originalRoleAssignments: structuredClone(original) },
    can: () => true, load: async () => {}, formFields: []
  }
  if (role) ctx.form.roleAssignments.push({ roleCode: 'ACADEMIC_TEACHER', scopeMode: 'AUTO', scopeType: 'ASSIGNED', scopeIds: [] })
  const api = {
    updateUser: async () => { calls.push('profile'); return { code: 0, data: { version: 5 } } },
    assignUserRoles: async () => { calls.push('roles'); return denied ? { code: 1, message: '授权范围不允许' } : { code: 0, data: { version: 5 } } }
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

test('opening account editor retains the actual detail version', async () => {
  const f = fixture()
  f.ctx.scopeOrgTree = []; f.ctx.reason = () => ''; f.ctx.isStudent = false
  f.api.getUserDetail = async () => ({ code: 0, data: { userNo: 'staff-test', name: '测试管理员', version: 7, roleAssignments: [] } })
  f.api.getDepartmentTree = async () => ({ code: 0, data: [] })
  await createOpenEdit(f.api, { error: () => {} }).call(f.ctx, { id: '13' })
  assert.equal(f.ctx.form.version, 7)
})

test('stale editor sends its read version and cannot retry over a newer role assignment', async () => {
  const f = fixture({ role: true })
  const persisted = ['COLLEGE_ADMIN']; const versions = []; let reads = 0
  f.ctx.load = async () => { reads++ }
  f.api.assignUserRoles = async (_id, roles, _scopes, { expectedVersion } = {}) => {
    versions.push(expectedVersion)
    if (expectedVersion !== undefined && expectedVersion !== 5) return { code: 409, bizCode: 'DATA_CONFLICT', message: '账号已更新' }
    persisted.splice(0, persisted.length, ...roles)
    return { code: 0, data: { version: 6 } }
  }
  await f.submit.call(f.ctx)
  assert.deepEqual(persisted, ['COLLEGE_ADMIN'])
  assert.equal(f.ctx.form.open, true)
  assert.equal(f.ctx.form.roleAssignments.length, 2)
  await f.submit.call(f.ctx)
  assert.deepEqual(versions, [4]); assert.equal(reads, 0)
  assert.match(f.messages.join(' '), /重新.*核对|重新.*打开/)
})

test('mixed save sends read version then uses the committed profile receipt version', async () => {
  const f = fixture({ profile: true, role: true })
  const writes = []
  f.api.updateUser = async (_id, payload) => { writes.push(['profile', payload.expectedVersion]); return { code: 0, data: { version: 8 } } }
  f.api.assignUserRoles = async (_id, _roles, _scopes, { expectedVersion } = {}) => { writes.push(['roles', expectedVersion]); return { code: 0, data: { version: 9 } } }
  await f.submit.call(f.ctx)
  assert.deepEqual(writes, [['profile', 4], ['roles', 8]])
})

test('partial save retries only roles with the committed profile version', async () => {
  const f = fixture({ profile: true, role: true })
  const writes = []
  f.api.updateUser = async () => { writes.push('profile'); return { code: 0, data: { version: 8 } } }
  f.api.assignUserRoles = async (_id, _roles, _scopes, { expectedVersion } = {}) => { writes.push(expectedVersion); return { code: 1, message: '暂未完成' } }
  await f.submit.call(f.ctx); await f.submit.call(f.ctx)
  assert.deepEqual(writes, ['profile', 8, 8]); assert.equal(f.ctx.form.value.name, '测试修改')
})

test('missing or invalid read version prevents role writes', async () => {
  for (const version of [undefined, null, '', '4', -1, 1.5]) {
    const f = fixture({ role: true }); f.ctx.form.version = version
    await f.submit.call(f.ctx)
    assert.deepEqual(f.calls, []); assert.equal(f.ctx.form.open, true)
  }
})

test('missing committed profile version prevents role writes and profile replay', async () => {
  const f = fixture({ profile: true, role: true })
  f.api.updateUser = async () => { f.calls.push('profile'); return { code: 0 } }
  await f.submit.call(f.ctx); await f.submit.call(f.ctx)
  assert.deepEqual(f.calls, ['profile']); assert.equal(f.ctx.form.open, true)
  assert.equal(f.ctx.form.originalValue.name, '测试修改')
})

test('actual compatibility layer honors editor version over a later account-list cache read', async () => {
  const f = fixture({ role: true }); const writes = []
  const persisted = ['COLLEGE_ADMIN']
  const api = {
    ...f.api,
    getUsers: async () => ({ code: 0, data: { list: [{ id: '13', version: 5 }] } })
  }
  for (const method of ['getContext', 'getUserDetail', 'setUserStatus', 'resetUserPassword', 'getRoles', 'getRoleDetail', 'getBrandConfig', 'saveBrandConfig', 'resetBrandConfig', 'batchDisableUsers']) {
    api[method] ||= async () => ({ code: 0, data: {} })
  }
  const request = async (_path, { body }) => {
    writes.push(body.expectedVersion)
    if (body.expectedVersion !== 5) throw Object.assign(new Error('账号已被更新'), { code: 409, bizCode: 'DATA_CONFLICT' })
    persisted.splice(0, persisted.length, ...body.roleCodes)
    return { version: 6 }
  }
  createCompatibility(request, { warning: () => {}, error: () => {} })(api)
  await api.getUsers()
  const submit = createSubmit(api, Object.fromEntries(['info', 'error', 'success'].map(k => [k, text => f.messages.push(text)])),
    { validateRequired: () => ({}) }, accountDetailsChanged, roleAssignmentSignature)
  await submit.call(f.ctx); await submit.call(f.ctx)
  assert.deepEqual(writes, [4])
  assert.deepEqual(persisted, ['COLLEGE_ADMIN'])
  assert.equal(f.ctx.form.open, true)
  assert.equal(f.ctx.form.roleAssignments.length, 2)
})
