import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { orientationDestination } from '../src/modules/orientation/routeContext.js'

const read = path => readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8')
const ok = data => ({ code: 0, data })
const batchId = '9007199254740993'
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

function screen(file, api = {}, props = {}) {
  const imports = []
  const script = parse(read(file)).descriptor.script.content
    .replace(/import \* as api from [^\n]+/g, '')
    .replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, names) => {
      imports.push(...names.split(',').map(name => name.trim())); return ''
    }).replace(/import\s+(\w+)\s+from\s+['"][^'"]+['"]/g, (_, name) => { imports.push(name); return '' })
    .replace('export default', 'return')
  const downloads = [], messages = [], destinations = [], events = []
  const dependencies = { orientationDestination, downloadXlsxFromApi: result => downloads.push(result),
    formatDateTime: value => value, toast: { error: value => messages.push(value), success: value => messages.push(value) } }
  const component = new Function('api', ...imports, script)(api, ...imports.map(name => dependencies[name] || {}))
  const vm = { $route: { path: '/admin/orientation/statistics', query: { batchId } },
    $router: { push: value => destinations.push(value) }, $emit: (...args) => events.push(args), ...props }
  Object.assign(vm, component.data.call(vm))
  for (const [key, value] of Object.entries(component.methods || {})) vm[key] = value.bind(vm)
  for (const [key, value] of Object.entries(component.computed || {})) Object.defineProperty(vm, key, { get: () => value.call(vm) })
  return { vm, component, downloads, messages, destinations, events }
}

const permission = allowed => ({ permissionActions: { 'orientation.student.export': { allowed } } })
const stats = api => screen('views/admin/orientation/OrientationStatsView.vue', api)
const query = api => screen('views/admin/orientation/OrientationDataView.vue', api)

test('all existing list export entrances submit their own batch instead of selecting another active one', async () => {
  for (const [file, report] of [['DormCheckinView', 'dormList'], ['OrientationExceptionView', 'exceptionList'],
    ['OrientationMaterialReviewView', 'materialList'], ['RegistrationProgressView', 'progressList'],
    ['OrientationStudentListView', 'studentList'], ['PaymentGreenChannelView', 'paymentList']]) {
    const calls = []
    const { vm } = screen(`views/admin/orientation/${file}.vue`, { createExport: (...args) => { calls.push(args); return ok({}) } })
    if (!Object.getOwnPropertyDescriptor(vm, 'batchId')?.get) vm.batchId = batchId
    vm.filters = { batchId }; vm.tab = 'payment'
    await vm.exportFn({ purpose: '测试批次台账核对', batchId: 'wrong' })
    assert.equal(calls[0][0], report, file)
    assert.equal(calls[0][1].batchId, batchId, file)
    if (file === 'PaymentGreenChannelView') {
      vm.tab = 'green'; await vm.exportFn({ purpose: '测试批次台账核对' })
      assert.equal(calls[1][0], 'greenChannelList'); assert.equal(calls[1][1].batchId, batchId)
    }
  }
})

function exportApi(handler = async () => ({ taskId: '21', status: 'SUCCESS' })) {
  const calls = []
  const source = read('modules/orientation/api/orientation.api.js')
  const body = source.slice(source.indexOf('export async function createExport'), source.indexOf('/* ---------------- 审计'))
    .replace('export async function', 'async function')
  const createExport = new Function('fail', 'callData', 'request', `${body}; return createExport`)(
    (message, code = 1) => ({ message, code }), async fn => { try { return ok(await fn()) } catch (e) { return { code: 1, message: e.message } } },
    async (url, options) => { calls.push({ url, ...options }); return handler() })
  return { calls, createExport }
}

test('export API refuses missing or unsafe batch without querying the first active batch', async () => {
  for (const id of [undefined, '', '0', 'bad', 9007199254740992]) {
    const api = exportApi()
    assert.notEqual((await api.createExport('studentList', { batchId: id, purpose: '当前批次台账核对', auditConfirmed: true })).code, 0)
    assert.deepEqual(api.calls, [])
  }
  const api = exportApi()
  const result = await api.createExport('greenChannelList', { batchId, purpose: '当前批次台账核对', auditConfirmed: true })
  assert.equal(result.data.downloadUrl, '/api/v1/export/tasks/21/download')
  assert.deepEqual(api.calls[0].body, { batchId, purpose: '当前批次台账核对', reportType: 'green-channel' })
  assert.equal(api.calls.length, 1)
  assert.notEqual((await exportApi(() => ({})).createExport('studentList', { batchId, purpose: '当前批次台账核对', auditConfirmed: true })).code, 0)
})

test('statistics todo links carry the batch actually displayed, including a default-batch entry', async () => {
  const { vm, destinations } = stats({ getOrientationDashboard: async () => ok({ batchId, batchName: '迎新甲' }) })
  vm.$route.query = {}; await vm.load(); vm.go('/admin/orientation/materials')
  assert.equal(destinations[0], `/admin/orientation/materials?batchId=${batchId}`)
})

