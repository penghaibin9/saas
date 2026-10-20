import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { findActiveInPlan, getVisibleNavPlan } from '../src/config/navPlan.js'
import { workspaceCurrentPage, workspacePages } from '../src/components/workspace/teacherWorkspace.js'
const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/InternshipMaterialCenterView.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content.replace(/^import[^\n]+\r?\n/gm, '').replace(/^ {2}components:.*\r?\n/m, '').replace('export default', 'return')
const file = (fileId = '9007199254740999', safe = true) => ({ fileId, versionId: '9007199254740998', versionNo: 2, fileName: '测试材料.pdf', canPreview: safe, canDownload: safe, readyForBusiness: safe })
const detail = (id = '2', items = [file()]) => ({ internshipId: id, batchId: '1', studentName: '测试学生', items, summary: { total: items.length, ready: items.filter(f => f.readyForBusiness).length, unsafe: items.filter(f => !f.readyForBusiness).length }, manifest: null })
function setup(api = {}, permission = () => true) {
  const def = new Function('internshipMaterialCenterApi', 'canCode', 'toast', script)({ createPreviewProvider: () => ({}), ...api }, permission, { warning() {} })
  const targets = [], vm = { ...def.data(), ctx: {}, batchStore: { selectedBatchId: '1', withBatchQuery: q => ({ ...q, batchId: vm.batchStore.selectedBatchId }) }, $route: { query: {} }, $router: { push: t => targets.push(t), replace: t => targets.push(t) } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(def.computed)) if (key !== 'batchStore') Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, def, targets }
}
test('material center template compiles', () => assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'MaterialCenter.vue', id: 'material' }).errors, []))
test('student and file links preserve query filters and return without losing pagination', () => {
  const { vm, targets } = setup(); vm.$route.query = { keyword: '测试', safetyStatus: 'READY', page: '3' }; vm.restoreQuery(); assert.equal(vm.page, 3)
  vm.openStudent({ internshipId: '9007199254740999' }); assert.equal(targets[0].query.id, '9007199254740999'); assert.equal(targets[0].query.page, '3')
  vm.$route.query = { ...targets[0].query, file: file().fileId }; vm.closePreview(); assert.equal(targets[1].query.file, undefined); assert.equal(targets[1].query.id, '9007199254740999')
  vm.closeStudent(); assert.equal(targets[2].query.id, undefined); assert.equal(targets[2].query.safetyStatus, 'READY')
})
test('detail stays selected even outside the current list page, without auto-previewing files', async () => {
  const { vm } = setup({ detail: async () => detail(), list: async () => ({ items: [], total: 50 }) }); vm.selectedId = '2'; await vm.refreshDetail(); await vm.load()
  assert.equal(vm.selected.internshipId, '2'); assert.equal(vm.activePreviewFileId, ''); assert.equal(vm.total, 50)
})
test('detail refresh restores a safe file link and refuses unavailable files instead of switching silently', async () => {
  const { vm } = setup({ detail: async () => detail() }); vm.selectedId = '2'; vm.$route.query = { file: file().fileId }; await vm.refreshDetail(); assert.equal(vm.activePreviewFile.fileId, file().fileId)
  vm.$route.query.file = 'missing'; vm.restorePreview(); assert.equal(vm.activePreviewFile, null); assert.equal(vm.previewRequested, true)
})
test('cross-batch or mismatched object responses are not displayed', async () => {
  const { vm } = setup({ detail: async () => ({ ...detail(), batchId: '2' }) }); vm.selectedId = '2'; await vm.refreshDetail(); assert.equal(vm.selected, null); assert.match(vm.detailError, /不属于当前批次/)
})
test('a failed refresh clears previous student facts and provides a retry state', async () => {
  const { vm } = setup({ detail: async () => { throw new Error('读取失败') } }); vm.selectedId = '2'; vm.selected = detail(); await vm.refreshDetail()
  assert.equal(vm.selected, null); assert.equal(vm.detailLoading, false); assert.equal(vm.detailError, '读取失败')
})
test('late list and detail responses cannot restore a previous batch or student', async () => {
  let finishList, finishDetail
  const { vm } = setup({ list: () => new Promise(r => { finishList = r }), detail: () => new Promise(r => { finishDetail = r }) }); vm.selectedId = '2'
  const list = vm.load(), read = vm.refreshDetail(); vm.epoch++; vm.clearDetail(); vm.selectedId = '3'; finishList({ items: [{ internshipId: '2' }], total: 1 }); finishDetail(detail()); await Promise.all([list, read])
  assert.deepEqual(vm.rows, []); assert.equal(vm.selected, null)
})
test('empty materials are not shown as passing safety checks', () => { const { vm } = setup(); vm.selected = detail('2', []); assert.equal(vm.selectedStatus, 'NOT_SYNCED'); assert.equal(vm.statusText(vm.selectedStatus), '尚未登记材料') })
test('preview and download reject forged or unsafe objects and duplicate downloads', async () => {
  let finish, calls = 0
  const { vm, targets } = setup({ downloadMaterial: () => { calls++; return new Promise(r => { finish = r }) } }); vm.selectedId = '2'; vm.selected = detail('2', [file(), file('unsafe', false)])
  vm.previewFile(file('outside')); vm.previewFile(file('unsafe')); assert.equal(targets.length, 0)
  await vm.downloadFile(file('unsafe')); await vm.downloadFile(file('outside')); assert.equal(calls, 0)
  const one = vm.downloadFile(file()); await vm.downloadFile(file()); assert.equal(calls, 1); finish(); await one; assert.equal(vm.downloadingId, '')
})
test('sync uses archive.manage, prevents duplicates, and preserves receipt if readback fails', async () => {
  let finish, writes = 0
  const { vm } = setup({ sync: () => { writes++; return new Promise(r => { finish = r }) }, list: async () => ({ items: [], total: 0 }), detail: async () => { throw new Error('回读失败') } }); vm.selectedId = '2'; vm.selected = detail()
  const pending = vm.syncCurrent(); await vm.syncCurrent(); assert.equal(writes, 1); finish({ items: [file()], unsafe: [] }); await pending
  assert.match(vm.syncReceipt, /已同步 1/); assert.equal(vm.detailError, '回读失败'); assert.equal(vm.syncing, false)
  const { vm: denied } = setup({ sync: () => assert.fail('no sync permission') }, (_, code) => code === 'internship.archive.view'); denied.selectedId = '2'; denied.selected = detail(); await denied.syncCurrent()
})
test('late sync does not reload a new context or show a receipt for another student', async () => {
  let finish
  const { vm } = setup({ sync: () => new Promise(r => { finish = r }), list: () => assert.fail('no old-scope reload') }); vm.selectedId = '2'; vm.selected = detail(); const pending = vm.syncCurrent()
  vm.epoch++; vm.clearDetail(); finish({ items: [file()], unsafe: [] }); await pending; assert.equal(vm.syncReceipt, ''); assert.equal(vm.selected, null)
})
test('no batch or no permission prevents reads, and unmount invalidates responses', async () => {
  const { vm } = setup({ list: () => assert.fail('no unauthorized request') }, () => false); await vm.load(); assert.match(vm.error, /权限/); vm.batchStore.selectedBatchId = ''; await vm.load(); assert.match(vm.error, /选择实习批次/)
  let finish; const { vm: live, def } = setup({ detail: () => new Promise(r => { finish = r }) }); live.selectedId = '2'; const pending = live.refreshDetail(); def.beforeUnmount.call(live); finish(detail()); await pending; assert.equal(live.selected, null)
})
test('material deep links resolve to archive in the actual shared teacher shell', () => {
  const url = '/admin/internship/material-center?batchId=1&id=2&file=9007199254740999'
  assert.equal(findActiveInPlan('/admin/internship/material-center', url).modKey, 'in-employment-archive-stats')
  const modules = getVisibleNavPlan({ permissionPatterns: ['*'] }).find(g => g.key === 'internship').children
  assert.equal(workspaceCurrentPage(workspacePages(modules), url).title, '材料归档')
})

const apiScript = fs.readFileSync(new URL('../src/modules/internship/api/material-center.api.js', import.meta.url), 'utf8').replace(/^import[^\n]+\r?\n/gm, '').replace('export const internshipMaterialCenterApi', 'const internshipMaterialCenterApi').replace('export default internshipMaterialCenterApi', 'return internshipMaterialCenterApi')
test('preview cancellation returns AbortError without assigning a readonly DOMException code', async () => {
  let finish, bytes = 0
  const api = new Function('request', 'fileSdk', 'buildPreviewDescriptorFromFile', apiScript)(() => new Promise(r => { finish = r }), { blobFrom: () => { bytes++; return Promise.resolve(new Blob()) } }, f => f)
  const controller = new AbortController(), provider = api.createPreviewProvider(), pending = provider.fetchBytes({ fileId: '7' }, { signal: controller.signal })
  controller.abort(); await assert.rejects(pending, e => e.name === 'AbortError' && e.code === 'PREVIEW_ABORTED'); finish({ url: '/api/v1/example' }); await Promise.resolve(); assert.equal(bytes, 0)
  await assert.rejects(provider.fetchBytes({ fileId: '8' }, { signal: controller.signal }), e => e.name === 'AbortError')
})
