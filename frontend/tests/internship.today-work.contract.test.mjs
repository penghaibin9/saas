import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parse } from '@vue/compiler-sfc'

const dashboard = await readFile(new URL('../src/modules/internship/views/InternshipDashboardView.vue', import.meta.url), 'utf8')
const backend = await readFile(new URL('../../backend/app/modules/internship/services/internship_service.py', import.meta.url), 'utf8')

function view(api = {}) {
  const script = parse(dashboard).descriptor.script.content
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
    .replace(/ {2}components: \{[^\n]*\},\r?\n/, '')
    .replace('export default', 'return')
  const batch = { selectedBatchId: '7' }, pushes = []
  const options = new Function('internshipApi', 'useInternshipBatchStore', 'withInternshipBatch', script)(api, () => batch, (path, batchId) => ({ path, batchId }))
  const vm = { ...options.data(), ctx: { ctxKey: 'school:teacher', permissionActions: {} }, $route: { query: {} }, $router: { push: to => pushes.push(to) }, $nextTick: () => {} }
  for (const [name, method] of Object.entries(options.methods)) vm[name] = method.bind(vm)
  for (const [name, getter] of Object.entries(options.computed)) Object.defineProperty(vm, name, { get: () => getter.call(vm) })
  return { vm, batch, pushes, options }
}

test('Today Work omits duplicated overview metrics and keeps them in dedicated analytics pages', () => {
  assert.doesNotMatch(dashboard, /<ModuleHero/)
  assert.doesNotMatch(dashboard, /id="idb-batch-progress"/)
  assert.doesNotMatch(dashboard, /class="idb-progress/)
})

test('an older batch response cannot replace the current dashboard', async () => {
  let first; const requests = []
  const { vm, batch } = view({ getDashboardSummary: params => { requests.push(params); return params.batchId === '7' ? new Promise(resolve => { first = resolve }) : Promise.resolve({ code: 0, data: { batchName: '新批次' } }) } })
  vm.hero.workItems = [{ id: 'old' }]
  const old = vm.load(); assert.deepEqual(vm.hero.workItems, [])
  batch.selectedBatchId = '8'; await vm.load()
  first({ code: 0, data: { batchName: '旧批次' } }); await old
  assert.equal(vm.hero.batchName, '新批次'); assert.equal(vm.loading, false)
  assert.deepEqual(requests.map(q => q.batchId), ['7', '8'])
})

test('clearing the batch invalidates an in-flight dashboard and shows setup', async () => {
  let finish
  const { vm, batch } = view({ getDashboardSummary: () => new Promise(resolve => { finish = resolve }) })
  const old = vm.load(); batch.selectedBatchId = ''; await vm.load()
  finish({ code: 0, data: { workItems: [{ id: 'old' }] } }); await old
  assert.equal(vm.needsBatch, true); assert.equal(vm.loading, false); assert.deepEqual(vm.hero.workItems, [])
})

test('dashboard failures clear old facts and retry without pretending there are zero tasks', async () => {
  let fail = true
  const { vm } = view({ getDashboardSummary: async () => { if (fail) throw new Error('网络中断'); return { code: 0, data: { workItems: [{ id: 'new' }] } } } })
  vm.hero.workItems = [{ id: 'old' }]; await vm.load()
  assert.equal(vm.error, '网络中断'); assert.equal(vm.loading, false); assert.deepEqual(vm.hero.workItems, [])
  fail = false; await vm.load(); assert.equal(vm.error, ''); assert.equal(vm.hero.workItems[0].id, 'new')
})

test('role context change and unmount reject previous dashboard responses', async () => {
  for (const reason of ['role', 'unmount']) {
    let finish
    const { vm, options } = view({ getDashboardSummary: () => new Promise(resolve => { finish = resolve }) })
    const old = vm.load()
    if (reason === 'role') vm.ctx.ctxKey = 'school:other-role'
    else options.beforeUnmount.call(vm)
    finish({ code: 0, data: { workItems: [{ id: 'old' }] } }); await old
    assert.deepEqual(vm.hero.workItems, [])
  }
})

test('stale work items and forbidden toolbar actions cannot navigate', () => {
  const { vm, pushes } = view()
  vm.loading = false; vm.openWorkItem({ id: 'old', route: '/admin/internship/risks' })
  vm.onToolbar('createBatch'); assert.equal(pushes.length, 0)
  vm.ctx.permissionActions.createBatch = { allowed: true }; vm.onToolbar('createBatch')
  assert.deepEqual(pushes, [{ path: '/admin/internship/batches/new', batchId: '7' }])
})

test('Today Work renders the workflow and concrete objects without repeated KPI blocks or writes', () => {
  const todayIndex = dashboard.indexOf('id="idb-todos"')
  const journeyIndex = dashboard.indexOf('class="idb-journey"')
  assert.ok(journeyIndex > -1 && todayIndex > journeyIndex, '流程入口之后必须直接进入真实待办')
  assert.match(dashboard, /v-for="item in workItems"/)
  assert.match(dashboard, /\{\{ workItemTotal \}\}/)
  assert.match(dashboard, /!\['in-command-screen', 'in-workbench'\]\.includes\(item\.key\)/)
  assert.match(dashboard, /风险贯穿全程/)
  assert.match(dashboard, /item\.whyHere/)
  assert.match(dashboard, /item\.recentChange/)
  assert.match(dashboard, /item\.waitingOn/)
  assert.match(dashboard, /item\.nextActor/)
  assert.match(dashboard, /item\.receipt/)
  assert.doesNotMatch(dashboard, /internshipApi\.(review|handle|approve|publish|close)/)
})

test('dashboard projection reuses the three existing authorities and exposes continuity metadata', () => {
  for (const model of ['WeeklyReport', 'AttendanceException', 'RiskRecord']) {
    assert.match(backend, new RegExp(`select\\(${model}\\)`))
  }
  for (const field of ['whyHere', 'recentChange', 'waitingOn', 'nextActor', 'receipt', 'resumeKey', 'sourceVersion']) {
    assert.match(backend, new RegExp(`"${field}"`), `缺少 ${field}`)
  }
  assert.match(backend, /work_candidates\[:8\]/)
  assert.match(backend, /does not create\s*#?\s*another todo table/i)
})

test('missing batch is an actionable setup state rather than a load failure', () => {
  assert.match(dashboard, /v-else-if="needsBatch"/)
  assert.match(dashboard, /前往批次管理/)
  const missingBatchBranch = dashboard.slice(dashboard.indexOf('if (!this.batchStore.selectedBatchId)'), dashboard.indexOf('this.loading = true', dashboard.indexOf('if (!this.batchStore.selectedBatchId)') + 1))
  assert.match(missingBatchBranch, /this\.needsBatch = true/)
  assert.match(missingBatchBranch, /this\.error = ''/)
})

test('opening a concrete report or exception seeds the existing continuous-review queue', () => {
  assert.match(dashboard, /saveReviewQueue/)
  assert.match(dashboard, /WEEKLY_REPORT: 'weekly-report'/)
  assert.match(dashboard, /ATTENDANCE_EXCEPTION: 'attendance-exception'/)
  assert.match(dashboard, /listPath: '\/admin\/internship'/)
})
