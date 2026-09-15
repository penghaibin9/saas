import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

function setup(api) {
  const names = []
  const source = parse(readFileSync(new URL('../src/views/admin/orientation/OrientationFlowConfigView.vue', import.meta.url), 'utf8')).descriptor.script.content
    .replace(/import \* as api from [^\n]+/g, '')
    .replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, list) => { names.push(...list.split(',').map(v => v.trim())); return '' })
    .replace('export default', 'return')
  const errors = []
  const component = new Function('api', ...names, source)(api, ...names.map(n => n === 'toast' ? { success() {}, error(v) { errors.push(v) } } : {}))
  const vm = component.data()
  for (const [key, fn] of Object.entries(component.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(component.computed)) Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, errors }
}
const context = { permissionActions: { 'orientation.student.view': { allowed: true }, 'orientation.student.edit': { allowed: true } } }
test('flow sequence uses display position without rewriting sort weights or missing configurations', async () => {
  const rows = [{ id: '38', stepKey: 'IDENTITY', sortOrder: 10 }, { id: '39', stepKey: 'DORM', sortOrder: 20 }, { id: '40', stepKey: 'FINANCE', sortOrder: 30 }]
  const { vm } = setup({ getOrientationContext: async () => ({ code: 0, data: context }), getFlowConfig: async () => ({ code: 0, data: rows }) })
  await vm.load()
  assert.deepEqual(vm.rows.map(r => r.displayOrder), [1, 2, 3])
  assert.deepEqual(vm.rows.map(r => r.sortOrder), [10, 20, 30])
  assert.equal(rows[0].displayOrder, undefined)
  assert.equal(vm.hasLegacySteps, true)
})
test('flow context failure stops requests and clears stale configuration', async () => {
  let requests = 0
  const { vm } = setup({ getOrientationContext: async () => ({ code: 1, message: '会话失效' }), getFlowConfig: async () => { requests++ } })
  vm.rows = [{ id: 'old' }];await vm.load()
  assert.equal(requests, 0);assert.deepEqual(vm.rows, []);assert.equal(vm.error, '会话失效');assert.equal(vm.loading, false)
})
test('flow update prevents double click and preserves state on a failed request', async () => {
  let reject, calls = 0
  const { vm, errors } = setup({ updateFlowConfig: () => { calls++;return new Promise((_, fail) => { reject = fail }) } })
  vm.ctx = context
  const row = { id: '38', enabled: true };vm.rows = [row]
  const first = vm.onRowAction('toggleEnabled', row)
  await vm.onRowAction('toggleEnabled', row)
  assert.equal(calls, 1);assert.equal(vm.rowActions(row)[0].disabled, true)
  reject(new Error('连接失败'));await first
  assert.equal(row.enabled, true);assert.equal(vm.submitting, false);assert.deepEqual(errors, ['连接失败'])
})
test('standard completion keeps the dialog open while pending, blocks duplicates and trusts server readback', async () => {
  let finish, calls = 0
  const { vm } = setup({ completeStandardFlowConfig: () => { calls++; return new Promise(resolve => { finish = resolve }) } })
  vm.ctx = context
  vm.rows = [{ id: '38', stepKey: 'IDENTITY', sortOrder: 10 }, { id: '39', stepKey: 'DORM', sortOrder: 20 }]
  vm.restoreVisible = true
  const first = vm.completeStandard()
  await vm.completeStandard()
  assert.equal(calls, 1);assert.equal(vm.restoreSubmitting, true);assert.equal(vm.restoreVisible, true)
  const items = [{ id: '41', stepKey: 'ACTIVATE', sortOrder: 10 }, { id: '42', stepKey: 'INFO', sortOrder: 20 }, { id: '39', stepKey: 'DORM', sortOrder: 30 }]
  finish({ code: 0, data: { addedCount: 5, restoredCount: 0, items } })
  await first
  assert.equal(vm.restoreSubmitting, false);assert.equal(vm.restoreVisible, false)
  assert.deepEqual(vm.rows.map(row => row.displayOrder), [1, 2, 3])
  assert.deepEqual(vm.rows.map(row => row.stepKey), items.map(row => row.stepKey))
})
test('legacy aliases are labelled and cannot be re-enabled from the page', () => {
  const { vm } = setup({})
  vm.ctx = context
  const legacy = { stepKey: 'IDENTITY', enabled: false, required: true }
  const standard = { stepKey: 'INFO', enabled: true, required: true }
  assert.equal(vm.isLegacy(legacy), true)
  assert.equal(vm.rowActions(legacy).every(action => action.disabled), true)
  assert.equal(vm.rowActions(standard).every(action => !action.disabled), true)
})
