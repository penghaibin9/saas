import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const projectSource = readFileSync(new URL('../src/modules/studentAffairs/views/funding/FundingProjectView.vue', import.meta.url), 'utf8').replaceAll('\r', '')
const batchSource = readFileSync(new URL('../src/modules/studentAffairs/views/funding/FundingBatchView.vue', import.meta.url), 'utf8').replaceAll('\r', '')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

function method(source, signature, next) {
  const start = source.indexOf(`    ${signature}`)
  const end = source.indexOf(`\n    ${next}`, start)
  assert.ok(start >= 0 && end > start, `${signature} method is present`)
  return source.slice(source.indexOf('{', start + `    ${signature}`.length) + 1, end).replace(/\n {4}\},$/, '')
}

const loadProjects = new AsyncFunction('studentAffairsApi', 'toast', method(batchSource, 'async loadProjects()', 'async load()'))
const loadBatches = new AsyncFunction('studentAffairsApi', method(batchSource, 'async load()', 'applyFilters()'))
const loadCatalog = new AsyncFunction('studentAffairsApi', method(projectSource, 'async load()', 'applyFilters()'))
const changeProjectStatus = new AsyncFunction('studentAffairsApi', 'toast', method(projectSource, 'async submitStatusChange()', 'typeLabel(type)'))
const changeBatchStatus = new AsyncFunction('studentAffairsApi', 'toast', method(batchSource, 'async submitBatchAction()', 'projectName(id)'))
const openBatchForm = new Function('freshForm', method(batchSource, 'openForm()', 'async save()'))
const freshBatchForm = () => ({ projectId: '', schoolYear: '', quota: null, publicityDays: 5, publish: false, applyWindow: { start: '', end: '' } })

function page(items, total, summary = {}) {
  return { code: 0, data: { items, total, summary } }
}

test('project catalog keeps the newest server filter result and real summary', async () => {
  const pending = []
  const vm = {
    loadSeq: 0,
    page: 2,
    pageSize: 20,
    filters: { keyword: '国家奖', projectType: 'SCHOLARSHIP', status: 'ENABLED' }
  }
  const api = { getFundingProjects: params => new Promise(resolve => pending.push({ params, resolve })) }
  const first = loadCatalog.call(vm, api)
  vm.filters = { keyword: '助学金 ', projectType: 'GRANT', status: '' }
  const second = loadCatalog.call(vm, api)
  pending[1].resolve(page([{ projectId: '8' }], 41, { all: 41, byStatus: { ENABLED: 40 }, byType: { GRANT: 41 } }))
  await second
  pending[0].resolve(page([], 0, { all: 0, byStatus: {}, byType: {} }))
  await first
  assert.deepEqual(pending[0].params, { keyword: '国家奖', projectType: 'SCHOLARSHIP', status: 'ENABLED', page: 2, pageSize: 20 })
  assert.equal(pending[1].params.keyword, '助学金')
  assert.equal(vm.projects[0].projectId, '8')
  assert.equal(vm.total, 41)
  assert.equal(vm.summary.byStatus.ENABLED, 40)
  assert.equal(vm.loading, false)
})

test('project enable or disable freezes the visible version and rejects duplicate clicks', async () => {
  let finish
  const calls = []
  const vm = {
    actionBusy: false,
    statusDialog: { visible: true, target: 'DISABLED', row: { projectId: '9', version: 4, projectName: '校级奖学金' } },
    load: async () => {}
  }
  const api = { setFundingProjectStatus: (...args) => { calls.push(args); return new Promise(resolve => { finish = resolve }) } }
  const toast = { success() {}, error: assert.fail }
  const first = changeProjectStatus.call(vm, api, toast)
  vm.statusDialog.row.version = 99
  await changeProjectStatus.call(vm, api, toast)
  assert.deepEqual(calls, [['9', 'DISABLED', 4]])
  finish({ code: 0, data: { status: 'DISABLED' } })
  await first
  assert.equal(vm.statusDialog.visible, false)
  assert.equal(vm.actionBusy, false)
})

