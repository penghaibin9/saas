import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

const batch = { id: '1000000000000000907', batchNo: 'ARCHIVE-2026', batchName: '2026 迎新', status: 'CLOSED' }
const archive = { id: '71', archiveName: '2026 迎新归档', batchId: batch.id, batchNo: batch.batchNo, batchName: batch.batchName, batchStatus: 'CLOSED', status: 'PENDING' }
const context = () => ({ dataScope: { scope: 'TENANT', name: '全校' }, permissionActions: {
  'orientation.student.view': { allowed: true }, 'orientation.student.edit': { allowed: true }
} })
const ok = data => ({ code: 0, data })
const list = rows => ok({ list: rows, total: rows.length })
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

function mount(overrides = {}, routeBatch = batch.id) {
  const source = readFileSync(new URL('../src/views/admin/orientation/OrientationArchiveView.vue', import.meta.url), 'utf8')
  const imports = []
  const script = parse(source).descriptor.script.content
    .replace(/import \* as api from [^\n]+/g, '')
    .replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, names) => {
      imports.push(...names.split(',').map(name => name.trim())); return ''
    }).replace('export default', 'return')
  const messages = []
  const calls = []
  const api = {
    getOrientationContext: async () => ok(context()),
    getOrientationBatches: async () => list([]),
    getOrientationBatch: async id => { calls.push(['batch', id]); return ok(batch) },
    getArchives: async params => { calls.push(['archives', params]); return list([archive]) },
    ...overrides
  }
  const component = new Function('api', ...imports, script)(api, ...imports.map(name => name === 'toast'
    ? { success: message => messages.push(message), error: message => messages.push(message) } : {}))
  const destinations = []
  const vm = { ...component.data(), $route: { path: '/admin/orientation/archive', query: { batchId: routeBatch } },
    $router: { push: destination => destinations.push(destination), replace: destination => { destinations.push(destination); vm.$route.query = destination.query } } }
  for (const [name, fn] of Object.entries(component.methods)) vm[name] = fn.bind(vm)
  for (const [name, fn] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: () => fn.call(vm) })
  return { vm, component, calls, destinations, messages }
}

test('archive deep link filters exact batch and prefills it even outside the first batch page', async () => {
  const { vm, component, calls } = mount()
  await component.created.call(vm)
  assert.deepEqual(calls.find(([name]) => name === 'batch'), ['batch', batch.id])
  assert.equal(calls.find(([name]) => name === 'archives')[1].batchId, batch.id)
  assert.equal(vm.filters.batchId, batch.id)
  assert.equal(vm.currentBatch.id, batch.id)
  assert.equal(vm.batches[0].id, batch.id)
  vm.onToolbar('create')
  assert.equal(vm.editingModel.batchNo, batch.batchNo)
  assert.equal(vm.editVisible, true)
  assert.equal(vm.editFields.find(field => field.key === 'batchNo').disabled, true)
})

test('filter reset keeps the current batch and another batch search writes a refreshable route', async () => {
  const { vm, component, calls, destinations } = mount()
  await component.created.call(vm)
  vm.filters = { batchId: 'other', keyword: '旧关键词', status: 'DONE' }; vm.page = 9
  await vm.reset()
  assert.deepEqual(vm.filters, { batchId: batch.id, keyword: '', status: '' })
  assert.equal(calls.at(-1)[1].batchId, batch.id)
  assert.equal(calls.at(-1)[1].page, 1)
  vm.filters.batchId = '1000000000000000908'
  await vm.search()
  assert.deepEqual(destinations.at(-1), { path: '/admin/orientation/archive', query: { batchId: '1000000000000000908' } })
})

test('changing batches drops late rows and closes old forms and snapshot context', async () => {
  const old = deferred()
  const next = { ...batch, id: '1000000000000000908', batchNo: 'ARCHIVE-NEXT', batchName: '另一批次' }
  const { vm, component } = mount({
    getOrientationBatch: async id => ok(id === batch.id ? batch : next),
    getArchives: params => params.batchId === batch.id ? old.promise : Promise.resolve(list([{ ...archive, id: '72', batchId: next.id }]))
  })
  const first = component.created.call(vm)
  await Promise.resolve()
  vm.editVisible = true; vm.runVisible = true; vm.snapshotId = '71'
  vm.$route.query.batchId = next.id
  await component.watch['$route.query.batchId'].call(vm)
  assert.equal(vm.editVisible, false); assert.equal(vm.runVisible, false); assert.equal(vm.snapshotId, null)
  old.resolve(list([archive])); await first
  assert.equal(vm.currentBatch.id, next.id)
  assert.equal(vm.rows[0].id, '72')
  assert.equal(vm.loading, false)
})

test('open batches cannot run archives and preparation links keep the exact batch', async () => {
  const writes = []
  const current = { ...batch, status: 'ACTIVE' }
  const pending = { ...archive, batchStatus: 'ACTIVE' }
  const { vm, component, destinations, messages } = mount({ getOrientationBatch: async () => ok(current), runArchive: async id => writes.push(id) })
  await component.created.call(vm)
  const run = vm.rowActions(pending).find(action => action.key === 'run')
  assert.equal(run.disabled, true)
  assert.match(run.disabledReason, /关闭本批次/)
  vm.onRowAction('run', pending)
  assert.equal(vm.runVisible, false)
  vm.runRow = pending; await vm.onRun()
  assert.deepEqual(writes, [])
  assert.ok(messages.every(message => /关闭本批次/.test(message)))
  vm.openBatchWork('qualification', current)
  vm.openBatchWork('no-show', current)
  vm.onRowAction('prepare', pending)
  assert.deepEqual(destinations, [
    { path: '/admin/orientation/qualification', query: { batchId: batch.id } },
    { path: '/admin/orientation/no-show', query: { batchId: batch.id } },
    { path: '/admin/orientation/batches', query: { batchId: batch.id, panel: 'settings' } }
  ])
})

