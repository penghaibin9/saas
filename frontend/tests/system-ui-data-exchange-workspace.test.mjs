import test from 'node:test'
import assert from 'node:assert/strict'
import { setImmediate } from 'node:timers/promises'
import { exchangeRights, taskId, taskKey, assertTask, taskCounts, actionAvailable,
  createExchangeState, createExchangeController } from '../src/modules/system/utils/dataExchangeWorkspace.js'

const imp = (patch = {}) => ({ id: '41', jobType: 'IMPORT', moduleCode: 'SYSTEM', version: 0,
  importType: 'IDENTITY_TEACHER', status: 'VALIDATED', sourceFileId: '900',
  totalRows: 2, validRows: 2, invalidRows: 0, retryable: false, cancellable: true, ...patch })
const exp = (patch = {}) => ({ id: '41', jobType: 'EXPORT', moduleCode: 'SYSTEM', version: 0,
  exportType: 'INITIAL_CREDENTIAL_RECEIPT', status: 'SUCCEEDED', fileObjectId: '901',
  rowCount: 2, downloadedCount: 0, strongSensitive: true, downloadable: true, ...patch })
const context = view => ({ visibility: view.visibility, moduleCode: view.moduleCode || null,
  allowedVisibilities: ['OWN', 'MODULE', 'TENANT'], allowedModules: ['SYSTEM'] })
const deferred = () => { let resolve; const promise = new Promise(yes => { resolve = yes }); return { promise, resolve } }
const rights = { read: true, upload: true, confirm: true, retry: true, revoke: true, download: true }
function setup(overrides = {}) {
  const state = createExchangeState(), calls = [], jobs = { IMPORT: imp(), EXPORT: exp() }
  let grants = { ...rights }
  const api = {
    summary: async view => ({ ...context(view), total: 77, imports: 50, exports: 27, pending: 5, failed: 2, scanning: 1, expired: 1, receipts: 20 }),
    list: async q => ({ ...context(q), list: Object.values(jobs), total: 77, page: q.page, pageSize: q.pageSize }),
    getImport: async (id, view) => { calls.push(['read', id, view]); return structuredClone(jobs.IMPORT) },
    getExport: async (id, view) => { calls.push(['read-export', id, view]); return structuredClone(jobs.EXPORT) },
    getImportErrors: async (_id, q) => ({ list: [], total: 0, page: q.page, pageSize: q.pageSize }),
    confirmImport: async (id, version) => { calls.push(['confirm', id, version]); jobs.IMPORT = imp({ version: 2, status: 'SUCCEEDED', cancellable: false }) },
    retryImport: async (id, version) => { calls.push(['retry', id, version]); jobs.IMPORT = imp({ version: version + 1, status: 'SCANNING' }) },
    cancelImport: async (id, version, reason) => { calls.push(['cancel', id, version, reason]); jobs.IMPORT = imp({ version: version + 1, status: 'CANCELLED' }) },
    revokeExport: async (id, version, reason) => { calls.push(['revoke', id, version, reason]); jobs.EXPORT = exp({ version: version + 1, status: 'REVOKED', downloadable: false }) },
    downloadExport: async row => { calls.push(['download', row.id, row.version]); jobs.EXPORT = exp({ version: row.version + 2, downloadedCount: 1 }); return { ticket: 'SECRET_TICKET_SENTINEL' } },
    ...overrides
  }
  const controller = createExchangeController({ state, api, rights: () => grants })
  return { state, api, controller, calls, jobs, grant: value => { grants = { ...grants, ...value } } }
}
async function review(s, type = 'confirm', row = s.jobs.IMPORT) {
  await s.controller.prepare(type, row); assert.ok(s.state.pending)
  s.state.pending.acknowledged = true; s.state.pending.reason = '本次测试操作原因'
}
const writes = s => s.calls.filter(c => ['confirm', 'retry', 'cancel', 'revoke', 'download'].includes(c[0]))

