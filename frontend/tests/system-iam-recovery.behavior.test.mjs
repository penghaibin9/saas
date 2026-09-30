import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { setImmediate } from 'node:timers'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import * as contract from '../src/modules/system/utils/workspaceContract.js'

const source = readFileSync(new URL('../src/modules/system/components/workspace/SystemIamGovernancePanel.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const ok = data => ({ code: 0, data })
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function panel(api = {}) {
  const sandbox = { ...contract, AppButton: {}, ModulePageShell: {}, roleDisplayLabel: code => code,
    permissionDisplayLabel: code => code, presentAuditRecord: v => v, toast: { error() {} },
    schoolIamApi: { summary: async () => ok({ roleCount: 27, memberCount: 200 }),
      permissionCatalog: async () => ok({ customRoleAssignablePermissions: [] }),
      roleTemplates: async () => ok({ items: [] }), ...api } }
  vm.runInNewContext(descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'globalThis.component ='), sandbox)
  const component = sandbox.component
  const ctx = { ...component.data(), ctx: {}, $route: { query: {} }, $nextTick: cb => cb() }
  for (const [key, value] of Object.entries(component.methods)) ctx[key] = value.bind(ctx)
  for (const [key, value] of Object.entries(component.computed)) Object.defineProperty(ctx, key, { get: value.bind(ctx) })
  ctx.fence = contract.createRequestFence()
  return { ctx, component }
}

test('IAM template compiles with independent loading and error branches', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'Iam.vue', id: 'iam' }).errors, [])
})
test('template failure leaves real permission catalog and summary available', async () => {
  const { ctx } = panel({ roleTemplates: async () => ({ code: 409, message: '模板待修复' }) })
  await ctx.load()
  assert.equal(ctx.sections.catalog.state, 'ready')
  assert.equal(ctx.sections.summary.state, 'ready')
  assert.equal(ctx.sections.templates.state, 'error')
  assert.equal(ctx.metric('summary', ctx.summary.roleCount), '27')
  assert.equal(ctx.loading, false)
})
test('summary failure is unknown, never zero; successful regions render before slow requests', async () => {
  const slow = deferred()
  const { ctx } = panel({ summary: async () => { throw new Error('网络中断') }, roleTemplates: () => slow.promise })
  const pending = ctx.load()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(ctx.sections.catalog.state, 'ready')
  assert.equal(ctx.metric('summary', ctx.summary.roleCount), '未取得')
  slow.resolve(ok({ items: [] })); await pending
  assert.equal(ctx.sections.templates.state, 'ready')
})
test('targeted retry only reloads its failed section and clears old values', async () => {
  let calls = 0
  const { ctx } = panel({ summary: async () => { calls++; return ok({ roleCount: 27 }) } })
  await ctx.load()
  await ctx.loadSection('templates')
  assert.equal(calls, 1)
  assert.equal(ctx.summary.roleCount, 27)
})
test('new school context and unmount reject all late responses', async () => {
  const old = deferred()
  const { ctx, component } = panel({ summary: () => old.promise })
  const pending = ctx.loadSection('summary')
  component.beforeUnmount.call(ctx)
  ctx.summary = { roleCount: 5 }
  old.resolve(ok({ roleCount: 99 })); await pending
  assert.equal(ctx.summary.roleCount, 5)
})
test('malformed catalog remains an error, not an empty permission success', async () => {
  const { ctx } = panel({ permissionCatalog: async () => ok({}) })
  await ctx.loadSection('catalog')
  assert.equal(ctx.sections.catalog.state, 'error')
})
test('access explanation preserves large member IDs as strings', async () => {
  let received
  const { ctx } = panel({ accessExplain: async id => { received = id; return ok({ allowed: false }) } })
  Object.assign(ctx.explain, { userId: '1000000000000000007', scopeTargetId: '1', resourceId: '2' })
  await ctx.explainAccess()
  assert.equal(received, '1000000000000000007')
})
