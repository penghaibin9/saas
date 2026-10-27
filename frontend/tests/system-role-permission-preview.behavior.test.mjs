import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import * as wc from '../src/modules/system/utils/workspaceContract.js'

const account = { key: 'systemAdmin.user.view', label: '账号管理', path: '/admin/system/accounts/staff', surfaceKey: 'accounts', children: [] }
const teaching = { key: 'academicAffairs.teachingTask.view', label: '教学任务', path: '/admin/academic-affairs/teaching-tasks', surfaceKey: 'tasks', children: [] }
const audit = { key: 'approval.todo.view', label: '我的待办', path: '/admin/approval/todos', surfaceKey: 'todo', children: [] }
const tree = children => [{ key: 'group', label: '功能', children }]
const detail = {
  id: '301', type: 'CUSTOM', version: 2, scopeCode: 'ASSIGNED',
  permissionCodes: [account.key, teaching.key],
  readOnlyPreservedPermissions: [{ permissionCode: teaching.key, label: teaching.label }]
}

test('the same role total is independent of the operator edit ceiling', () => {
  const narrow = wc.makePermissionDraft(tree([account, audit]), detail, '301')
  const broad = wc.makePermissionDraft(tree([account, teaching, audit]), detail, '301')
  assert.deepEqual(wc.rolePermissionSummary(detail, narrow, true), {
    currentTotal: 2, editableAssigned: 1, preserved: 1, selected: 1, projectedTotal: 2
  })
  assert.equal(wc.rolePermissionSummary(detail, broad, true).currentTotal, 2)
  assert.equal(wc.rolePermissionSummary(detail, broad, true).editableAssigned, 2)
  assert.equal(wc.rolePermissionSummary(detail, broad, true).preserved, 0)
})

test('full preview includes preserved menus without adding them to the write payload', () => {
  const draft = wc.makePermissionDraft(tree([account, audit]), detail, '301')
  const preview = wc.roleMenuPreview(detail, draft, true)
  assert.ok(preview.items.some(item => item.path === teaching.path))
  assert.ok(preview.items.some(item => item.path === account.path))
  const broad = wc.makePermissionDraft(tree([account, teaching]), detail, '301')
  assert.deepEqual(preview, wc.roleMenuPreview(detail, broad, true))
  const body = wc.permissionSaveArgs(draft, '核对本校角色配置', wc.newRequestId())
  assert.deepEqual(body.menuKeys, [account.key])
  assert.equal(Object.hasOwn(body, 'scopeTarget'), false)
})

test('unsaved menu changes affect the projected total and preview, not the saved total', () => {
  let draft = wc.makePermissionDraft(tree([account, audit]), detail, '301')
  draft = wc.changePermission(draft, draft.groups[0].rows[0], false)
  draft = wc.changePermission(draft, draft.groups[0].rows[1], true)
  const paths = wc.roleMenuPreview(detail, draft, true).items.map(item => item.path)
  assert.ok(paths.includes(teaching.path))
  assert.ok(paths.includes(audit.path))
  assert.ok(!paths.includes(account.path))
  assert.equal(wc.rolePermissionSummary(detail, draft, true).currentTotal, 2)
  assert.equal(wc.rolePermissionSummary(detail, draft, true).projectedTotal, 2)
  assert.deepEqual(wc.permissionDelta([account.key], draft.menuKeys), { added: [audit.key], removed: [account.key] })
  assert.deepEqual(detail.permissionCodes, [account.key, teaching.key])
})

test('readonly roles retain their complete preview and zero editable count', () => {
  const draft = wc.makeReadOnlyDraft(detail, '301')
  const summary = wc.rolePermissionSummary(detail, draft, false)
  assert.equal(summary.currentTotal, 2)
  assert.equal(summary.editableAssigned, 0)
  assert.equal(summary.preserved, 2)
  const paths = wc.roleMenuPreview(detail, draft, false).items.map(item => item.path)
  assert.ok(paths.includes(teaching.path))
  assert.ok(paths.includes(account.path))
})

test('unknown role codes are marked incomplete and missing role codes fail closed', () => {
  const draft = wc.makePermissionDraft(tree([account]), detail, '301')
  assert.throws(() => wc.roleMenuPreview({ ...detail, permissionCodes: undefined }, draft, true), /权限数据结构异常/)
  const partial = wc.roleMenuPreview({ ...detail, permissionCodes: [...detail.permissionCodes, 'historical.unknown'] }, draft, true)
  assert.equal(partial.complete, false)
  assert.equal(partial.unmappedCount, 1)
})

test('one permission can expose several real menu entries while duplicate paths appear once', () => {
  const value = { ...detail, permissionCodes: [audit.key] }
  const draft = wc.makePermissionDraft(tree([audit]), value, '301')
  const preview = wc.roleMenuPreview(value, draft, true)
  const paths = preview.items.map(item => item.path)
  assert.ok(paths.includes('/admin/approval/todos'))
  assert.ok(paths.includes('/admin/approval'))
  assert.equal(paths.length, new Set(paths).size)
  assert.ok(paths.every(path => !path.startsWith('/platform')))
  assert.equal(wc.rolePermissionSummary(value, draft, true).currentTotal, 1)
  assert.equal(preview.complete, true)
})

const source = readFileSync(new URL('../src/modules/system/components/workspace/RolePermissionPanel.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)

test('the production panel defaults to the full role preview and keeps edit-only mode separate', () => {
  const env = { wc, AppIcon: {}, AppConfirmDialog: {}, permissionDisplayLabel: v => v, systemApi: {} }
  vm.runInNewContext(descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'globalThis.component ='), env)
  const component = env.component
  const ctx = { ...component.data(), detail, draft: wc.makePermissionDraft(tree([account]), detail, '301'),
    state: 'ready', locked: false, ctx: { permissionActions: { configRolePermission: { visible: true, allowed: true } } } }
  for (const [key, value] of Object.entries(component.computed)) Object.defineProperty(ctx, key, { get: value.bind(ctx) })
  assert.equal(ctx.previewMode, 'role')
  assert.equal(ctx.permissionSummary.currentTotal, 2)
  assert.ok(ctx.previewMenus.some(item => item.path === teaching.path))
  ctx.previewMode = 'editable'
  assert.equal(ctx.previewMenus.length, 1)
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'RolePermissionPanel.vue', id: 'permission' }).errors, [])
})