test('viewOwn grants read, not writes/download; viewTenant-only selects TENANT', () => {
  const r = exchangeRights(code => code === 'systemAdmin.dataExchange.viewOwn')
  assert.equal(r.read, true); assert.equal(r.initialVisibility, 'OWN')
  for (const k of ['confirm', 'retry', 'download', 'revoke', 'upload']) assert.equal(r[k], false)
  assert.equal(exchangeRights(c => c === 'systemAdmin.dataExchange.viewTenant').initialVisibility, 'TENANT')
  assert.equal(exchangeRights(c => c === 'systemAdmin.audit.sensitive.view').read, false)
})
test('task IDs retain type and large decimal strings; invalid versions fail closed', () => {
  assert.notEqual(taskKey(imp()), taskKey(exp())); assert.equal(taskId('9223372036854775806'), '9223372036854775806')
  for (const id of [41, '', '0', '0041', '41/confirm', '41.0', null]) assert.throws(() => taskId(id))
  for (const version of [undefined, null, -1, '0', NaN]) assert.throws(() => assertTask(imp({ version })))
  assert.equal(assertTask(imp()).version, 0); assert.throws(() => assertTask(exp(), imp()))
})
for (const status of ['SCANNING', 'WORKER_CLAIMED', 'PARSING', 'FUTURE']) test(`processing ${status} has unknown counts and cannot confirm`, () => {
  assert.equal(taskCounts(imp({ status })).totalRows, null); assert.equal(actionAvailable('confirm', imp({ status }), rights), false)
})
for (const patch of [{ totalRows: 0, validRows: 0 }, { invalidRows: undefined }, { invalidRows: '0' }, { totalRows: 5 }, { validRows: '2' }]) test(`inconsistent import blocks confirmation: ${JSON.stringify(patch)}`, () => {
  assert.equal(actionAvailable('confirm', imp(patch), rights), false)
})
test('receipt relationship only accepts same-module typed export-task metadata', () => {
  const row = exp({ id: '62', adapterType: 'IMPORT_JOB', adapterRef: '41' })
  assertTask(imp({ receiptJobs: { list: [row], total: 1 } }))
  for (const p of [{ adapterRef: '40' }, { jobType: 'IMPORT' }, { moduleCode: 'OTHER' }]) assert.throws(() => assertTask(imp({ receiptJobs: { list: [{ ...row, ...p }], total: 1 } })))
})
test('summary failure preserves successful tasks and list failure preserves real summary', async () => {
  const a = setup({ summary: async () => { throw Error('summary unavailable') } }); await a.controller.refresh()
  assert.equal(a.state.summary.data, null); assert.equal(a.state.list.total, 77); assert.equal(a.state.list.rows.length, 2)
  const b = setup({ list: async () => { throw Error('list unavailable') } }); await b.controller.refresh()
  assert.equal(b.state.summary.data.total, 77); assert.equal(b.state.list.total, null); assert.equal(b.state.list.error, 'list unavailable')
})
test('malformed pagination is not turned into an empty successful list', async () => {
  const s = setup({ list: async q => ({ ...context(q), list: [], total: '0', page: q.page, pageSize: q.pageSize }) }); await s.controller.loadList()
  assert.ok(s.state.list.error); assert.equal(s.state.list.total, null)
})
test('late first page cannot overwrite a later page', async () => {
  const d = deferred(); const s = setup({ list: async q => q.page === 1 ? d.promise : ({ ...context(q), list: [], total: 22, page: 2, pageSize: 20 }) })
  const old = s.controller.loadList(1); await s.controller.loadList(2)
  d.resolve({ ...context({ visibility: 'OWN' }), list: [imp()], total: 22, page: 1, pageSize: 20 }); await old
  assert.equal(s.state.list.page, 2)
})
test('unapproved visibility denied; detail reads preserve authorized explicit context', async () => {
  const s = setup(); assert.equal(await s.controller.changeView('TENANT'), false); await s.controller.refresh()
  assert.equal(await s.controller.changeView('MODULE', 'UNKNOWN'), false); await s.controller.changeView('MODULE', 'SYSTEM')
  await s.controller.openDetail(imp()); assert.deepEqual(s.calls[0][2], { visibility: 'MODULE', moduleCode: 'SYSTEM' })
})
test('late import detail cannot replace selected export sharing a numeric id', async () => {
  const d = deferred(); const s = setup({ getImport: () => d.promise })
  const old = s.controller.openDetail(imp()); await s.controller.openDetail(exp()); d.resolve(imp()); await old
  assert.equal(s.state.detail.item.jobType, 'EXPORT')
})
test('dispose rejects late reads', async () => {
  const d = deferred(); const s = setup({ getImport: () => d.promise }); const old = s.controller.openDetail(imp())
  s.controller.dispose(); d.resolve(imp()); await old; assert.equal(s.state.detail.item, null)
})
test('error page strips raw snapshots and retains server total', async () => {
  const s = setup({ getImportErrors: async (_id, q) => ({ list: [{ id: '1', rowNo: 4, message: '字段必填', snapshot: { password: 'SECRET' } }], total: 42, page: q.page, pageSize: q.pageSize }) })
  await s.controller.openDetail(imp()); await s.controller.loadErrors(2)
  assert.equal(s.state.errors.total, 42); assert.equal(s.state.errors.page, 2); assert.ok(!JSON.stringify(s.state.errors).includes('SECRET'))
})
test('review final read → one version-only write → persistent readback', async () => {
  const s = setup(); await review(s); await s.controller.perform()
  assert.deepEqual(s.calls.slice(0, 4).map(c => c[0]), ['read', 'read', 'confirm', 'read'])
  assert.deepEqual(writes(s), [['confirm', '41', 0]]); assert.match(s.state.receipt, /已完成/)
})
for (const [type, row] of [['confirm', imp()], ['cancel', imp()], ['download', exp()], ['revoke', exp()]]) test(`${type} requires explicit acknowledgment`, async () => {
  const s = setup(); await s.controller.prepare(type, row); await s.controller.perform(); assert.equal(writes(s).length, 0)
})
test('version/file/count/state changes after review invalidate the action without POST', async () => {
  for (const patch of [{ version: 1 }, { sourceFileId: '999' }, { totalRows: 3, validRows: 3 }, { status: 'CONFIRMING' }]) {
    const s = setup(); await review(s); Object.assign(s.jobs.IMPORT, patch); await s.controller.perform()
    assert.equal(writes(s).length, 0); assert.match(s.state.operationError, /没有提交/)
  }
})
test('losing permission during final read prevents POST', async () => {
  const s = setup(); await review(s); s.api.getImport = async () => { s.grant({ confirm: false }); return imp() }
  await s.controller.perform(); assert.equal(writes(s).length, 0)
})
test('double-click confirmation is single-flight', async () => {
  const d = deferred(); let n = 0; const s = setup({ confirmImport: async () => { n++; return d.promise } }); await review(s)
  const pending = s.controller.perform(); await setImmediate(); await s.controller.perform(); assert.equal(n, 1)
  s.jobs.IMPORT = imp({ status: 'SUCCEEDED', version: 2 }); d.resolve(); await pending
})
test('POST timeout remains blocked across closing/reopening and view changes', async () => {
  let n = 0; const s = setup({ confirmImport: async () => { n++; throw Error('timeout') } }); await s.controller.refresh(); await review(s); await s.controller.perform()
  assert.ok(s.state.unresolved['IMPORT:41']); s.controller.closeAction(); await s.controller.changeView('TENANT')
  await s.controller.prepare('confirm', imp()); assert.equal(s.state.pending, null); assert.equal(n, 1)
})
test('unchanged readback stays blocked; a new version is displayed without replay', async () => {
  const s = setup({ confirmImport: async () => { throw Error('timeout') } }); await review(s); await s.controller.perform()
  await s.controller.openDetail(imp()); assert.ok(s.state.unresolved['IMPORT:41'])
  s.jobs.IMPORT = imp({ status: 'SUCCEEDED', version: 2 }); await s.controller.openDetail(imp())
  assert.equal(s.state.unresolved['IMPORT:41'], undefined); assert.match(s.state.receipt, /没有重放/)
})
test('successful POST but failed readback does not claim confirmed completion', async () => {
  const s = setup(); await review(s); let reads = 0; s.api.getImport = async () => { if (++reads > 1) throw Error('read failed'); return imp() }
  await s.controller.perform(); assert.ok(s.state.unresolved['IMPORT:41']); assert.match(s.state.receipt, /需要核对/)
})
test('cancel and revoke require trimmed reasons and exact loaded version', async () => {
  for (const type of ['cancel', 'revoke']) {
    const s = setup(); await review(s, type, type === 'cancel' ? imp() : exp()); s.state.pending.reason = 'x'; await s.controller.perform(); assert.equal(writes(s).length, 0)
    s.state.pending.reason = '  本次测试操作原因  '; await s.controller.perform(); assert.deepEqual(writes(s)[0], [type, '41', 0, '本次测试操作原因'])
  }
})
test('download uses canonical client and never stores ticket or raw ticket errors', async () => {
  const s = setup(); await review(s, 'download', exp()); await s.controller.perform()
  assert.deepEqual(writes(s), [['download', '41', 0]]); assert.ok(!JSON.stringify(s.state).includes('SECRET_TICKET_SENTINEL'))
  const t = setup({ downloadExport: async () => { throw Error('/download?ticket=SECRET_VALUE failed') } }); await review(t, 'download', exp()); await t.controller.perform()
  assert.ok(!t.state.operationError.includes('SECRET_VALUE'))
})
