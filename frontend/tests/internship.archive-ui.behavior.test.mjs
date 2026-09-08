import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'

const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/ArchiveView.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace(/ {2}components: \{[\s\S]*?ActionReceipt \},/, '').replace('export default', 'return')
const ok = data => ({ code: 0, data })
const record = () => ({ id: '9007199254740999', studentName: '测试学生', studentNo: 'UI-001', archived: false, version: null, recordVersion: 3, missing: [], archivePassed: true })
function setup(api = {}, permission = () => true) {
  const def = new Function('archiveApi', 'canCode', 'toast', script)(api, permission, { success() {}, error() {}, warning() {} })
  const targets = [], vm = { ...def.data(), ctx: {}, $route: { query: {} }, batchStore: { selectedBatchId: '1', withBatchQuery: q => ({ ...q, batchId: vm.batchStore.selectedBatchId }) }, $router: { push: t => targets.push(t), replace: t => targets.push(t), beforeEach: () => () => {} } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(def.computed)) if (key !== 'batchStore') Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, def, targets }
}
function focus(vm, data = record()) { vm.panel = { visible: true, rowId: data.id, loading: false, error: '', data }; vm.rows = [data]; return data }

test('archive template compiles', () => assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'ArchiveView.vue', id: 'archive' }).errors, []))

test('student detail, return and aggregate views preserve query filters and large IDs', () => {
  const { vm, targets } = setup(); vm.$route.query = { panel: 'materials', keyword: '测试', page: '3', pending: '0' }; vm.restoreQuery()
  assert.equal(vm.onlyIncomplete, false); assert.equal(vm.page, 3)
  vm.openDetail(record()); assert.equal(targets[0].query.id, record().id); assert.equal(targets[0].query.page, '3'); vm.$route.query = targets[0].query
  vm.closePanel(); assert.equal(targets[1].query.id, undefined); assert.equal(targets[1].query.keyword, '测试'); assert.equal(targets[1].query.pending, '0')
  vm.switchTab('enterprise'); assert.equal(targets[2].query.view, 'enterprise'); assert.equal(targets[2].query.id, undefined); assert.equal(targets[2].query.batchId, '1')
})

test('student loads use scoped bounded pending queries, and aggregate failure remains an error', async () => {
  const calls = [], { vm } = setup({ getByStudent: async q => { calls.push(q); return ok({ list: [], total: 0 }) }, byEnterprise: async () => ({ code: 1, message: '汇总失败' }) })
  vm.page = 3; vm.onlyIncomplete = true; vm.keyword = '测试'; await vm.load()
  assert.deepEqual(calls[0], { batchId: '1', page: 3, pageSize: 20, keyword: '测试', onlyPending: true })
  vm.tab = 'enterprise'; vm.aggRows = [{ group: 'old' }]; await vm.load(); assert.equal(vm.error, '汇总失败'); assert.deepEqual(vm.aggRows, [])
})

test('late lists cannot populate a different batch or replace newer filters', async () => {
  const pending = [], { vm } = setup({ getByStudent: () => new Promise(resolve => pending.push(resolve)) })
  const old = vm.load(); vm.keyword = '新筛选'; const current = vm.load(); pending[1](ok({ list: [{ id: 'new' }], total: 1 })); await current
  pending[0](ok({ list: [{ id: 'old' }], total: 99 })); await old; assert.equal(vm.rows[0].id, 'new')
})

test('direct archive links confirm current batch membership before displaying details', async () => {
  const proofs = [], data = record(), { vm } = setup({ getDetail: async () => ok(data), getByStudent: async q => { proofs.push(q); return ok({ list: [data] }) } })
  await vm.openDetailById(data.id); assert.equal(vm.panel.data.id, data.id)
  assert.deepEqual(proofs[0], { batchId: '1', keyword: 'UI-001', page: 1, pageSize: 20 })
  const { vm: outside } = setup({ getDetail: async () => ok(data), getByStudent: async () => ok({ list: [] }) }); await outside.openDetailById(data.id)
  assert.equal(outside.panel.data, null); assert.match(outside.panel.error, /当前批次/); assert.equal(outside.panel.visible, true)
})