test('failed or late statistics reads cannot export the previous batch', async () => {
  const old = deferred(); let readCount = 0
  const { vm } = stats({ getOrientationDashboard: () => ++readCount === 1 ? old.promise : Promise.resolve({ code: 1, message: '读取失败' }) })
  vm.ctx = permission(true); vm.data.batchId = batchId
  const pending = vm.load(); assert.equal(vm.data.batchId, '')
  await vm.load(); old.resolve(ok({ batchId: 'wrong' })); await pending
  assert.equal(vm.error, '读取失败'); assert.equal(vm.data.batchId, '')
  vm.openExport(); assert.equal(vm.exportVisible, false)
})

test('statistics export retains its receipt for redownload and prevents duplicate generation', async () => {
  const request = deferred(), calls = []
  const { vm, downloads } = stats({ createExport: (...args) => { calls.push(args); return request.promise } })
  vm.ctx = permission(true); vm.loading = false; vm.data.batchId = batchId
  vm.openExport(); vm.exportPurpose = '迎新台账核对用途'
  const saving = vm.exportReport(); await vm.exportReport()
  assert.equal(calls.length, 1); assert.equal(calls[0][1].batchId, batchId)
  request.resolve(ok({ fileName: '迎新台账.xlsx', rowCount: 1, taskId: '21' })); await saving
  assert.equal(vm.exportVisible, true); assert.equal(downloads.length, 1)
  vm.downloadExport(); await vm.exportReport()
  assert.equal(downloads.length, 2); assert.equal(calls.length, 1)
})

test('export failures retain the purpose and statistics; leaving suppresses late downloads', async () => {
  const { vm } = stats({ createExport: async () => ({ code: 1, message: '导出服务繁忙' }) })
  vm.ctx = permission(true); vm.loading = false; vm.data.batchId = batchId; vm.exportPurpose = '迎新台账核对用途'
  await vm.exportReport()
  assert.equal(vm.exportPurpose, '迎新台账核对用途'); assert.equal(vm.error, ''); assert.equal(vm.exportError, '导出服务繁忙')
  const late = deferred()
  const other = stats({ createExport: () => late.promise })
  other.vm.ctx = permission(true); other.vm.loading = false; other.vm.data.batchId = batchId; other.vm.exportPurpose = '迎新台账核对用途'
  const saving = other.vm.exportReport(); other.component.beforeUnmount.call(other.vm)
  late.resolve(ok({ taskId: '22' })); await saving
  assert.deepEqual(other.downloads, [])
})

test('newcomer query checks export permission and opens the precise student within the batch', async () => {
  const calls = []
  const { vm, destinations } = query({ createExport: (...args) => { calls.push(args); return ok({}) } })
  vm.ctx = permission(false); vm.onToolbar('export'); assert.equal(vm.exportVisible, false)
  assert.notEqual((await vm.exportFn({})).code, 0); assert.equal(calls.length, 0)
  vm.ctx = permission(true); vm.onToolbar('export'); assert.equal(vm.exportVisible, true)
  await vm.exportFn({ auditConfirmed: true, purpose: '当前批次台账核对' })
  assert.equal(calls[0][1].batchId, batchId)
  vm.openStudent({ id: '9007199254740995', batchId })
  assert.deepEqual(destinations[0], { path: '/admin/orientation/students/9007199254740995', query: { batchId } })
})

test('newcomer query drops stale filtered rows and keeps a read failure separate from an empty list', async () => {
  const old = deferred(); let reads = 0
  const { vm } = query({ getOrientationStudents: () => ++reads === 1 ? old.promise : Promise.resolve({ code: 1, message: '读取失败' }) })
  const initial = vm.load(); await vm.load(); old.resolve(ok({ list: [{ id: 'old' }], total: 1 })); await initial
  assert.deepEqual(vm.rows, []); assert.equal(vm.total, 0); assert.equal(vm.error, '读取失败')
})

test('shared orientation export dialog validates, downloads, reuses the receipt and retains failed input', async () => {
  const request = deferred(); let writes = 0
  const { vm, component, downloads, messages } = screen('modules/orientation/components/ExportDialog.vue', {}, {
    options: { scopes: [{ value: 'SCOPE_ALL' }], fieldGroups: [{ key: 'ledger' }] },
    exportFn: () => { writes++; return request.promise },
  })
  component.watch.visible.call(vm, true); await vm.doExport(); assert.equal(writes, 0)
  vm.purpose = '当前批次台账核对'; vm.auditConfirmed = true
  const saving = vm.doExport(); await vm.doExport(); assert.equal(writes, 1)
  request.resolve(ok({ taskId: '21', fileName: '台账.xlsx' })); await saving
  vm.downloadResult(); await vm.doExport(); assert.equal(writes, 1); assert.equal(downloads.length, 2)
  component.watch.visible.call(vm, true); vm.purpose = '保留失败时的用途'; vm.auditConfirmed = true
  vm.exportFn = async () => { throw new Error('网络中断') }; await vm.doExport()
  assert.equal(vm.purpose, '保留失败时的用途'); assert.equal(vm.busy, false); assert.ok(messages.includes('网络中断'))
})
