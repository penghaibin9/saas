import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const read = path => fs.readFileSync(new URL(`../src/modules/graduation/${path}`, import.meta.url), 'utf8')
const dashboard = read('views/GraduationDashboardView.vue')
const review = read('components/GraduationDocumentReviewWorkspace.vue')
const script = source => source.match(/<script(?: setup)?>([\s\S]*?)<\/script>/)[1]
const style = source => source.match(/<style scoped>([\s\S]*?)<\/style>/)[1]
const plain = value => JSON.parse(JSON.stringify(value))

function dashboardInstance(response = { code: 0, data: {} }) {
  const store = { selectedBatchId: '71', selectedBatchName: '测试批次' }
  const pushes = [], requests = []
  const options = vm.runInNewContext(
    script(dashboard).replace(/^import .+\n/gm, '').replace('export default', 'globalThis.options ='),
    { ModulePageShell: {}, ModuleToolbar: {}, RiskTag: {}, LoadingState: {}, ErrorState: {}, EmptyState: {},
      URLSearchParams, useGraduationBatchStore: () => store,
      graduationApi: { getDashboardSummary: async params => { requests.push(params); return response } } },
    { timeout: 1000 }
  )
  const instance = { ...options.data(), ctx: { permissionActions: {} }, $router: { push: target => pushes.push(target) } }
  for (const [key, value] of Object.entries(options.methods)) instance[key] = value.bind(instance)
  for (const [key, value] of Object.entries(options.computed)) Object.defineProperty(instance, key, { get: () => value.call(instance) })
  return { instance, store, pushes, requests }
}

test('dashboard consumes the server ordering without fabricating or re-sorting work', async () => {
  const items = [{ id: 'first', priority: 'NORMAL' }, { id: 'second', priority: 'CRITICAL' }]
  const { instance, requests } = dashboardInstance({ code: 0, data: { todayWorkItems: items } })
  await instance.load()
  assert.equal(instance.firstWorkItem, items[0])
  assert.deepEqual(plain(instance.remainingWorkItems), [items[1]])
  assert.deepEqual(plain(requests), [{ batchId: '71' }])
  assert.equal(instance.error, '')
})

test('dashboard actions retain batch, selected object and source filters', () => {
  const { instance, pushes } = dashboardInstance()
  instance.goWorkItem({ primaryAction: { path: '/admin/graduation/proposals?tab=PENDING_REVIEW', query: { sel: '9', page: '2' } } })
  assert.deepEqual(plain(pushes[0]), { path: '/admin/graduation/proposals', query: { tab: 'PENDING_REVIEW', sel: '9', page: '2', batchId: '71' } })
  instance.goTodo({ id: 't3' })
  assert.deepEqual(plain(pushes[1]), { path: '/admin/graduation/finals', query: { tab: 'PENDING_REVIEW', batchId: '71' } })
})

test('dashboard unavailable and denied data never becomes a fake success', async () => {
  const { instance, requests, store } = dashboardInstance({ code: 403001, message: '范围拒绝' })
  await instance.load()
  assert.equal(instance.error, '范围拒绝')
  assert.equal(instance.firstWorkItem, null)
  store.selectedBatchId = ''
  await instance.load()
  assert.equal(requests.length, 1)
  assert.equal(instance.hasBatch, false)
  assert.deepEqual(plain(instance.hero.todayWorkItems), [])
})

test('toolbar still follows visible/allowed permission results and disabled reasons', () => {
  const { instance, store } = dashboardInstance()
  instance.ctx.permissionActions = { createBatch: { visible: false, allowed: true }, exportStats: { visible: true, allowed: false, reason: '只读' }, importStudents: { visible: true, allowed: true } }
  assert.equal(instance.toolbarActions.some(a => a.key === 'createBatch'), false)
  assert.equal(instance.toolbarActions.find(a => a.key === 'exportStats').disabledReason, '只读')
  assert.equal(instance.toolbarActions.find(a => a.key === 'exportStats').disabled, true)
  store.selectedBatchId = ''
  assert.equal(instance.toolbarActions.find(a => a.key === 'importStudents').disabled, true)
})

test('metrics are outside the priority task, not removed or hidden to meet first-fold checks', () => {
  assert.match(dashboard, /<ModulePageShell\s+class="gdb-shell"/)
  const start = dashboard.indexOf('<section class="gdb-overview gdb-work"')
  const end = dashboard.indexOf('</section>', start)
  assert.ok(dashboard.indexOf('class="gdb-kpis"') > end)
  assert.match(dashboard, /v-for="s in keyStats"/)
  assert.match(dashboard, /v-for="\(item, index\) in remainingWorkItems"/)
  assert.doesNotMatch(style(dashboard), /display:\s*none|font-size:\s*0|line-clamp|text-overflow:\s*ellipsis/)
})

function reviewInstance(submitting) {
  const calls = []
  const context = { safeLocalizedText: ({ value, dictionary, unknownLabel }) => dictionary[value] || unknownLabel,
    defineProps: () => ({ submitting }), defineEmits: () => (...args) => calls.push(args) }
  vm.runInNewContext(script(review).replace(/^import .+\n/gm, '') + '\nglobalThis.api = { emitUnlocked, queueKey }', context, { timeout: 1000 })
  return { ...context.api, calls }
}

test('all review navigation remains locked during an in-flight submission', () => {
  const locked = reviewInstance(true)
  for (const event of ['select', 'previous', 'next', 'select-file', 'select-version', 'download', 'update:autoNext', 'openStudentDossier']) locked.emitUnlocked(event, { id: 9 })
  assert.equal(locked.calls.length, 0)
  const ready = reviewInstance(false), record = { caseKey: 'case-9', id: 9 }
  ready.emitUnlocked('select', record)
  assert.equal(ready.queueKey(record, 0), 'case-9')
  assert.equal(ready.calls[0][1], record)
})

test('file-version authority, blocked states, evidence and business slots stay bound', () => {
  assert.ok(review.includes(':canonical-version-id="canonicalFileVersionId"'))
  for (const token of [':data-material-version="expectedVersion ?? \'\'"', ':data-file-version-id="canonicalFileVersionId ?? \'\'"', ':allow-download="Boolean(allowDownload && !submitting)"', 'v-if="versionConflict"', '<slot name="review" />', '<slot name="queue-footer" />', '<FileEvidencePanel', '正在提交当前审核结论']) assert.ok(review.includes(token), token)
  assert.doesNotMatch(style(review), /\.gd-scope-alert[^{}]*\{[^}]*display:\s*none/)
  assert.match(style(review), /\.gd-review-workspace__viewer\.is-command-locked\s*\{\s*pointer-events:\s*none/)
})

test('new presentation text respects the HTML font floor and uses content-width breakpoints', () => {
  for (const source of [dashboard, review]) {
    for (const match of style(source).matchAll(/font-size:\s*([\d.]+)px/g)) assert.ok(Number(match[1]) >= 11, match[0])
    assert.match(style(source), /@container /)
    assert.doesNotMatch(style(source), /\.bpl-|\.tw-|:root|\bbody\s*\{/)
  }
  for (const match of style(review).matchAll(/:global\(([^)]+)\)/g)) assert.ok(match[1].startsWith('.gd-business-view '), match[1])
  assert.match(style(review), /min-height:\s*34px/)
  assert.match(style(review), /background:\s*var\(--field-bg/)
})