test('batch project picker reads every page and never silently selects the first project', async () => {
  const calls = []
  const api = { getFundingProjects: async ({ page, pageSize }) => {
    calls.push({ page, pageSize })
    return page === 1
      ? pageResult(Array.from({ length: 200 }, (_, i) => ({ projectId: String(i + 1), status: 'ENABLED' })), 201)
      : pageResult([{ projectId: '201', status: 'ENABLED' }], 201)
  } }
  const vm = { loadingProjects: true, projects: [] }
  await loadProjects.call(vm, api, { error: assert.fail })
  assert.equal(vm.projects.length, 201)
  assert.deepEqual(calls, [{ page: 1, pageSize: 200 }, { page: 2, pageSize: 200 }])

  const formVm = { enabledProjects: vm.projects, filters: { projectId: '' } }
  openBatchForm.call(formVm, freshBatchForm)
  assert.equal(formVm.drawer.form.projectId, '')
  formVm.filters.projectId = '201'
  openBatchForm.call(formVm, freshBatchForm)
  assert.equal(formVm.drawer.form.projectId, '201')
})

function pageResult(items, total) {
  return { code: 0, data: { items, total } }
}

test('batch catalog sends server filters and keeps the newest request', async () => {
  const pending = []
  const vm = {
    loadSeq: 0,
    page: 3,
    pageSize: 10,
    filters: { keyword: '2026', projectId: '7', status: 'DRAFT' }
  }
  const api = { getFundingBatches: params => new Promise(resolve => pending.push({ params, resolve })) }
  const first = loadBatches.call(vm, api)
  vm.filters = { keyword: '2027 ', projectId: '', status: 'OPEN' }
  const second = loadBatches.call(vm, api)
  pending[1].resolve(page([{ batchId: '21' }], 29, { all: 29, availableNow: 8, byStatus: { OPEN: 9 } }))
  await second
  pending[0].resolve(page([], 0))
  await first
  assert.deepEqual(pending[0].params, { keyword: '2026', projectId: '7', status: 'DRAFT', page: 3, pageSize: 10 })
  assert.equal(pending[1].params.keyword, '2027')
  assert.equal(vm.batches[0].batchId, '21')
  assert.equal(vm.summary.availableNow, 8)
})

test('batch publish or close submits one visible version and keeps the dialog after conflict', async () => {
  let finish
  const calls = []
  const errors = []
  const vm = {
    actionBusy: false,
    actionDialog: { visible: true, action: 'CLOSE', row: { batchId: '31', version: 6, projectName: '成长奖学金' } },
    load: () => assert.fail('failed command must preserve the reviewed context')
  }
  const api = { actFundingBatch: (...args) => { calls.push(args); return new Promise(resolve => { finish = resolve }) } }
  const toast = { success() {}, error: message => errors.push(message) }
  const first = changeBatchStatus.call(vm, api, toast)
  vm.actionDialog.row.version = 7
  await changeBatchStatus.call(vm, api, toast)
  assert.deepEqual(calls, [['31', 'CLOSE', 6]])
  finish({ code: 409, message: '批次已有变化，请刷新核对' })
  await first
  assert.equal(vm.actionDialog.visible, true)
  assert.equal(vm.actionBusy, false)
  assert.match(errors[0], /已有变化/)
})

test('new batches are drafts by default and the UI states the four-client lifecycle', () => {
  assert.match(batchSource, /publish: false/)
  assert.match(batchSource, /学生 PC 与小程序会同步看到该批次/)
  assert.match(batchSource, /已经提交的申请、补件、评审、公示和发放继续办理/)
  assert.doesNotMatch(batchSource, /projects\[0\]/)
  assert.doesNotMatch(projectSource, /AppMetricCard/)
  assert.doesNotMatch(batchSource, /AppMetricCard/)
})
