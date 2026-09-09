import { setImmediate } from 'node:timers'
import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { IMPORT_TYPES, identityJob, importCounts, countText, importStatusLabel,
  confirmableJob, reviewFingerprint, importReceiptCounts, createImportState,
  createImportController, validJobId } from '../src/modules/system/utils/identityImportWorkspace.js'

const job = (patch = {}) => ({ id: '42', jobType: 'IMPORT', moduleCode: 'SYSTEM',
  importType: 'IDENTITY_TEACHER', status: 'VALIDATED', version: 0,
  sourceFileId: '11', totalRows: 3, validRows: 3, invalidRows: 0, ...patch })
const done = (patch = {}) => job({ status: 'SUCCEEDED', version: 2, confirmedRows: 3,
  result: { entities: { teachers: { created: 3 } } }, ...patch })
const file = () => ({ name: '教职工名单.xlsx', size: 512 })
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
function setup(overrides = {}, kind = 'teachers') {
  const state = createImportState(), calls = [], ids = []
  let server = job({ importType: IMPORT_TYPES[kind] }), uploadAllowed = true, confirmAllowed = true
  const api = { getImport: async (...args) => { calls.push(['read', ...args]); return structuredClone(server) },
    validateIdentity: async (...args) => { calls.push(['upload', ...args]); return structuredClone(server) },
    waitIdentityValidation: async (...args) => { calls.push(['poll', ...args]); return structuredClone(server) },
    confirmImport: async (...args) => { calls.push(['confirm', ...args]); server = done({ importType: IMPORT_TYPES[kind] }); return structuredClone(server) },
    getImportErrors: async (...args) => { calls.push(['errors', ...args]); return { list: [], total: 0, page: args[1].page, pageSize: 20 } }, ...overrides }
  const controller = createImportController({ state, api, kind, canUpload: () => uploadAllowed,
    canConfirm: () => confirmAllowed, onJobId: id => ids.push(id) })
  return { state, controller, calls, ids, api, setServer: v => { server = v },
    setConfirm: v => { confirmAllowed = v }, setUpload: v => { uploadAllowed = v } }
}
async function review(s) { await s.controller.resume('42'); await s.controller.prepareReview(); s.state.acknowledged = true }

