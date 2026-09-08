import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
const source = readFileSync(new URL('../src/views/admin/orientation/OrientationNoShowView.vue', import.meta.url), 'utf8')
function createView(api) {
  const names = []
  const script = parse(source).descriptor.script.content
    .replace(/import \* as api from [^\n]+/g, '')
    .replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, list) => { names.push(...list.split(',').map(s => s.trim())); return '' })
    .replace('export default', 'return')
  const component = new Function('api', ...names, script)(api, ...names.map(() => ({})))
  const vm = component.data()
  for (const [name, fn] of Object.entries(component.methods)) vm[name] = fn.bind(vm)
  return vm
}
test('pending arrival remains enforced when the status filter is cleared', async () => {
  let params
  const vm = createView({ getOrientationStudents: async p => { params = p; return { code: 0, data: { list: [], total: 0 } } } })
  await vm.load()
  assert.equal(params.pendingArrival, true)
  assert.equal(params.reportStatus, '')
  vm.filters.reportStatus = 'PREPARED'
  vm.page = 2
  await vm.load()
  assert.equal(params.pendingArrival, true)
  assert.equal(params.reportStatus, 'PREPARED')
  assert.equal(params.page, 2)
})
test('late response cannot replace a new pending-arrival filter result', async () => {
  let resolveOld
  const vm = createView({ getOrientationStudents: p => p.reportStatus === ''
    ? new Promise(resolve => { resolveOld = resolve })
    : Promise.resolve({ code: 0, data: { list: [{ id: 'prepared' }], total: 1 } }) })
  const old = vm.load()
  vm.filters.reportStatus = 'PREPARED'
  await vm.load()
  resolveOld({ code: 0, data: { list: [{ id: 'old' }], total: 50 } })
  await old
  assert.equal(vm.rows[0].id, 'prepared')
  assert.equal(vm.total, 1)
  assert.equal(vm.loading, false)
})