test('missing detail stays in its workspace with retry instead of disappearing', async () => {
  const { vm } = setup({ getDetail: async () => ({ code: 1, message: '实习记录不存在' }) }); await vm.openDetailById('0')
  assert.equal(vm.panel.visible, true); assert.equal(vm.panel.error, '实习记录不存在'); assert.equal(vm.panel.rowId, '0')
})

test('a closed or switched workspace ignores late detail and preflight responses', async () => {
  let finish
  const { vm } = setup({ getDetail: () => new Promise(resolve => { finish = resolve }), preflight: () => new Promise(resolve => { finish = resolve }) })
  const old = vm.openDetailById(record().id); vm.resetPanel(); finish(ok(record())); await old; assert.equal(vm.panel.data, null)
  focus(vm); const preflight = vm.runPreflight(vm.panel.data); vm.viewEpoch++; vm.resetPanel(); finish(ok({ ...record(), canArchive: true })); await preflight
  assert.equal(vm.panel.visible, false); assert.equal(vm.lastReceipt, null)
})

test('archive preflight blocks duplicate requests and does not confirm an unsafe record', async () => {
  let finish, calls = 0
  const { vm } = setup({ preflight: () => { calls++; return new Promise(resolve => { finish = resolve }) } }); const data = focus(vm)
  const pending = vm.doArchive(data); await vm.doArchive(data); assert.equal(calls, 1)
  finish(ok({ ...data, canArchive: false, missingActions: [], fileVersionSafety: { unsafe: 1, ready: 0, total: 1 } })); await pending
  assert.equal(vm.cd.visible, false); assert.match(vm.lastReceipt.objectLabel, /仍有归档阻断/); assert.doesNotMatch(vm.lastReceipt.objectLabel, /缺 0/)
})

test('archive confirmation uses preflight versions and conflict never retries with refreshed versions', async () => {
  const writes = [], data = record(), { vm } = setup({ preflight: async () => ok({ ...data, canArchive: true }), archive: async (id, body) => { writes.push({ id, body }); return { code: 409, message: '版本冲突' } }, getDetail: async () => ok({ ...data, recordVersion: 4 }) })
  focus(vm); await vm.doArchive(data); await vm.onConfirm({}); assert.equal(writes.length, 1)
  assert.deepEqual(writes[0], { id: data.id, body: { force: false, expectedVersion: 3, recordExpectedVersion: 3 } })
  assert.equal(vm.panel.data.recordVersion, 4); assert.equal(vm.pending.recordExpectedVersion, 3); assert.equal(vm.actionConflict, true)
  await vm.onConfirm({}); assert.equal(writes.length, 1); vm.cd.visible = false; vm.acknowledgeLatest(); assert.equal(vm.actionConflict, false); assert.equal(vm.pending, null)
})

test('revoke checks exact permission, requires a reason and retains it after failed write', async () => {
  const codes = [], data = { ...record(), archived: true, version: 2 }, { vm } = setup({ revoke: async () => ({ code: 409, message: '撤销冲突' }), getDetail: async () => ok({ ...data, version: 3 }) }, (_, code) => { codes.push(code); return true })
  focus(vm, data); vm.doRevoke(data); assert.ok(codes.includes('internship.archive.revoke'))
  await vm.onConfirm({ reason: '短' }); assert.match(vm.actionError, /5 字/)
  await vm.onConfirm({ reason: '需要补充材料重新核验' }); assert.equal(vm.keptReason, '需要补充材料重新核验'); assert.equal(vm.pending.expectedVersion, 2); assert.equal(vm.actionConflict, true)
})

test('successful archive reads the list and selected object back without retaining pending confirmation', async () => {
  const data = record(), archived = { ...data, archived: true, version: 1, recordVersion: 4 }
  const { vm } = setup({ preflight: async () => ok({ ...data, canArchive: true }), archive: async () => ok({ recordVersion: 4, operationReceipt: { status: 'COMMITTED' } }), getByStudent: async () => ok({ list: [archived], total: 1 }), getDetail: async () => ok(archived) })
  focus(vm); await vm.doArchive(data); await vm.onConfirm({}); await Promise.resolve()
  assert.equal(vm.cd.visible, false); assert.equal(vm.pending, null); assert.equal(vm.panel.data.archived, true); assert.equal(vm.lastReceipt.status, 'COMMITTED')
})

