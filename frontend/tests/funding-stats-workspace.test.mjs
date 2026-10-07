import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/modules/studentAffairs/views/funding/FundingStatsView.vue', import.meta.url), 'utf8').replaceAll('\r', '')
const apiSource = readFileSync(new URL('../src/modules/studentAffairs/api/studentAffairs.api.js', import.meta.url), 'utf8').replaceAll('\r', '')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

function method(signature, next) {
  const start = source.indexOf(`    ${signature}`)
  const end = source.indexOf(`\n    ${next}`, start)
  assert.ok(start >= 0 && end > start, `${signature} method is present`)
  return source.slice(source.indexOf('{', start + `    ${signature}`.length) + 1, end).replace(/\n {4}\},$/, '')
}

const emptyStats = () => ({
  byStatus: [], byType: [], byYear: [],
  ledger: { total: 0, byStatus: [], missing: 0, attention: 0 },
  amounts: { visible: false }, scope: {}, definitions: {}
})

const load = new AsyncFunction('studentAffairsApi', 'emptyStats', method('async load()', 'openDrill(metric, title)'))
const loadDrill = new AsyncFunction('studentAffairsApi', method('async loadDrill()', 'go(path)'))

test('summary keeps the newest response and merges missing ledger fields safely', async () => {
  const pending = []
  const vm = { loadSeq: 0, loading: false, errorMessage: '', stats: emptyStats() }
  const api = { getFundingStats: () => new Promise(resolve => pending.push(resolve)) }
  const first = load.call(vm, api, emptyStats)
  const second = load.call(vm, api, emptyStats)
  pending[1]({ code: 0, data: { beneficiaryStudents: 9, ledger: { attention: 2 } } })
  await second
  pending[0]({ code: 0, data: { beneficiaryStudents: 1, ledger: { attention: 0 } } })
  await first
  assert.equal(vm.stats.beneficiaryStudents, 9)
  assert.equal(vm.stats.ledger.attention, 2)
  assert.deepEqual(vm.stats.ledger.byStatus, [])
  assert.equal(vm.loading, false)
})

test('drill freezes metric and page context and discards late responses', async () => {
  const pending = []
  const vm = {
    drill: {
      seq: 0, metric: 'BENEFICIARY', page: 1, pageSize: 20, loading: false,
      errorMessage: '', items: [], total: 0, scopeLabel: ''
    }
  }
  const api = { getFundingStatsDrill: params => new Promise(resolve => pending.push({ params, resolve })) }
  const first = loadDrill.call(vm, api)
  vm.drill.metric = 'DISBURSEMENT_ATTENTION'
  vm.drill.page = 2
  const second = loadDrill.call(vm, api)
  pending[1].resolve({ code: 0, data: { items: [{ studentNo: 'B**1' }], total: 21, scopeLabel: '全校' } })
  await second
  pending[0].resolve({ code: 0, data: { items: [{ studentNo: 'A**1' }], total: 1, scopeLabel: '旧范围' } })
  await first
  assert.deepEqual(pending[0].params, { metric: 'BENEFICIARY', page: 1, pageSize: 20 })
  assert.deepEqual(pending[1].params, { metric: 'DISBURSEMENT_ATTENTION', page: 2, pageSize: 20 })
  assert.equal(vm.drill.items[0].studentNo, 'B**1')
  assert.equal(vm.drill.total, 21)
  assert.equal(vm.drill.scopeLabel, '全校')
  assert.equal(vm.drill.loading, false)
})

test('workspace is compact, role-aware and routes every funding branch to its real ledger', () => {
  assert.doesNotMatch(source, /AppMetricCard/)
  assert.match(source, /资助成效与到账核对/)
  assert.match(source, /学生去重口径/)
  assert.match(source, /stats\.amounts\?\.visible/)
  assert.match(source, /金额汇总按权限隐藏/)
  assert.match(source, /DISBURSEMENT_ATTENTION/)
  assert.match(source, /姓名与学号已脱敏/)
  for (const path of [
    '/admin/student-affairs/funding/ledger',
    '/admin/student-affairs/funding/disbursements',
    '/admin/student-affairs/funding/work-study',
    '/admin/student-affairs/funding/loans',
    '/admin/student-affairs/funding/fee-reductions'
  ]) assert.match(source, new RegExp(path.replaceAll('/', '\\/')))
  assert.match(apiSource, /getFundingStatsDrill/)
  assert.match(apiSource, /\/student-affairs\/funding\/stats\/drill/)
})
