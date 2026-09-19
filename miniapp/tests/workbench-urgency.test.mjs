import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/pages/teacher/workbench/index.vue', import.meta.url), 'utf8')
const start = source.indexOf('  computed: {') + '  computed: {'.length
const end = source.indexOf('\n  onLoad()', start)
const computed = new Function(`return {${source.slice(start, end).replace(/\s*},\s*$/, '')}}`)()

function state(metrics, preview) {
  const vm = { wb: { metrics, dueSoon: preview, riskStudents: [] }, todoBadge: metrics.find(m => m.key === 'pending')?.value || 0, visibleQuickActions: [] }
  for (const [key, get] of Object.entries(computed)) Object.defineProperty(vm, key, { get: () => get.call(vm) })
  return vm
}

test('ordinary material todo is actionable without being labelled near deadline', () => {
  const vm = state([{ key: 'pending', value: 1 }, { key: 'near', value: 0 }], [{ title: '补交材料审核', deadline: '' }])
  assert.equal(vm.extraMetrics.find(m => m.key === 'near').value, 0)
  assert.equal(vm.priorityTodos.length, 1)
  assert.equal(vm.priorityTodos[0].title, '补交材料审核')
})

test('urgency uses full server totals rather than the five-row preview', () => {
  const vm = state([{ key: 'pending', value: 12 }, { key: 'near', value: 7 }, { key: 'overdue', value: 2 }], Array(5).fill({}))
  assert.equal(vm.extraMetrics.find(m => m.key === 'near').value, 7)
  assert.equal(vm.extraMetrics.find(m => m.key === 'overdue').value, 2)
  assert.equal(vm.priorityTodos.length, 2)
})
