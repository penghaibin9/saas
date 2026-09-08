import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

const source = readFileSync(new URL('../src/modules/studentAffairs/views/dorm/DormTransferView.vue', import.meta.url), 'utf8')
function createView(api) {
  const names = []
  const script = parse(source).descriptor.script.content.replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, imports) => {
    names.push(...imports.split(',').map(x => x.trim())); return ''
  }).replace('export default', 'return')
  const component = new Function(...names, script)(...names.map(n => n === 'studentAffairsApi' ? api : {}))
  const view = component.data()
  for (const [name, fn] of Object.entries(component.methods)) view[name] = fn.bind(view)
  for (const [name, fn] of Object.entries(component.computed)) Object.defineProperty(view, name, { get: fn.bind(view) })
  return view
}

test('checkout queue filters before pagination and loads only the selected workspace', async () => {
  let query
  const vm = createView({ listDormCheckouts: async q => { query = q; return { data: { items: [{ requestId: 'older-pending' }], total: 45 } } } })
  vm.activeTab = 'checkout'; vm.checkoutPagination.page = 2; vm.studentFilter.studentId = '123'
  await vm.load()
  assert.equal(vm.errorMessage, '')
  assert.deepEqual(query, { page: 2, pageSize: 20, studentId: '123', status: 'PENDING' })
  assert.equal(vm.checkoutPagination.total, 45)
  assert.equal(vm.checkoutItems[0].requestId, 'older-pending')
})

test('history supports pages beyond the first hundred and ignores stale responses', async () => {
  let resolveOld
  const vm = createView({ listDormStays: q => q.page === 1
    ? new Promise(resolve => { resolveOld = resolve })
    : Promise.resolve({ data: { items: [{ stayId: 'page-six' }], total: 130 } }) })
  vm.activeTab = 'history'
  const old = vm.load()
  vm.stayPagination.page = 6
  await vm.load()
  resolveOld({ data: { items: [{ stayId: 'stale' }], total: 1 } })
  await old
  assert.equal(vm.stayItems[0].stayId, 'page-six')
  assert.equal(vm.stayPagination.total, 130)
  assert.equal(vm.loading, false)
})