test('material links keep batch and cannot mistake an internship ID for a score or evaluation ID', () => {
  const { vm, targets } = setup(); focus(vm)
  vm.goFix({ code: 'score', path: '/admin/internship/scores?stage=publish&id=9007199254740999' })
  assert.equal(targets[0].query.id, undefined); assert.equal(targets[0].query.keyword, '测试学生'); assert.equal(targets[0].query.batchId, '1'); assert.equal(targets[0].query.stage, 'publish')
  vm.goFix({ code: 'enterpriseEval', path: '/admin/internship/evaluations?stage=enterprise&id=9007199254740999' }); assert.equal(targets[1].path, '/admin/internship/enterprise-evals'); assert.equal(targets[1].query.id, undefined)
  vm.goFix({ code: 'visit', path: '/admin/internship/visits?id=9007199254740999' }); assert.equal(targets[2].path, '/admin/internship/guidance'); assert.equal(targets[2].query.view, 'visit')
  vm.goFix({ path: 'https://outside.invalid' }); assert.equal(targets.length, 3)
})

test('agreement missing-item navigation keeps in-progress statuses and the exact archive origin', () => {
  const { vm, targets } = setup(); focus(vm)
  vm.$route.fullPath = '/admin/internship/archive?batchId=1&id=9007199254740999&page=2'
  vm.goFix({ code: 'agreement', path: '/admin/internship/agreements?id=9007199254740999' })
  assert.equal(targets[0].query.id, undefined)
  assert.equal(targets[0].query.panel, 'audit-ledger')
  assert.equal(targets[0].query.status, '')
  assert.equal(targets[0].query.returnTo, vm.$route.fullPath)
  assert.equal(targets[0].query.batchId, '1')
})

test('missing permission or archived preconditions prevent package and employment operations', async () => {
  const denied = () => assert.fail('unauthorized request')
  const { vm } = setup({ buildPackage: denied, downloadPackage: denied, verifyRestore: denied, employmentTransition: denied, exportArchives: denied }, () => false)
  focus(vm, { ...record(), archived: true }); vm.pkgFile = { packageId: '99' }
  await vm.buildPackage(); await vm.downloadPackage(); await vm.verifyRestore(); await vm.goEmployment(); assert.notEqual((await vm.exportFn()).code, 0)
})

test('late package results cannot attach to a different student or batch', async () => {
  let finish
  const { vm } = setup({ buildPackage: () => new Promise(resolve => { finish = resolve }), buildBatchPackage: () => new Promise(resolve => { finish = resolve }) })
  focus(vm, { ...record(), archived: true }); const old = vm.buildPackage(); vm.resetPanel(); finish(ok({ packageId: 'old' })); await old; assert.equal(vm.pkgFile, null)
  const batch = vm.buildBatchPackage(); vm.viewEpoch++; vm.resetPanel(); finish(ok({ packageId: 'old-batch' })); await batch; assert.equal(vm.batchPackage, null)
})

test('unmount invalidates inflight reads and removes the local busy navigation guard', async () => {
  let finish, removed = false
  const { vm, def } = setup({ getByStudent: () => new Promise(resolve => { finish = resolve }) }); vm.removeRouteGuard = () => { removed = true }
  const old = vm.load(); def.beforeUnmount.call(vm); finish(ok({ list: [record()], total: 1 })); await old
  assert.equal(removed, true); assert.deepEqual(vm.rows, [])
})

test('aggregate export does not silently reuse the hidden student filter', async () => {
  const calls = [], { vm } = setup({ exportArchives: async q => { calls.push(q); return ok({ filename: '归档.xlsx' }) } })
  vm.keyword = '测试学生'; await vm.exportFn(); vm.tab = 'enterprise'; await vm.exportFn()
  assert.deepEqual(calls, [{ keyword: '测试学生', batchId: '1' }, { keyword: undefined, batchId: '1' }])
})
