import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

const batchId = '1000000000000000907'
const fixedBatch = { id: batchId, batchName: '迎新测试批次', batchNo: 'ROSTER-TEST', status: 'ACTIVE' }

test('batch workspace import validation forwards the same batch to the server', async () => {
  const calls = []
  const { vm } = mount('OrientationStudentListView', { validateImport: async (...args) => { calls.push(args); return { code: 0 } } }, { fixedBatch })
  const file = { name: 'new-students.xlsx' }
  await vm.validateImportFn(file)
  assert.deepEqual(calls, [['studentList', file, batchId]])
})

function mount(name, api = {}, props = {}) {
  const source = readFileSync(new URL(`../src/views/admin/orientation/${name}.vue`, import.meta.url), 'utf8')
  const imports = []
  const script = parse(source).descriptor.script.content
    .replace(/import \* as api from [^\n]+/g, '')
    .replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, names) => {
      imports.push(...names.split(',').map(name => name.trim())); return ''
    })
    .replace(/import\s+(\w+)\s+from\s+['"][^'"]+['"]/g, (_, name) => {
      imports.push(name); return ''
    })
    .replace('export default', 'return')
  const messages = []
  const component = new Function('api', ...imports, script)(api, ...imports.map(name => name === 'toast'
    ? { success(message) { messages.push(message) }, error(message) { messages.push(message) } } : {}))
  const destinations = []
  const vm = {
    ...component.data(), fixedBatch: null,
    $route: { query: {} },
    $router: { push(destination) { destinations.push(destination) } },
    ...props
  }
  for (const [name, fn] of Object.entries(component.methods)) vm[name] = fn.bind(vm)
  for (const [name, fn] of Object.entries(component.computed || {})) {
    Object.defineProperty(vm, name, { get: () => fn.call(vm), configurable: true })
  }
  return { vm, component, destinations, messages }
}

test('batch roster entry preserves an exact large ID and uses the batch workspace', () => {
  const { vm, destinations } = mount('OrientationBatchListView')
  vm.onRowAction('students', fixedBatch)
  assert.deepEqual(destinations, [{ path: '/admin/orientation/batches', query: { batchId, panel: 'students' } }])
  vm.$route.query = destinations[0].query
  assert.equal(vm.rosterBatchId, batchId)
  vm.$route.query = { batchId, panel: 'settings' }
  assert.equal(vm.rosterBatchId, '')
})

test('successful new batch creation opens its returned ID rather than an existing batch', async () => {
  const submitted = []
  const { vm, destinations } = mount('OrientationBatchListView', {
    createOrientationBatch: async form => { submitted.push(form); return { code: 0, data: fixedBatch } }
  })
  const form = { batchName: '新的迎新批次', batchNo: 'NEW-ROSTER' }
  vm.openCreate()
  await vm.onEditSubmit(form)
  assert.deepEqual(submitted, [form])
  assert.equal(vm.editVisible, false)
  assert.equal(vm.submitting, false)
  assert.deepEqual(destinations, [{ path: '/admin/orientation/batches', query: { batchId, panel: 'students' } }])
})

test('an active empty batch adopts the latest flow with its server version and blocks duplicate clicks', async () => {
  const writes = []
  let finish
  const row = { ...fixedBatch, version: 4 }
  const { vm } = mount('OrientationBatchListView', {
    refreshOrientationBatchFlow: (id, version) => {
      writes.push({ id, version })
      return new Promise(resolve => { finish = resolve })
    },
    getOrientationBatches: async () => ({ code: 0, data: { list: [row], total: 1 } })
  })
  assert.equal(vm.rowActions(row).find(action => action.key === 'refreshFlow').disabled, false)
  vm.onRowAction('refreshFlow', row)
  const first = vm.onConfirm()
  await vm.onConfirm()
  assert.deepEqual(writes, [{ id: batchId, version: 4 }])
  assert.equal(vm.confirmSubmitting, true)
  finish({ code: 0, data: { changed: true, version: 5 } })
  await first
  assert.equal(vm.confirmSubmitting, false)
  assert.equal(vm.confirmVisible, false)
})

test('draft and closed batches explain why their frozen flow cannot be refreshed here', () => {
  const { vm } = mount('OrientationBatchListView')
  const draft = vm.rowActions({ status: 'DRAFT' }).find(action => action.key === 'refreshFlow')
  const closed = vm.rowActions({ status: 'CLOSED' }).find(action => action.key === 'refreshFlow')
  assert.equal(draft.disabled, true)
  assert.match(draft.disabledReason, /启用时会自动采用最新流程/)
  assert.equal(closed.disabled, true)
  assert.match(closed.disabledReason, /保持原冻结流程/)
})

