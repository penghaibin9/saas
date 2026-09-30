import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import * as wc from '../src/modules/system/utils/workspaceContract.js'

const source = readFileSync(new URL('../src/modules/system/components/workspace/RolePermissionPanel.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
function view(write = async () => ({ code: 0, data: { id: '81', version: 5, type: 'CUSTOM', cacheInvalidated: true } })) {
  const env = { wc, AppIcon: {}, AppConfirmDialog: {}, permissionDisplayLabel: v => v, systemApi: { adoptRole: write } }
  vm.runInNewContext(descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'globalThis.component ='), env)
  const c = env.component
  const ctx = { ...c.data(), roleId: '81', locked: false, ctx: { permissionActions: { configRolePermission: { visible: true, allowed: true } } }, $emit() {} }
  for (const [key, value] of Object.entries(c.methods)) ctx[key] = value.bind(ctx)
  for (const [key, value] of Object.entries(c.computed)) Object.defineProperty(ctx, key, { get: value.bind(ctx) })
  ctx.state = 'ready'; ctx.fence = wc.createRequestFence(); ctx.load = async () => { ctx.reloaded = true }
  ctx.detail = { type: 'BUILTIN', localAdoption: { eligible: true, expectedVersion: 4, expectedTemplateVersion: 3, expectedTemplateDigest: 'digest' } }
  return ctx
}

test('adoption dialog compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'Permission.vue', id: 'permission' }).errors, [])
})

test('adoption sends only reviewed snapshot and reloads the same role', async () => {
  let request
  const ctx = view(async (id, body) => { request = { id, body }; return { code: 0, data: { id, version: 5, type: 'CUSTOM', cacheInvalidated: true } } })
  await ctx.adopt({ reason: '本校自行管理此角色' })
  assert.equal(request.id, '81')
  assert.equal(request.body.expectedVersion, 4)
  assert.equal(request.body.expectedTemplateVersion, 3)
  assert.equal(request.body.expectedTemplateDigest, 'digest')
  assert.equal(request.body.permissionCodes, undefined)
  assert.equal(ctx.reloaded, true)
  assert.equal(ctx.receipt.kind, 'success')
})

test('protected, readonly and context-locked roles cannot submit adoption', async () => {
  let calls = 0
  const ctx = view(async () => { calls++ })
  ctx.detail.localAdoption.eligible = false; await ctx.adopt({ reason: '本校自行管理此角色' })
  ctx.detail.localAdoption.eligible = true; ctx.locked = true; await ctx.adopt({ reason: '本校自行管理此角色' })
  ctx.locked = false; ctx.ctx.permissionActions.configRolePermission.allowed = false; await ctx.adopt({ reason: '本校自行管理此角色' })
  assert.equal(calls, 0)
})

test('failed or ambiguous write prevents repeats until reread', async () => {
  let calls = 0
  const ctx = view(async () => { calls++; throw new Error('角色版本已变化') })
  await ctx.adopt({ reason: '本校自行管理此角色' }); await ctx.adopt({ reason: '本校自行管理此角色' })
  assert.equal(calls, 1); assert.equal(ctx.outcomeUnknown, true)
  assert.match(ctx.error, /版本已变化/)
})

test('late adoption response is discarded after context invalidation', async () => {
  let resolve
  const ctx = view(() => new Promise(r => { resolve = r }))
  const pending = ctx.adopt({ reason: '本校自行管理此角色' })
  ctx.fence.invalidate(); ctx.clear()
  resolve({ code: 0, data: { id: '81', type: 'CUSTOM', version: 5 } }); await pending
  assert.equal(ctx.receipt, null); assert.equal(ctx.reloaded, undefined)
})

test('post-commit cache failure shows warning without repeating mutation', async () => {
  const ctx = view(async () => ({ code: 0, data: { id: '81', type: 'CUSTOM', version: 5, cacheInvalidated: false } }))
  await ctx.adopt({ reason: '本校自行管理此角色' })
  assert.equal(ctx.receipt.kind, 'warning'); assert.equal(ctx.reloaded, true)
})
