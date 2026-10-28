import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { emptyConflict, isConflict, captureConflict } from '../src/modules/internship/composables/conflictGuard.js'
import { normalizeUiError } from '../src/utils/presentationSafety.js'
import { formatDateTime } from '../src/utils/dateUtils.js'
import { workRoute, REQUIRED_PERMISSIONS } from '../src/modules/internship/components/command-screen/screen-core.mjs'
import { buildPreviewDescriptorFromFile } from '../src/components/file/viewer/viewer-contract.js'

const batchId = '9007199254740993001', id = '9007199254740993002'
const row = (version = 1, extra = {}) => ({ id, batchId, version, status: 'PENDING', statusLabel: '待审批',
  studentName: '合成学生', startDate: '2026-10-06', endDate: '2026-10-08', ...extra })
const ok = data => ({ code: 0, data })

test('请假与返岗待办按当前批次和原编号重建安全深链', () => {
  const context = { batchId, grants: { 'internship.leave.view': true, 'internship.leave.review': true } }
  for (const [kind, panel] of [['LEAVE_REVIEW', 'pending'], ['LEAVE_RETURN', 'return']]) {
    const item = { kind, objectId: id, route: 'https://example.invalid/private', batchId: 'other-batch' }
    assert.equal(workRoute(item, context), `/admin/internship/leaves?batchId=${batchId}&id=${id}&panel=${panel}`)
  }
  assert.ok(REQUIRED_PERMISSIONS.includes('internship.leave.review'))
})

test('请假待办拒绝缺少办理权限、不可信编号及授权来源故障', () => {
  const item = { kind: 'LEAVE_REVIEW', objectId: id }
  assert.equal(workRoute(item, { batchId, grants: { 'internship.leave.view': true } }), null)
  assert.equal(workRoute(item, { batchId, grants: { 'internship.leave.review': true } }), null)
  const context = { batchId, grants: { 'internship.leave.view': true, 'internship.leave.review': true } }
  assert.equal(workRoute(item, { ...context, accessHealthy: false }), null)
  assert.equal(workRoute({ ...item, objectId: '../1' }, context), null)
})

