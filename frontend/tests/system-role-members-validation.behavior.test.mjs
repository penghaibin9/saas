import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { parse, compileTemplate } from '@vue/compiler-sfc'

const { descriptor } = parse(readFileSync(new URL('../src/modules/system/components/workspace/RoleMembersPanel.vue', import.meta.url), 'utf8'))
function panel() {
  const calls = []
  const env = { schoolIamApi: { batchAddRoleMembers: async (id, payload) => { calls.push({ id, payload }); return { addedCount: 1, skippedCount: 0 } } }, presentAuditRecord: value => value,
    wc: { actionAllowed: () => true, unwrap: value => value, contextFingerprint: () => 'school' }, systemConfirm: async () => true }
  vm.runInNewContext(descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'globalThis.component ='), env)
  const component = env.component
  const focused = []
  const ctx = { ...component.data(), ctx: {}, roleId: '109', locked: false, $emit() {}, $nextTick: async () => {},
    $refs: Object.fromEntries(['reasonInput', 'expiryInput'].map(field => [field, { focus: () => focused.push(field), scrollIntoView() {} }])) }
  for (const [key, method] of Object.entries(component.methods)) ctx[key] = method.bind(ctx)
  for (const [key, method] of Object.entries(component.computed)) Object.defineProperty(ctx, key, { get: method.bind(ctx) })
  ctx.fence = { start: () => () => true }
  ctx.loadMembers = async () => true
  ctx.selected = [{ id: '9007199254740999', name: '测试老师' }]; ctx.adding = true
  return { ctx, calls, focused }
}

test('member form compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'RoleMembersPanel.vue', id: 'members' }).errors, [])
})
test('missing reason focuses the required input and preserves selected teachers without a request', async () => {
  const { ctx, calls, focused } = panel()
  await ctx.submit()
  assert.equal(calls.length, 0); assert.equal(ctx.selected.length, 1)
  assert.match(ctx.validationError, /至少 5 个字/); assert.deepEqual(focused, ['reasonInput'])
  ctx.clearValidation('reasonInput'); assert.equal(ctx.validationError, '')
})
test('expired date focuses its field and preserves reason and selection', async () => {
  const { ctx, calls, focused } = panel()
  ctx.reason = '负责本学期教务管理'; ctx.expiresAt = '2000-01-01'
  await ctx.submit()
  assert.equal(calls.length, 0); assert.deepEqual(focused, ['expiryInput'])
  assert.equal(ctx.reason, '负责本学期教务管理'); assert.equal(ctx.selected.length, 1)
})
test('valid reason submits unchanged permission contract and string IDs', async () => {
  const { ctx, calls } = panel()
  ctx.reason = '  负责本学期教务管理  '
  await ctx.submit()
  assert.equal(calls.length, 1); assert.equal(calls[0].payload.userIds[0], '9007199254740999')
  assert.equal(calls[0].payload.reason, '负责本学期教务管理'); assert.equal(calls[0].payload.expiresAt, null)
  assert.equal(calls[0].payload.permissionCodes, undefined); assert.equal(ctx.adding, false)
})
