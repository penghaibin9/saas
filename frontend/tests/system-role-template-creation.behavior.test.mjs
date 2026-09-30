import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import * as wc from '../src/modules/system/utils/workspaceContract.js'
import { presentAuditRecord } from '../src/utils/presentationSafety.js'

const source = readFileSync(new URL('../src/modules/system/views/SystemRoleListView.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const template = { id: '71', templateCode: 'STAFF', templateVersion: 3, permissionDigest: 'digest', permissions: ['x.view'] }
function view(items = [template], create = async () => ({ code: 0, data: { id: '99', initialPermissionCount: 1 } })) {
  const env = { wc, AppIcon: {}, SystemWorkspaceFrame: {}, RolePermissionPanel: {}, RoleMembersPanel: {}, RoleTemplatesPanel: {}, AppConfirmDialog: {}, roleDisplayLabel: v => v,
    systemApi: { createRole: create }, schoolIamApi: { roleTemplates: async () => ({ code: 0, data: { items } }) }, systemConfirm: async () => true }
  vm.runInNewContext(descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'globalThis.component ='), env)
  const component = env.component
  const ctx = { ...component.data(), ctx: {}, surface: 'roles', $route: { path: '/admin/system/iam', query: {} } }
  for (const [key, value] of Object.entries(component.methods)) ctx[key] = value.bind(ctx)
  for (const [key, value] of Object.entries(component.computed)) Object.defineProperty(ctx, key, { get: value.bind(ctx) })
  ctx.fence = wc.createRequestFence(); ctx.can = () => true; ctx.loadRoles = async () => {}; ctx.openRole = () => {}
  return ctx
}
test('role creation template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'Roles.vue', id: 'roles' }).errors, [])
})
test('template creation submits reviewed version and digest, not a client permission list', async () => {
  let request
  const ctx = view([template], async body => { request = body; return { code: 0, data: { id: '99', initialPermissionCount: 1 } } })
  await ctx.openCreate('STAFF'); ctx.form.name = '本校岗位'
  await ctx.saveForm()
  assert.equal(request.initialPermissions, 'TEMPLATE')
  assert.equal(request.expectedTemplateVersion, 3)
  assert.equal(request.expectedTemplateDigest, 'digest')
  assert.equal(request.permissionCodes, undefined)
  assert.match(ctx.flash, /带入 1 项权限/)
})
test('empty role is an explicit choice', async () => {
  let request
  const ctx = view([template], async body => { request = body; return { code: 0, data: { id: '99', initialPermissionCount: 0 } } })
  await ctx.openCreate('STAFF'); ctx.form.name = '本校岗位'; ctx.form.initialPermissions = 'EMPTY'
  await ctx.saveForm()
  assert.equal(request.initialPermissions, 'EMPTY')
})
test('template conflict preserves user input and prevents duplicate creation', async () => {
  let calls = 0
  const ctx = view([template], async () => { calls++; throw new Error('来源模板已变化') })
  await ctx.openCreate('STAFF'); ctx.form.name = '本校岗位'
  await ctx.saveForm(); await ctx.saveForm()
  assert.equal(ctx.form.name, '本校岗位'); assert.equal(ctx.mutationBlocked, true); assert.equal(calls, 1)
})
test('incomplete templates cannot be offered as ready snapshots', async () => {
  const ctx = view([{ ...template, permissionDigest: '' }])
  await ctx.openCreate('STAFF')
  assert.equal(ctx.sourceTemplates.length, 0); assert.match(ctx.formError, /权限不完整/)
})
test('role audit names identify the actual school operation', () => {
  assert.equal(presentAuditRecord({ action: 'ROLE_CREATE' }).displayAction, '创建本校角色')
  assert.equal(presentAuditRecord({ action: 'ROLE_PERMISSION_SAVE' }).displayAction, '修改角色权限')
})