test('version zero and stable decimal task IDs remain valid', () => {
  assert.equal(identityJob(job(), 'teachers').version, 0)
  assert.equal(confirmableJob(job()), true)
  for (const id of ['', '0', '-1', '1.5', 'abc', '42/confirm', '04']) assert.equal(validJobId(id), false)
})
test('wrong identity kind, tenant-facing module, ID or missing version fails closed', () => {
  for (const patch of [{ importType: 'IDENTITY_STUDENT' }, { moduleCode: 'OTHER' }, { jobType: 'EXPORT' }, { version: undefined }, { version: '0' }, { version: -1 }, { id: '43' }]) {
    assert.throws(() => identityJob(job(patch), 'teachers', '42'))
  }
})
test('scanning, claimed, parsing and unknown counts are never rendered as zero', () => {
  for (const status of ['SCANNING', 'WORKER_CLAIMED', 'PARSING', 'UNKNOWN']) {
    assert.deepEqual(importCounts(job({ status, totalRows: 0, validRows: 0, invalidRows: 0 })), { totalRows: null, validRows: null, invalidRows: null })
    assert.equal(confirmableJob(job({ status })), false)
  }
  assert.equal(countText(null), '未取得'); assert.equal(countText(0), '0')
  assert.equal(importStatusLabel(job({ status: 'FUTURE_STATE' })), '状态待核对')
})
test('confirmation requires consistent server counts, not truthy strings or default zeros', () => {
  for (const patch of [{ validRows: 0 }, { invalidRows: undefined }, { invalidRows: '0' }, { validRows: '3' }, { totalRows: 4 }, { version: '1' }, { invalidRows: 1 }, { totalRows: -3 }]) assert.equal(confirmableJob(job(patch)), false)
})
test('receipt projections expose audited counts, never private credentials or snapshots', () => {
  const data = done({ result: { entities: { students: { created: 1 }, studentAccounts: { created: 2 } }, summary: { studentsReused: 2, accountsSkipped: 1 }, credentials: [{ password: 'SECRET_SENTINEL' }] } })
  assert.deepEqual(importReceiptCounts(data, 'students').map(r => r.value), [1, 2, 2, 1])
  assert.ok(!JSON.stringify(importReceiptCounts(data, 'students')).includes('SECRET_SENTINEL'))
  assert.deepEqual(importReceiptCounts(job(), 'teachers'), [])
  assert.equal(importReceiptCounts(done({ result: {} }), 'teachers')[0].value, null)
})
test('upload registers a real File object once, records a task ID, then uses canonical reads', async () => {
  const s = setup(), selected = file(); s.controller.selectFile(selected); await s.controller.upload()
  assert.deepEqual(s.calls.map(r => r[0]), ['upload', 'read']); assert.equal(s.calls[0][2], selected)
  assert.deepEqual(s.ids, ['42']); assert.equal(s.state.busy, ''); assert.equal(s.state.readback, false)
})
test('empty and non-xlsx uploads never reach the API', async () => {
  const s = setup(); for (const f of [null, { name: 'data.csv', size: 12 }, { name: 'data.xlsx', size: 0 }]) {
    assert.equal(s.controller.selectFile(f), false); await s.controller.upload()
  }
  assert.equal(s.calls.length, 0)
})
test('upload permission is checked at click time', async () => {
  const s = setup(); s.controller.selectFile(file()); s.setUpload(false); await s.controller.upload(); assert.equal(s.calls.length, 0)
})
test('explicit failed-upload retry keeps exact File identity; never retries automatically', async () => {
  const files = []; const s = setup({ validateIdentity: async (_kind, f) => { files.push(f); throw Error('network unavailable') } })
  const f = file(); s.controller.selectFile(f); await s.controller.upload(); assert.equal(files.length, 1)
  assert.equal(s.state.uploadUncertain, true); await s.controller.upload(); assert.deepEqual(files, [f, f])
})
test('poll timeout keeps registered task and unknown counts without another upload', async () => {
  const scan = job({ status: 'SCANNING', totalRows: 0, validRows: 0, invalidRows: 0 })
  const s = setup({ waitIdentityValidation: async () => ({ ...scan, pollTimedOut: true }) }); s.setServer(scan)
  s.controller.selectFile(file()); await s.controller.upload()
  assert.equal(s.state.job.id, '42'); assert.match(s.state.note, /不需要重新上传/)
  assert.equal(importCounts(s.state.job).totalRows, null); await s.controller.upload()
  assert.equal(s.calls.filter(c => c[0] === 'upload').length, 1)
})
test('disposing a polling workspace aborts local polling, not the server job', async () => {
  const wait = deferred(); let signal
  const s = setup({ waitIdentityValidation: async (_id, options) => { signal = options.signal; return wait.promise } })
  s.setServer(job({ status: 'SCANNING' })); const pending = s.controller.resume('42'); await new Promise(r => setImmediate(r))
  s.controller.dispose(); assert.equal(signal.aborted, true); wait.resolve(job()); await pending
  assert.equal(s.state.job.status, 'SCANNING'); assert.equal(s.calls.some(r => r[0] === 'confirm'), false)
})
test('disposing an outstanding initial read ignores all late task data', async () => {
  const wait = deferred(); const s = setup({ getImport: () => wait.promise }); const pending = s.controller.resume('42')
  s.controller.dispose(); wait.resolve(job()); await pending; assert.equal(s.state.job, null)
})
test('an invalid or wrong-kind deep link never performs a write or shows another identity task', async () => {
  const s = setup(); await s.controller.resume('wrong'); assert.equal(s.calls.length, 0)
  s.setServer(job({ importType: 'IDENTITY_STUDENT' })); await s.controller.resume('42'); assert.equal(s.state.job, null)
  assert.match(s.state.error, /身份类型/); assert.equal(s.calls.filter(r => r[0] === 'confirm').length, 0)
})
test('confirmed job flow is fresh read, reviewed state, final read, one version-only API call and persisted readback', async () => {
  const s = setup(); await review(s); assert.equal(s.state.review, reviewFingerprint(job())); await s.controller.confirm()
  assert.deepEqual(s.calls.map(r => r[0]), ['read', 'read', 'read', 'confirm', 'read'])
  assert.deepEqual(s.calls.find(r => r[0] === 'confirm'), ['confirm', '42', 0])
  assert.equal(s.state.readback, true); assert.equal(s.state.uncertain, false); assert.equal(s.state.review, null)
})
test('confirmation without explicit human acknowledgment sends no confirm request', async () => {
  const s = setup(); await s.controller.resume('42'); await s.controller.prepareReview(); await s.controller.confirm()
  assert.equal(s.calls.filter(r => r[0] === 'confirm').length, 0)
})
test('server version change after review invalidates approval instead of silently retrying', async () => {
  const s = setup(); await review(s); s.setServer(job({ version: 1 })); await s.controller.confirm()
  assert.equal(s.calls.some(r => r[0] === 'confirm'), false); assert.equal(s.state.review, null); assert.match(s.state.note, /本次未提交/)
})
test('file, status and row-count changes after review each stop writes', async () => {
  for (const patch of [{ sourceFileId: '12' }, { totalRows: 4, validRows: 4 }, { status: 'CONFIRMING' }]) {
    const s = setup(); await review(s); s.setServer(job(patch)); await s.controller.confirm(); assert.equal(s.calls.some(r => r[0] === 'confirm'), false)
  }
})
test('lost permission during the final GET prevents the subsequent POST', async () => {
  const s = setup(); await review(s); s.api.getImport = async () => { s.setConfirm(false); return job() }
  await s.controller.confirm(); assert.equal(s.calls.some(r => r[0] === 'confirm'), false); assert.match(s.state.error, /无确认权限/)
})
test('POST timeout creates an uncertain outcome and blocks a second confirmation', async () => {
  let posts = 0; const s = setup({ confirmImport: async () => { posts++; throw Error('timeout') } }); await review(s)
  await s.controller.confirm(); assert.equal(s.state.uncertain, true); await s.controller.prepareReview(); await s.controller.confirm()
  assert.equal(posts, 1); assert.equal(s.state.readback, false)
})
test('successful POST with failing readback does not claim persistence verification', async () => {
  let posted = false; const s = setup({ getImport: async () => { if (posted) throw Error('read failed'); return job() }, confirmImport: async () => { posted = true; return done() } })
  await review(s); await s.controller.confirm(); assert.equal(s.state.job.status, 'SUCCEEDED'); assert.equal(s.state.readback, false); assert.equal(s.state.uncertain, true)
  s.api.getImport = async () => done(); await s.controller.resume('42'); assert.equal(s.state.readback, true); assert.equal(s.state.uncertain, false)
})
test('result unknown but still VALIDATED stays blocked until a definitive outcome', async () => {
  const s = setup({ confirmImport: async () => { throw Error('timeout') } }); await review(s); await s.controller.confirm(); await s.controller.resume('42')
  assert.equal(s.state.uncertain, true); await s.controller.prepareReview(); assert.equal(s.state.review, null)
})
test('failure before the final POST only invalidates the review and never invents an accepted write', async () => {
  const s = setup(); await review(s); s.api.getImport = async () => { throw Error('unavailable') }; await s.controller.confirm()
  assert.equal(s.state.uncertain, false); assert.equal(s.state.review, null); assert.equal(s.calls.some(r => r[0] === 'confirm'), false)
})
test('in-flight confirmation is single-flight even with repeated clicks', async () => {
  const wait = deferred(); let posts = 0; const s = setup({ confirmImport: () => { posts++; return wait.promise } })
  await review(s); const pending = s.controller.confirm(); await new Promise(r => setImmediate(r)); await s.controller.confirm()
  assert.equal(posts, 1); s.setServer(done()); wait.resolve(done()); await pending; assert.equal(s.state.readback, true)
})
test('invalid preview loads error pages and drops sensitive row snapshots', async () => {
  const s = setup({ getImportErrors: async (_id, query) => ({ list: [{ id: '1', rowNo: 4, fieldCode: 'teacherNo', message: '工号重复', snapshot: { password: 'SECRET_SENTINEL' } }], total: 23, page: query.page, pageSize: 20 }) })
  s.setServer(job({ status: 'VALIDATION_FAILED', validRows: 2, invalidRows: 1 })); await s.controller.resume('42')
  assert.equal(s.state.errors.total, 23); assert.equal(s.state.errors.rows.length, 1)
  assert.ok(!JSON.stringify(s.state.errors).includes('SECRET_SENTINEL')); await s.controller.prepareReview(); assert.equal(s.state.review, null)
})
test('error endpoint failure remains error, not a zero-error success', async () => {
  const s = setup({ getImportErrors: async () => { throw Error('error rows failed') } }); s.setServer(job({ status: 'VALIDATION_FAILED', validRows: 2, invalidRows: 1 })); await s.controller.resume('42')
  assert.equal(s.state.errors.error, 'error rows failed'); assert.equal(confirmableJob(s.state.job), false)
})
test('malformed error pagination is rejected rather than counted as complete', async () => {
  const s = setup({ getImportErrors: async () => ({ list: [], total: '0', page: 1, pageSize: 20 }) }); s.state.job = job(); await s.controller.loadErrors(1)
  assert.match(s.state.errors.error, /分页不完整/)
})
test('late first-page errors cannot overwrite a later error page', async () => {
  const wait = deferred(); const s = setup({ getImportErrors: async (_id, q) => q.page === 1 ? wait.promise : { list: [{ id: 'later', message: 'later' }], total: 30, page: 2, pageSize: 20 } })
  s.state.job = job(); const old = s.controller.loadErrors(1); await s.controller.loadErrors(2)
  wait.resolve({ list: [{ id: 'old' }], total: 30, page: 1, pageSize: 20 }); await old; assert.equal(s.state.errors.page, 2); assert.equal(s.state.errors.rows[0].id, 'later')
})
test('teacher and student pages share the production workspace while fixing identity kinds', () => {
  for (const [name, kind] of [['Teacher', 'teachers'], ['Student', 'students']]) {
    const source = fs.readFileSync(new URL(`../src/modules/system/views/System${name}ImportView.vue`, import.meta.url), 'utf8')
    assert.match(source, new RegExp(`kind="${kind}"`)); assert.match(source, /beforeRouteLeave/); assert.match(source, /beforeRouteUpdate/)
  }
})
test('production import SFC and both route entries compile without template errors', () => {
  for (const relative of ['components/workspace/IdentityImportWorkspace.vue', 'views/SystemTeacherImportView.vue', 'views/SystemStudentImportView.vue']) {
    const source = fs.readFileSync(new URL(`../src/modules/system/${relative}`, import.meta.url), 'utf8')
    const { descriptor, errors } = parse(source); assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: relative }); assert.ok(script.content)
    const result = compileTemplate({ source: descriptor.template.content, filename: relative, id: relative }); assert.deepEqual(result.errors, [])
    assert.ok(!source.includes('localStorage')); assert.ok(!source.includes('mock'))
  }
})
