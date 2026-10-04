// Isolated collector behavior tests. Synthetic responses are never procurement evidence.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const source = readFileSync(new URL('../g20_internship.k6.js', import.meta.url), 'utf8')
  .replace(/^import .*\r?\n/gm, '')
  .replace(/export default function \(\)/, 'function iterate()')
  .replace(/export (function|const) /g, '$1 ')

function harness({ vus = 2, sameAccount = false, validIdentity = true, businessCode = 0,
                   badJson = false, env = {}, tokenCount = vus } = {}) {
  const tokens = Array.from({ length: tokenCount }, (_, i) => `synthetic-token-${i}`)
  const added = new Map()
  class Metric {
    constructor(name) { this.name = name; added.set(name, []) }
    add(value) { added.get(this.name).push(value) }
  }
  const exec = { vu: { idInTest: 1, iterationInScenario: 0 },
    instance: { vusActive: vus }, scenario: { startTime: 100000 } }
  let now = 160100
  class Clock extends Date { static now() { return now } }
  const gets = []
  const context = {
    __ENV: { G20_BASE_URL: 'http://127.0.0.1:9999', G20_VUS: String(vus),
      G20_AUTH_TOKENS_FILE: 'synthetic.json', G20_REAL_RUN_ACK: 'YES',
      G20_PATHS: '/api/v1/internship/dashboard?batchId=1', ...env },
    open: () => JSON.stringify(tokens), Date: Clock, exec,
    Counter: Metric, Gauge: Metric, Rate: Metric, Trend: Metric,
    sleep: () => {}, check: (response, checks) => Object.values(checks).every(check => check(response)),
    http: {
      batch: requests => requests.map(request => {
        const i = Number(request.params.headers.Authorization.split('-').at(-1))
        return { status: validIdentity ? 200 : 401, json: () => ({ code: 0, data: {
          tenantId: '7', userId: `db-${sameAccount ? 1 : i + 1}`, mustChangePassword: false
        } }) }
      }),
      get: (url, params) => {
        gets.push({ url, params })
        return { status: 200, timings: { duration: 123 }, json: () => {
          if (badJson) throw new Error('synthetic HTML response')
          return { code: businessCode }
        } }
      }
    }
  }
  vm.createContext(context)
  const script = new vm.Script(`${source}\n({setup, iterate, handleSummary, options})`)
  const api = script.runInContext(context)
  return { ...api, added, exec, gets, setNow: value => { now = value } }
}

test('different tokens for one account fail formal setup before business load', () => {
  const run = harness({ vus: 5000, sameAccount: true })
  assert.throws(() => run.setup(), /distinct active database accounts/)
  assert.equal(run.added.get('g20_verified_tokens')[0], 5000)
  assert.equal(run.added.get('g20_verified_accounts')[0], 1)
  assert.equal(run.gets.length, 0)
})

test('server identity verification rejects invalid accounts', () => {
  const run = harness({ vus: 5000, validIdentity: false })
  assert.throws(() => run.setup(), /account verification failed/)
  assert.equal(run.added.get('g20_verified_accounts')[0], 0)
  assert.equal(run.gets.length, 0)
})

test('server distinct account count crosses into summary through metrics only', () => {
  const run = harness(); run.setup()
  const metrics = {
    g20_verified_tokens: { values: { value: run.added.get('g20_verified_tokens')[0] } },
    g20_verified_accounts: { values: { value: run.added.get('g20_verified_accounts')[0] } },
    g20_identity_verification_rate: { values: { rate: 1 } }
  }
  const report = run.handleSummary({ metrics })['g20-k6-summary.json']
  const summary = JSON.parse(report)
  assert.equal(summary.authIdentityCount, 2)
  assert.equal(summary.identityVerification.allVerified, true)
  assert.equal(summary.preflight.configurationAndIdentityReady, false)
  assert.equal(summary.schemaVersion, 2)
  assert.doesNotMatch(report, /synthetic-token|db-1|db-2/)
})

test('only hold-stage requests contribute measured business timing', () => {
  const run = harness()
  run.setNow(159900); run.iterate()
  assert.equal(run.added.get('g20_business_duration').length, 0)
  run.setNow(160100); run.iterate()
  assert.deepEqual(run.added.get('g20_business_duration'), [123])
  run.setNow(220100); run.iterate()
  assert.equal(run.added.get('g20_business_duration').length, 1)
})

test('concurrency samples use actual active VUs and each VU contributes once', () => {
  const run = harness({ vus: 5000 })
  run.exec.instance.vusActive = 4999
  run.iterate(); run.iterate()
  assert.deepEqual(run.added.get('g20_hold_vus'), [4999, 4999])
  assert.deepEqual(run.added.get('g20_business_users'), [1])
  assert.deepEqual(run.added.get('g20_business_requests'), [1, 1])
})

test('HTTP 200 with a failed business envelope is a failure and contributes no user', () => {
  const run = harness({ businessCode: 1 }); run.iterate()
  assert.deepEqual(run.added.get('g20_business_failure'), [true])
  assert.equal(run.added.get('g20_business_users').length, 0)
})

test('HTTP 200 with HTML in place of business JSON fails', () => {
  const run = harness({ badJson: true }); run.iterate()
  assert.deepEqual(run.added.get('g20_business_failure'), [true])
  assert.equal(run.added.get('g20_business_users').length, 0)
})

test('health readiness cannot be counted as formal business load', () => {
  assert.throws(() => harness({ vus: 5000, env: { G20_PATHS: '/health/ready' } }), /business paths/)
})

test('formal mode rejects a short window or missing explicit acknowledgement', () => {
  assert.throws(() => harness({ vus: 5000, env: { G20_HOLD: '5s' } }), /60-second/)
  assert.throws(() => harness({ vus: 5000, env: { G20_REAL_RUN_ACK: '' } }), /requires G20_REAL_RUN_ACK/)
})

test('fixed mean limit remains when operational percentiles are customized', () => {
  const run = harness({ env: { G20_P95_MS: '5000', G20_P99_MS: '6000' } })
  assert.equal(run.options.thresholds.g20_business_duration[0], 'avg<=3000')
  assert.throws(() => harness({ env: { G20_MAX_ERROR_RATE: '0' } }), /thresholds/)
})

test('string threshold status is never coerced to passing', () => {
  const run = harness()
  const summary = JSON.parse(run.handleSummary({ metrics: {
    http_req_failed: { thresholds: { 'rate<0.01': { ok: 'false' } } }
  } })['g20-k6-summary.json'])
  assert.equal(summary.thresholdStatus.http_req_failed['rate<0.01'], false)
})