test('学校今日工作使用规范原单路由，保留中文类型与全部记录入口', () => {
  const source = fs.readFileSync(new URL('../src/modules/internship/views/InternshipDashboardView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*? from [^\n]+\n/gm, '').replace('export default', 'return')
  const imported = [...source.matchAll(/^import ([\s\S]*?) from [^\n]+$/gm)].flatMap(([, names]) => names.replace(/[{}]/g, '').split(',').map(name => name.trim()))
  const store = { selectedBatchId: batchId }, routes = []
  const deps = { workRoute, REQUIRED_PERMISSIONS, useInternshipBatchStore: () => store,
    matchPermission: (patterns, code) => patterns.includes(code), withInternshipBatch: path => path }
  const component = new Function(...imported, script)(...imported.map(name => deps[name] ?? {}))
  const item = { kind: 'LEAVE_RETURN', objectId: id, route: 'https://example.invalid/private' }
  const vm = { ...component.data(), loading: false, hero: { workItems: [item] }, workFilter: 'LEAVE_RETURN',
    ctx: { permissionPatterns: ['internship.leave.view', 'internship.leave.review'] }, $router: { push: path => routes.push(path) } }
  for (const [name, method] of Object.entries(component.methods)) vm[name] = (...args) => method.apply(vm, args)
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: () => getter.call(vm) })
  vm.openWorkItem(item)
  assert.deepEqual(routes, [`/admin/internship/leaves?batchId=${batchId}&id=${id}&panel=return`])
  assert.equal(vm.workKindLabel(item.kind), '返岗待确认')
  assert.equal(vm.activeQueue.path, '/admin/internship/leaves?panel=return')
  vm.ctx.moduleAccessHealthy = false; vm.openWorkItem(item)
  assert.equal(routes.length, 1); assert.equal(vm.activeQueue, null)
  vm.ctx.moduleAccessHealthy = true; vm.ctx.permissionServiceError = '授权暂不可用'; vm.openWorkItem(item)
  assert.equal(routes.length, 1); assert.equal(vm.activeQueue, null)
  vm.ctx.permissionServiceError = ''
  vm.ctx.permissionPatterns = ['internship.leave.view']; vm.openWorkItem(item)
  assert.equal(routes.length, 1)
})
function deferred() { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
function page(overrides = {}) {
  const source = fs.readFileSync(new URL('../src/modules/internship/views/LeaveReviewView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*? from [^\n]+\n/gm, '').replace('export default', 'return')
  const imported = [...source.matchAll(/^import ([\s\S]*?) from [^\n]+$/gm)].flatMap(([, names]) => names.replace(/[{}]/g, '').split(',').map(name => name.trim()))
  let generation = 0
  const store = { selectedBatchId: batchId, withBatchQuery: query => ({ ...query, batchId: store.selectedBatchId }) }
  const messages = [], navigations = [], downloads = [], urls = [], revoked = []
  const deps = { emptyConflict, isConflict, captureConflict, normalizeUiError, formatDateTime, buildPreviewDescriptorFromFile, currentSessionGeneration: () => generation,
    canCode: (ctx, code) => !(ctx.deniedPermissions || []).includes(code), useInternshipBatchStore: () => store, REJECT_LEAVE: [],
    toast: { error: message => messages.push(message), success: message => messages.push(message) },
    leaveApi: { getLeaveDetail: async () => ok(row()), getLeaves: async () => ok({ list: [], total: 0 }),
      getReturnQueue: async () => ok({ list: [] }), review: async () => ok(row(2, { status: 'APPROVED' })),
      ackReturn: async () => ok(row(3, { status: 'RETURNED', returnAcknowledged: true })),
      markEvidenceViewed: async (_, body) => ok({ id, version: body.expectedVersion, evidenceFileId: body.evidenceFileId }), ...overrides },
    guidanceVisitApi: { downloadAttachment: async () => downloads.push('legacy') },
    requestBlob: async () => new Uint8Array([1]),
    fileSdk: { metadata: async fileId => ({ fileId, canPreview: true }), blob: async () => new Uint8Array([1]) },
    FilePreviewer: {}, document: { hidden: false, addEventListener() {}, removeEventListener() {},
      body: { appendChild() {} }, createElement: () => ({ click: () => downloads.push('save'), remove() {} }) },
    URL: { createObjectURL: () => { const url = 'blob:fixture-' + urls.length; urls.push(url); return url }, revokeObjectURL: url => revoked.push(url) } }
  const exportSource = fs.readFileSync(new URL('../src/utils/xlsxDownload.js', import.meta.url), 'utf8').match(/export function prepareXlsxDownload\([\s\S]*?\n}/)[0].replace('export ', '')
  deps.prepareXlsxDownload = new Function('URL', 'base64ToBlob', exportSource + '\nreturn prepareXlsxDownload')(deps.URL, content => content)
  const names = [...new Set([...imported, 'document', 'URL'])]
  const downloadSource = fs.readFileSync(new URL('../src/modules/internship/api/guidance-visit.api.js', import.meta.url), 'utf8').match(/export async function downloadAttachment\([\s\S]*?\n}/)[0].replace('export ', '')
  deps.guidanceVisitApi.downloadAttachment = new Function('requestBlob', 'document', 'URL', downloadSource + '\nreturn downloadAttachment')(fileId => deps.requestBlob(fileId), deps.document, deps.URL)
  const component = new Function(...names, script)(...names.map(name => deps[name] ?? {}))
  const vm = { ...component.data(), ctx: { ctxKey: 'school-role' },
    $route: { path: '/admin/internship/leaves', query: { batchId, id } },
    $router: { replace: value => navigations.push(value) } }
  for (const [name, method] of Object.entries(component.methods)) vm[name] = (...args) => method.apply(vm, args)
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: () => getter.call(vm) })
  vm.selectedId = id; vm.detail.data = row()
  return { vm, component, store, api: deps.leaveApi, messages, navigations, downloads, urls, revoked, deps, switchAccount: () => generation++ }
}

const ledger = (count = 1) => ok({ filename: '请假审批台账.xlsx', contentBase64: 'UEs=', mediaType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', rowCount: count, totalRows: count, exportedRows: count, truncated: false })

test('四个视图查询与导出共用已查询条件，未查询输入不进入导出', async () => {
  for (const panel of ['pending', 'approved', 'all', 'return']) {
    const calls = []
    const p = page({ getLeaves: async params => { calls.push(['list', params]); return ok({ list: [], total: 1 }) }, exportLeaves: async params => { calls.push(['export', params]); return ledger() } })
    p.vm.activePanel = panel; p.vm.keyword = '合成学生'; p.vm.statusFilter = panel === 'return' || panel === 'all' ? '' : panel === 'pending' ? 'PENDING' : 'APPROVED'
    await p.vm.reload(); p.vm.keyword = '尚未查询草稿'
    assert.equal(await p.vm.exportFn(), true)
    const [, listed] = calls.find(call => call[0] === 'list'), [, exported] = calls.find(call => call[0] === 'export')
    const { page: _, pageSize: __, ...filters } = listed
    assert.deepEqual(exported, filters); assert.equal(exported.keyword, '合成学生'); assert.equal(exported.returnPending, panel === 'return')
    assert.equal(p.vm.exportFile.rowCount, 1); assert.equal(p.urls.length, 1)
    assert.equal(p.downloads.length, 0)
  }
})

test('无导出权限不请求，撤权后不生成文件；完整生成后上下文切换撤销地址', async () => {
  const delayed = deferred(); let calls = 0
  const p = page({ exportLeaves: async () => { calls++; return delayed.promise } })
  p.vm.ctx.deniedPermissions = ['internship.leave.export']; await p.vm.exportFn(); assert.equal(calls, 0)
  p.vm.ctx.deniedPermissions = []; const pending = p.vm.exportFn()
  p.vm.ctx.deniedPermissions = ['internship.leave.export']; delayed.resolve(ledger()); await pending
  assert.equal(p.urls.length, 0); assert.equal(p.vm.exporting, false)
  p.vm.ctx.deniedPermissions = []; p.api.exportLeaves = async () => ledger(25); await p.vm.exportFn()
  assert.equal(p.vm.exportFile.rowCount, 25); assert.equal(p.vm.exportFile.filename, '请假审批台账.xlsx')
  p.vm.resetContext(); assert.equal(p.vm.exportFile, null); assert.deepEqual(p.revoked, p.urls)
})

test('旧生成结束不能解除新生成锁；过期成功和错误都不污染当前回执', async () => {
  const old = deferred(), latest = deferred(); let calls = 0
  const p = page({ exportLeaves: () => (++calls === 1 ? old : latest).promise })
  const first = p.vm.exportFn(); p.vm.resetContext(); const second = p.vm.exportFn()
  old.resolve({ code: 503001, message: '旧页面错误' }); await first
  assert.equal(p.vm.exporting, true); assert.equal(p.vm.exportError, '')
  latest.resolve(ledger()); await second; assert.equal(p.vm.exporting, false); assert.equal(p.urls.length, 1)
  for (const invalidate of [p => p.store.selectedBatchId = 'other', p => p.switchAccount(), p => p.vm.activePanel = 'return', p => p.vm.appliedFilters.keyword = '新条件', p => { p.deps.document.hidden = true; p.vm.visibilityChanged() }, p => { p.vm.disposed = true; p.vm.resetContext() }]) {
    const result = deferred(), q = page({ exportLeaves: () => result.promise })
    const request = q.vm.exportFn(); invalidate(q); result.resolve(ledger()); await request
    assert.equal(q.urls.length, 0); assert.equal(q.vm.exportFile, null); assert.equal(q.vm.exportError, '')
  }
})

test('不完整台账不能创建链接，失败显示可重试中文错误；地址恢复条件与页码', async () => {
  const p = page({ exportLeaves: async () => ok({ ...ledger().data, truncated: true }) })
  await p.vm.exportFn(); assert.equal(p.urls.length, 0); assert.ok(p.vm.exportError.includes('不完整'))
  p.api.exportLeaves = async () => ledger(); await p.vm.exportFn(); assert.equal(p.vm.exportError, ''); assert.equal(p.urls.length, 1)
  p.vm.activePanel = 'all'; p.vm.$route.query = { batchId, panel: 'all', keyword: '000123', status: 'OVERDUE', page: '2' }; p.vm.restoreQuery()
  assert.deepEqual(p.vm.queryParams(), { batchId, keyword: '000123', status: 'OVERDUE', returnPending: false }); assert.equal(p.vm.page, 2)
  p.vm.detail.data = row(3, { status: 'OVERDUE', reviewComment: '保留审批意见', enterpriseName: '合成企业' })
  assert.equal(p.vm.hasReview, true); assert.equal(p.vm.leaveStatusLabel('WITHDRAWN'), '已撤回'); assert.equal(p.vm.leaveStatusLabel('OVERDUE'), '超期未销假')
  assert.ok(p.vm.summaryItems.some(item => item.label === '实习企业' && item.value === '合成企业'))
})

test('办理后越界页同步地址，后续原单地址变更不清除成功回执', async () => {
  const p = page({ getLeaves: async params => ok({ list: params.page === 2 ? [] : [row()], total: 1 }) })
  p.vm.page = 2; p.vm.activePanel = 'all'; p.vm.lastReceipt = { id, version: 4, statusLabel: '已驳回' }
  p.vm.$route.query = { batchId, panel: 'all', status: '', keyword: '', page: '2' }
  await p.vm.load()
  const synced = p.navigations.find(item => item.query.page === '1')
  assert.ok(synced); assert.equal(p.vm.page, 1)
  p.vm.$route.query = synced.query
  p.component.watch['$route.query'].call(p.vm, { ...synced.query, id }, synced.query)
  assert.equal(p.vm.lastReceipt.version, 4); assert.equal(p.vm.page, 1)
})

test('授权来源故障撤销已生成台账且不能再次请求', async () => {
  let calls = 0
  const p = page({ exportLeaves: async () => { calls++; return ledger() } })
  await p.vm.exportFn(); p.vm.ctx.moduleAccessHealthy = false
  p.component.watch.canExport.call(p.vm, p.vm.canExport)
  assert.equal(p.vm.exportFile, null); assert.deepEqual(p.revoked, p.urls)
  await p.vm.exportFn(); assert.equal(calls, 1)
  p.vm.ctx.moduleAccessHealthy = true; p.vm.ctx.permissionServiceError = '权限服务暂不可用'
  await p.vm.exportFn(); assert.equal(calls, 1)
})

test('同一请假单较旧详情不能覆盖较新版本', async () => {
  const first = deferred(), second = deferred(); let calls = 0
  const p = page({ getLeaveDetail: () => (++calls === 1 ? first : second).promise })
  const old = p.vm.loadDetail(id), current = p.vm.loadDetail(id)
  second.resolve(ok(row(4))); await current; first.resolve(ok(row(3))); await old
  assert.equal(p.vm.detail.data.version, 4)
})

test('旧批次办理回执不能解除新请假单的提交锁', async () => {
  const first = deferred(), second = deferred(); let calls = 0
  const p = page({ review: () => (++calls === 1 ? first : second).promise })
  p.vm.openReview(p.vm.detail.data, 'REJECT'); const old = p.vm.onConfirm({ reason: '请补充当前证明' })
  p.store.selectedBatchId = '9007199254740993009'; p.vm.selectedId = '9007199254740993010'
  p.vm.pending = null; p.vm.cd = { visible: false, submitting: false }; p.vm.conflict = emptyConflict()
  p.vm.detail.data = row(7, { id: p.vm.selectedId, batchId: p.store.selectedBatchId })
  p.vm.openReview(p.vm.detail.data, 'REJECT'); const current = p.vm.onConfirm({ reason: '核对另一原单证明' })
  first.resolve(ok(row(2, { status: 'REJECTED' }))); await old
  assert.equal(p.vm.cd.submitting, true); assert.equal(p.vm.lastReceipt, null)
  second.resolve({ code: 503001, message: '暂时不可用' }); await current
  assert.equal(p.vm.cd.submitting, false)
})

test('办理成功后列表回读失败保留回执且不冒充全部办结', async () => {
  const p = page({ getLeaves: async () => ({ code: 503001, message: '列表暂不可用' }) })
  p.vm.openReview(p.vm.detail.data, 'REJECT'); await p.vm.onConfirm({ reason: '请修改原单事由' })
  assert.equal(p.vm.lastReceipt.id, id); assert.equal(p.vm.doneHint, false)
  assert.equal(p.navigations.length, 0); assert.ok(p.vm.error)
})

test('办理成功后原单详情回读失败保留回执并停止自动续办', async () => {
  const p = page({ getLeaveDetail: async () => ({ code: 503001, message: '详情暂不可用' }) })
  p.vm.openReview(p.vm.detail.data, 'REJECT'); await p.vm.onConfirm({ reason: '请修改原单事由' })
  assert.equal(p.vm.lastReceipt.id, id); assert.equal(p.vm.doneHint, false)
  assert.equal(p.navigations.length, 0); assert.ok(p.vm.detail.error)
})

test('账号改变后迟到详情不能回填学校学生资料', async () => {
  const wait = deferred(), p = page({ getLeaveDetail: () => wait.promise })
  const reading = p.vm.loadDetail(id); p.switchAccount(); p.vm.detail = { loading: false, error: '', data: null }
  wait.resolve(ok(row(3))); await reading; assert.equal(p.vm.detail.data, null)
})

test('详情返回其他批次原单时拒绝办理', async () => {
  const p = page({ getLeaveDetail: async () => ok(row(3, { batchId: 'other' })) })
  await p.vm.loadDetail(id); assert.equal(p.vm.detail.data, null); assert.ok(p.vm.detail.error)
})

test('冲突保留意见和原版本，明确采用前不能重新提交', async () => {
  let writes = 0
  const p = page({ review: async () => { writes++; return { code: 409001, message: '原单已变化' } }, getLeaveDetail: async () => ok(row(6)) })
  p.vm.openReview(p.vm.detail.data, 'REJECT'); await p.vm.onConfirm({ reason: '请补充第二版证明说明' })
  assert.equal(p.vm.pending.expectedVersion, 1); assert.equal(p.vm.pending.reason, '请补充第二版证明说明')
  assert.equal(p.vm.conflict.kept, '请补充第二版证明说明'); assert.equal(p.vm.detail.data.version, 6)
  await p.vm.onConfirm({ reason: '请补充第二版证明说明' }); assert.equal(writes, 1)
  p.vm.adoptConflict(); assert.equal(p.vm.pending.expectedVersion, 6); assert.equal(p.vm.conflict.active, false)
})

test('证明下载返回时切换批次不保存旧文件也不登记查看', async () => {
  const wait = deferred(); let markers = 0
  const p = page({ markEvidenceViewed: async () => { markers++; return ok({}) } })
  p.deps.requestBlob = () => wait.promise
  p.vm.detail.data = row(4, { attachment: { fileId: '9007199254740993015', fileName: '合成证明.png' } })
  const download = p.vm.downloadAtt(); p.store.selectedBatchId = 'other'; wait.resolve(new Uint8Array([1])); await download
  assert.equal(p.downloads.length, 0); assert.equal(markers, 0)
})

test('证明预览实际读取字节后按冻结原版本留痕', async () => {
  let marker, bytes = 0
  const p = page({ markEvidenceViewed: async (original, body) => { marker = { original, ...body }; return ok({ id, version: body.expectedVersion, evidenceFileId: body.evidenceFileId }) } })
  p.deps.fileSdk.blob = async () => { bytes++; return new Uint8Array([2]) }
  p.vm.detail.data = row(5, { hasEvidence: true, attachment: { fileId: '9007199254740993015', fileName: '合成证明.png' } })
  await p.vm.previewAtt(); assert.equal(bytes, 0); assert.equal(p.vm.detail.data.evidenceViewed, undefined)
  await p.vm.previewProvider.fetchBytes({ fileId: '9007199254740993015' })
  assert.equal(bytes, 1); assert.equal(marker.original, id); assert.equal(marker.expectedVersion, 5)
  assert.equal(marker.batchId, batchId); assert.equal(marker.evidenceFileId, '9007199254740993015'); assert.equal(p.vm.detail.data.evidenceViewed, true)
})

test('页面卸载后旧证明读取不登记或恢复私密材料', async () => {
  const wait = deferred(); let markers = 0
  const p = page({ markEvidenceViewed: async () => { markers++; return ok({}) } })
  p.deps.fileSdk.blob = () => wait.promise
  p.vm.detail.data = row(5, { attachment: { fileId: '9007199254740993015' } }); await p.vm.previewAtt()
  const reading = p.vm.previewProvider.fetchBytes({ fileId: '9007199254740993015' })
  p.component.beforeUnmount.call(p.vm); wait.resolve(new Uint8Array([2])); await assert.rejects(reading)
  assert.equal(markers, 0); assert.equal(p.vm.detail.data, null); assert.equal(p.vm.previewFile, null)
})

test('收起证明预览后迟到字节不登记查看', async () => {
  const wait = deferred(), controller = new AbortController(); let markers = 0
  const p = page({ markEvidenceViewed: async () => { markers++; return ok({}) } })
  p.deps.fileSdk.blob = () => wait.promise
  p.vm.detail.data = row(5, { attachment: { fileId: '9007199254740993015' } }); await p.vm.previewAtt()
  const reading = p.vm.previewProvider.fetchBytes({ fileId: '9007199254740993015' }, { signal: controller.signal })
  controller.abort(); wait.resolve(new Uint8Array([2])); await assert.rejects(reading); assert.equal(markers, 0)
})

test('证明一次展开使用现有文档描述，收起后清除已冻结预览', async () => {
  const p = page()
  p.deps.fileSdk.metadata = async fileId => ({ fileId, fileName: '合成证明.png', mimeType: 'image/png', canPreview: true })
  p.vm.detail.data = row(5, { attachment: { fileId: '9007199254740993015' } })
  await p.vm.previewAtt()
  assert.equal(p.vm.previewDescriptor.fileId, '9007199254740993015')
  assert.equal(p.vm.previewDescriptor.previewKind, 'IMAGE')
  p.vm.clearPreview()
  assert.equal(p.vm.previewDescriptor, null); assert.equal(p.vm.previewProvider, null)
})

test('已确认返岗原单不能重复办理，核实说明保留在中文时间线', () => {
  const p = page(); p.vm.detail.data = row(5, { status: 'RETURNED', returnAcknowledged: true, auditTrail: [{ action: '返岗确认', detail: { note: '已核实合成学生返岗' } }] })
  p.vm.openReturn(p.vm.detail.data); assert.equal(p.vm.pending, null); assert.equal(p.vm.auditRecords[0].reason, '已核实合成学生返岗')
})

test('冲突后申请已办结时不能采用新版本重放原动作', async () => {
  const p = page({ review: async () => ({ code: 409001 }), getLeaveDetail: async () => ok(row(6, { status: 'APPROVED' })) })
  p.vm.openReview(p.vm.detail.data, 'REJECT'); await p.vm.onConfirm({ reason: '保留的退回意见' })
  p.vm.adoptConflict(); assert.equal(p.vm.conflict.active, true); assert.equal(p.vm.pending.expectedVersion, 1); assert.equal(p.vm.pending.reason, '保留的退回意见')
})
