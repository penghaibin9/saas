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
    $router: { push(destination) { destinations.push(destination) }, async replace(destination) { destinations.push(destination); vm.$route.query = destination.query } },
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

test('standalone roster reset keeps the route batch and search updates its deep link', async () => {
  const requests=[]
  const {vm,destinations}=mount('OrientationStudentListView', {
    getOrientationStudents:async params=>{requests.push(params);return {code:0,data:{list:[],total:0}}}
  })
  vm.$route.query={batchId:'18'}
  vm.filters={...vm.filters,batchId:'18',keyword:'旧筛选'}
  vm.batches=[{id:'19',status:'ACTIVE'},{id:'18',status:'ACTIVE'}]
  vm.reset()
  assert.equal(requests[0].batchId,'18')
  assert.equal(vm.filters.keyword,'')
  vm.filters.batchId='19'
  await vm.search()
  assert.deepEqual(destinations.at(-1),{query:{batchId:'19'}})
  assert.equal(requests.at(-1).batchId,'19')
  vm.filters.batchId=''
  await vm.search()
  assert.deepEqual(destinations.at(-1),{query:{batchId:''}})
})

test('late roster response cannot replace the newly selected batch', async () => {
  const completions=[]
  const {vm}=mount('OrientationStudentListView', {
    getOrientationStudents:()=>new Promise(resolve=>completions.push(resolve))
  })
  vm.filters.batchId='18'; const old=vm.load()
  vm.filters.batchId='19'; const current=vm.load()
  completions[1]({code:0,data:{list:[{id:'batch19-student'}],total:1}}); await current
  completions[0]({code:0,data:{list:[{id:'batch18-student'}],total:1}}); await old
  assert.deepEqual(vm.rows,[{id:'batch19-student'}])
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

const schoolContext = () => ({ dataScope: { scope: 'TENANT' }, permissionActions: {
  'orientation.student.view': { allowed: true }, 'orientation.student.edit': { allowed: true }
} })

test('batch settings deep link reads only its exact batch and reset preserves it', async () => {
  const calls = []
  const { vm, component, destinations } = mount('OrientationBatchListView', {
    getOrientationContext: async () => ({ code: 0, data: schoolContext() }),
    getOrientationBatch: async id => { calls.push(id); return { code: 0, data: fixedBatch } },
    getOrientationBatches: async () => { throw new Error('should not read all batches') }
  })
  vm.$route.query = { batchId, panel: 'settings' }
  vm.page = 5; vm.filters = { keyword: '旧筛选', status: 'DRAFT' }
  await component.created.call(vm)
  assert.deepEqual(calls, [batchId])
  assert.deepEqual(vm.rows, [fixedBatch]); assert.equal(vm.total, 1); assert.equal(vm.page, 1)
  await vm.reset()
  assert.deepEqual(calls, [batchId, batchId])
  assert.equal(vm.settingsBatchId, batchId)
  assert.deepEqual(vm.filters, { keyword: '', status: '' })
  vm.showAllBatches()
  assert.deepEqual(destinations.at(-1), { path: '/admin/orientation/batches', query: { batchId: '' } })
})

test('settings failure stays on the selected batch rather than displaying an unrelated list', async () => {
  const { vm } = mount('OrientationBatchListView', {
    getOrientationBatch: async () => ({ code: 1, message: '本批次已不可访问' })
  })
  vm.$route.query = { batchId, panel: 'settings' }; vm.rows = [fixedBatch]
  await vm.load()
  assert.equal(vm.error, '本批次已不可访问')
  assert.deepEqual(vm.rows, []); assert.equal(vm.total, 0); assert.equal(vm.loading, false)
})

test('switching batch settings closes old actions and discards late batch reads', async () => {
  let finishOld
  const next = { ...fixedBatch, id: '1000000000000000908', batchName: '另一批次' }
  const { vm, component } = mount('OrientationBatchListView', {
    getOrientationContext: async () => ({ code: 0, data: schoolContext() }),
    getOrientationBatch: id => id === batchId ? new Promise(resolve => { finishOld = resolve }) : Promise.resolve({ code: 0, data: next })
  })
  vm.$route.query = { batchId, panel: 'settings' }
  const first = vm.load()
  vm.confirmVisible = true; vm.confirmRow = fixedBatch; vm.confirmMode = 'close'
  vm.editVisible = true; vm.numberingVisible = true
  vm.$route.query.batchId = next.id
  await component.watch.batchContextKey.call(vm)
  assert.equal(vm.confirmVisible, false); assert.equal(vm.confirmRow, null)
  assert.equal(vm.editVisible, false); assert.equal(vm.numberingVisible, false)
  finishOld({ code: 0, data: fixedBatch }); await first
  assert.deepEqual(vm.rows, [next]); assert.equal(vm.loading, false)
})

test('moving from roster to settings cannot restore the old roster from a late response', async () => {
  let finishRoster
  let reads = 0
  const { vm, component } = mount('OrientationBatchListView', {
    getOrientationContext: async () => ({ code: 0, data: schoolContext() }),
    getOrientationBatch: async () => ++reads === 1 ? new Promise(resolve => { finishRoster = resolve }) : { code: 0, data: fixedBatch }
  })
  vm.$route.query = { batchId, panel: 'students' }
  const old = vm.loadRosterBatch()
  vm.$route.query.panel = 'settings'
  await component.watch.batchContextKey.call(vm)
  finishRoster({ code: 0, data: fixedBatch }); await old
  assert.equal(vm.rosterBatch, null)
  assert.deepEqual(vm.rows, [fixedBatch])
})

test('batch close requires school scope and management capability and explains each denial', async () => {
  for (const kind of ['missing', 'college', 'read-only', 'no-manage']) {
    const writes = []
    const { vm, messages } = mount('OrientationBatchListView', { closeOrientationBatch: async id => writes.push(id) })
    vm.ctx = kind === 'missing' ? null : schoolContext()
    if (kind === 'college') vm.ctx.dataScope.scope = 'COLLEGE'
    if (kind === 'read-only') vm.ctx.readonlyTenant = true
    if (kind === 'no-manage') vm.ctx.permissionActions['orientation.student.edit'].allowed = false
    const action = vm.rowActions(fixedBatch).find(row => row.key === 'close')
    assert.equal(action.disabled, true)
    assert.match(action.disabledReason, /权限|全校数据范围|只读/)
    vm.onRowAction('close', fixedBatch)
    assert.equal(vm.confirmVisible, false)
    vm.confirmRow = fixedBatch; vm.confirmMode = 'close'
    await vm.onConfirm()
    assert.deepEqual(writes, [])
    assert.equal(messages.length, 2)
  }
})

test('successful close rereads the exact batch and offers continuation into its archive', async () => {
  const closed = { ...fixedBatch, status: 'CLOSED' }
  const writes = [], reads = []
  const { vm, destinations, messages } = mount('OrientationBatchListView', {
    closeOrientationBatch: async id => { writes.push(id); return { code: 0, data: { id, status: 'CLOSED' } } },
    getOrientationBatch: async id => { reads.push(id); return { code: 0, data: closed } }
  })
  vm.$route.query = { batchId, panel: 'settings' }; vm.ctx = schoolContext()
  assert.equal(vm.rowActions(fixedBatch).find(row => row.key === 'close').disabled, false)
  vm.onRowAction('close', fixedBatch); await vm.onConfirm()
  assert.deepEqual(writes, [batchId]); assert.deepEqual(reads, [batchId])
  assert.deepEqual(vm.rows, [closed]); assert.equal(vm.confirmVisible, false)
  assert.match(messages[0], /已结束.*继续归档/)
  assert.equal(vm.rowActions(closed).find(row => row.key === 'archive').label, '继续归档')
  vm.onRowAction('archive', closed)
  assert.deepEqual(destinations.at(-1), { path: '/admin/orientation/archive', query: { batchId } })
})

test('late close response cannot close a new batch dialog or refresh the old batch', async () => {
  let finishClose
  const next = { ...fixedBatch, id: '1000000000000000908' }
  const reads = []
  const { vm, component, messages } = mount('OrientationBatchListView', {
    getOrientationContext: async () => ({ code: 0, data: schoolContext() }),
    closeOrientationBatch: () => new Promise(resolve => { finishClose = resolve }),
    getOrientationBatch: async id => { reads.push(id); return { code: 0, data: next } }
  })
  vm.$route.query = { batchId, panel: 'settings' }; vm.ctx = schoolContext()
  vm.onRowAction('close', fixedBatch); const old = vm.onConfirm()
  vm.$route.query.batchId = next.id
  await component.watch.batchContextKey.call(vm)
  vm.onRowAction('close', next)
  finishClose({ code: 0, data: { status: 'CLOSED' } }); await old
  assert.equal(vm.confirmVisible, true); assert.equal(vm.confirmRow.id, next.id)
  assert.deepEqual(reads, [next.id]); assert.deepEqual(messages, [])
})

test('ordinary all-batch view retains server filtering and pagination', async () => {
  const calls = []
  const { vm } = mount('OrientationBatchListView', {
    getOrientationBatches: async params => { calls.push(params); return { code: 0, data: { list: [fixedBatch], total: 45 } } }
  })
  vm.filters = { keyword: '2026', status: 'ACTIVE' }; vm.page = 3
  await vm.load()
  assert.deepEqual(calls, [{ keyword: '2026', status: 'ACTIVE', page: 3, pageSize: 10 }])
  assert.deepEqual(vm.rows, [fixedBatch]); assert.equal(vm.total, 45)
})

test('no-show follow-up carries exact student and original batch instead of searching names', () => {
  const { vm, destinations } = mount('OrientationNoShowView')
  const student = { id: '9007199254740997', batchId, name: '同名学生' }
  vm.loading = false; vm.$route.query.batchId = 'another-batch'
  vm.ctx = { permissionActions: { 'orientation.enrollment.finalize': { allowed: true } } }
  vm.onRowAction('disposition', student)
  assert.deepEqual(destinations.pop(), { path: '/admin/orientation/qualification', query: { batchId, orientationStudentId: student.id } })
  vm.onRowAction('detail', student)
  assert.deepEqual(destinations.pop(), { path: `/admin/orientation/students/${student.id}`, query: { batchId } })
  assert.deepEqual(vm.rowActions().map(action => action.key), ['disposition', 'detail'])
  vm.ctx.permissionActions['orientation.enrollment.finalize'].allowed = false
  assert.deepEqual(vm.rowActions().map(action => action.key), ['detail'])
  vm.onRowAction('disposition', student)
  assert.deepEqual(destinations, [])
})

test('no-show reads preserve batch and ignore obsolete responses and failed lists', async () => {
  const pending = [], calls = []
  const { vm, destinations } = mount('OrientationNoShowView', {
    getOrientationStudents(params) { calls.push(params); return new Promise(resolve => pending.push(resolve)) }
  })
  vm.$route.query.batchId = batchId
  vm.rows = [{ id: 'old' }]; vm.total = 99
  const first = vm.load()
  assert.deepEqual(vm.rows, []); assert.equal(vm.total, 0)
  vm.onRowAction('detail', { id: 'old' }); assert.deepEqual(destinations, [])
  vm.filters.keyword = '最新'; const second = vm.load()
  pending[1]({ code: 0, data: { list: [{ id: 'new' }], total: 1 } }); await second
  pending[0]({ code: 0, data: { list: [{ id: 'old' }], total: 99 } }); await first
  assert.deepEqual(vm.rows, [{ id: 'new' }])
  assert.ok(calls.every(params => params.batchId === batchId && params.pendingArrival))
  const failed = vm.load(); pending[2]({ code: 500 }); await failed
  assert.match(vm.error, /读取失败/); assert.deepEqual(vm.rows, []); assert.equal(vm.total, 0)
})

test('leaving no-show page invalidates its pending read', async () => {
  let finish
  const { vm, component } = mount('OrientationNoShowView', {
    getOrientationStudents: () => new Promise(resolve => { finish = resolve })
  })
  const loading = vm.load(); component.beforeUnmount.call(vm)
  finish({ code: 0, data: { list: [{ id: 'late' }], total: 1 } }); await loading
  assert.deepEqual(vm.rows, []); assert.equal(vm.total, 0)
})