test('failed batch creation keeps the form open and never enters a roster', async () => {
  const { vm, destinations, messages } = mount('OrientationBatchListView', {
    createOrientationBatch: async () => ({ code: 1, message: '批次编号已存在' })
  })
  vm.openCreate()
  await vm.onEditSubmit({ batchNo: 'EXISTING' })
  assert.equal(vm.editVisible, true)
  assert.equal(vm.submitting, false)
  assert.deepEqual(destinations, [])
  assert.deepEqual(messages, ['批次编号已存在'])
})

test('fixed-batch roster reset keeps its ID, clears filters and requests the first page', async () => {
  const requests = []
  const { vm } = mount('OrientationStudentListView', {
    getOrientationStudents: async params => { requests.push(params); return { code: 0, data: { list: [], total: 0 } } }
  }, { fixedBatch })
  vm.batches = [{ id: 'wrong-active-batch', status: 'ACTIVE' }]
  vm.filters = { ...vm.filters, batchId: 'wrong-active-batch', keyword: '旧筛选', classId: 'old-class' }
  vm.page = 8
  vm.reset()
  assert.equal(vm.filters.batchId, batchId)
  assert.equal(vm.filters.keyword, '')
  assert.equal(vm.page, 1)
  assert.equal(requests.length, 1)
  assert.equal(requests[0].batchId, batchId)
  assert.equal(requests[0].page, 1)
  await Promise.resolve()
  assert.equal(vm.loading, false)
})

test('fixed-batch list query overrides a stale filter while preserving server pagination', async () => {
  const requests = []
  const { vm } = mount('OrientationStudentListView', {
    getOrientationStudents: async params => { requests.push(params); return { code: 0, data: { list: [{ id: 'current-student' }], total: 24 } } }
  }, { fixedBatch })
  vm.filters.batchId = 'stale-filter'
  vm.filters.keyword = '本批次学生'
  vm.page = 2
  await vm.load()
  assert.equal(requests[0].batchId, batchId)
  assert.equal(requests[0].page, 2)
  assert.equal(requests[0].pageSize, 10)
  assert.equal(requests[0].keyword, '本批次学生')
  assert.deepEqual(vm.rows, [{ id: 'current-student' }])
  assert.equal(vm.total, 24)
})

test('fixed-batch student creation enforces its ID, prevents double click and reads server results', async () => {
  const writes = []
  const reads = []
  let finish
  const { vm } = mount('OrientationStudentListView', {
    createOrientationStudent: body => { writes.push(body); return new Promise(resolve => { finish = resolve }) },
    getOrientationStudents: async params => { reads.push(params); return { code: 0, data: { list: [{ id: 'created' }], total: 1 } } }
  }, { fixedBatch })
  vm.editVisible = true
  const form = { name: '测试新生', admissionNo: 'ROSTER-001', batchId: 'stale-form-batch', classId: 'test-class' }
  const first = vm.onEditSubmit(form)
  await vm.onEditSubmit(form)
  assert.equal(writes.length, 1)
  assert.equal(writes[0].batchId, batchId)
  assert.equal(writes[0].classId, 'test-class')
  assert.equal(form.batchId, 'stale-form-batch')
  assert.equal(vm.submitting, true)
  assert.equal(vm.editVisible, true)
  finish({ code: 0, data: { id: 'created' } })
  await first
  assert.equal(vm.submitting, false)
  assert.equal(vm.editVisible, false)
  assert.equal(reads.length, 1)
  assert.equal(reads[0].batchId, batchId)
  assert.deepEqual(vm.rows, [{ id: 'created' }])
})

test('fixed batch hides the redundant selector, locks the create field and preserves detail context', () => {
  const { vm, destinations } = mount('OrientationStudentListView', {}, { fixedBatch })
  vm.batches = [fixedBatch]
  vm.filters.batchId = batchId
  assert.equal(vm.filterFields.some(field => field.key === 'batchId'), false)
  assert.equal(vm.editFields.find(field => field.key === 'batchId').disabled, true)
  vm.viewDetail({ id: '1000000000000000987' })
  assert.deepEqual(destinations, [{ path: '/admin/orientation/students/1000000000000000987', query: { batchId, from: 'batch' } }])
})