test('read-only, missing management, and college scopes explain and prevent writes', async () => {
  for (const kind of ['readonly', 'no-manage', 'college']) {
    const ctx = context()
    if (kind === 'readonly') ctx.readonlyTenant = true
    if (kind === 'no-manage') ctx.permissionActions['orientation.student.edit'].allowed = false
    if (kind === 'college') ctx.dataScope.scope = 'COLLEGE'
    const writes = []
    const { vm, component } = mount({ getOrientationContext: async () => ok(ctx), createArchive: async body => writes.push(body), runArchive: async id => writes.push(id) })
    await component.created.call(vm)
    assert.equal(vm.toolbarActions[0].disabled, true)
    assert.match(vm.toolbarActions[0].disabledReason, /只读|管理权限|全校数据范围/)
    vm.onToolbar('create'); await vm.onEditSubmit({ archiveName: '不应写入' })
    vm.runRow = archive; await vm.onRun()
    assert.deepEqual(writes, [])
    assert.equal(vm.editVisible, false)
    const view = vm.rowActions({ ...archive, status: 'DONE' })[0]
    assert.equal(view.disabled, kind === 'college')
  }
})

test('missing view permission and failed context never fetch or offer archive writes', async () => {
  for (const denied of [true, false]) {
    const ctx = context(); ctx.permissionActions['orientation.student.view'].allowed = false
    const { vm, component, calls } = mount({ getOrientationContext: async () => denied ? ok(ctx) : { code: 1, message: '权限服务暂不可用' } })
    await component.created.call(vm)
    assert.deepEqual(calls, [])
    assert.equal(vm.noPermission, denied)
    if (!denied) assert.equal(vm.error, '权限服务暂不可用')
    assert.equal(vm.toolbarActions[0].disabled, true)
  }
})

test('creation binds the known batch, preserves a failed form, and prevents repeat submit', async () => {
  const pending = deferred(); const writes = []
  const { vm, component, messages } = mount({ createArchive: body => { writes.push(body); return pending.promise } })
  await component.created.call(vm)
  vm.onToolbar('create')
  const form = { archiveName: '自定义归档名称', batchNo: 'wrong-batch', remark: '保留备注' }
  const first = vm.onEditSubmit(form)
  await vm.onEditSubmit(form)
  assert.deepEqual(writes, [{ ...form, batchNo: batch.batchNo }])
  pending.resolve({ code: 1, message: '保存失败，请重试' }); await first
  assert.equal(vm.editVisible, true); assert.equal(vm.submitting, false)
  assert.equal(form.remark, '保留备注')
  assert.deepEqual(messages, ['保存失败，请重试'])
})

test('running a closed archive blocks repeated clicks then reloads the same batch', async () => {
  const pending = deferred(); const writes = []
  const { vm, component, calls, messages } = mount({ runArchive: id => { writes.push(id); return pending.promise } })
  await component.created.call(vm)
  vm.onRowAction('run', archive)
  const first = vm.onRun(); await vm.onRun()
  assert.deepEqual(writes, ['71']); assert.equal(vm.runSubmitting, true)
  pending.resolve(ok({ itemCount: 1 })); await first
  assert.equal(vm.runSubmitting, false); assert.equal(vm.runVisible, false)
  assert.equal(calls.at(-1)[1].batchId, batch.id)
  assert.match(messages[0], /已归档 1 名新生.*查看归档快照/)
})

test('snapshot close drops a late result and network failures stay retryable', async () => {
  const pending = deferred()
  const { vm, component } = mount({ getArchiveItems: () => pending.promise })
  await component.created.call(vm)
  const reading = vm.onRowAction('view', { ...archive, status: 'DONE' })
  vm.closeSnapshots()
  pending.resolve(list([{ id: '1', name: '历史学生', stage: 'ENROLLED' }]))
  await reading
  assert.deepEqual(vm.snapshots, []); assert.equal(vm.snapshotId, null)
  const failed = mount({ getArchiveItems: async () => { throw new Error('连接已中断') } })
  await failed.component.created.call(failed.vm)
  await failed.vm.onRowAction('view', { ...archive, status: 'DONE' })
  assert.equal(failed.vm.snapshotError, '连接已中断')
  assert.equal(failed.vm.snapshotLoading, false)
})

test('failed batch lookup clears stale data and cannot accidentally archive another batch', async () => {
  const { vm, component } = mount({ getOrientationBatch: async () => ({ code: 1, message: '当前批次不存在' }) })
  vm.rows = [archive]; vm.currentBatch = batch
  await component.created.call(vm)
  assert.equal(vm.error, '当前批次不存在')
  assert.deepEqual(vm.rows, []); assert.equal(vm.currentBatch, null)
  assert.equal(vm.toolbarActions[0].disabled, true)
})
