import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

// Run the real scenario function with read-only API doubles. Browser writes
// are deliberately trapped; these regression tests do not claim UI coverage.
const source = fs.readFileSync(new URL('../../e2e/lib/graduation-scenario-fixture.mjs', import.meta.url), 'utf8')
const start = source.indexOf('async function ensurePlagiarismCompleted(')
const end = source.indexOf('async function approveFinalInBrowser(', start)
assert.ok(start >= 0 && end > start, 'the canonical scenario helper must remain readable')
const helper = source.slice(start, end)

function harness(rows, optedIn = true) {
  const calls = []
  const context = {
    finalType: row => row.type || row.finalType,
    expect: (actual, message) => ({ toBe: expected => assert.strictEqual(actual, expected, message) }),
    process: { env: { E2E_ALLOW_DESTRUCTIVE_TESTS: optedIn ? 'true' : 'false' } },
    config: { sandboxAdmin: {} },
    loginApi: async () => ({ get: async (path, params) => {
      calls.push({ path, params })
      return rows
    } }),
    items: data => data,
    StaffLoginPage: class {
      async login() {
        calls.push('UI_REQUIRED')
        throw new Error('UI_REQUIRED')
      }
    }
  }
  vm.createContext(context)
  vm.runInContext(`${helper};globalThis.run=ensurePlagiarismCompleted`, context, { timeout: 1000 })
  return {
    run: () => context.run({}, { batchId: 'b', gdStudentId: 's' }, { id: 'f', type: '定稿' }),
    calls
  }
}

const good = {
  id: 'p', gdStudentId: 's', gdFinalId: 'f',
  status: 'DONE', overThreshold: false, disputeStatus: ''
}

test('graduation reuses only the exact completed final and student plagiarism result', async () => {
  const h = harness([{ ...good, gdFinalId: 'old' }, good])
  assert.equal(await h.run(), good)
  assert.equal(h.calls.length, 1)
  assert.equal(h.calls[0].params.batchId, 'b')
})

test('graduation prior final for the same student never authorizes current final approval', async () => {
  const h = harness([{ ...good, gdFinalId: 'old' }])
  await assert.rejects(h.run, /UI_REQUIRED/)
})

test('graduation another student cannot authorize review by a matching final id', async () => {
  const h = harness([{ ...good, gdStudentId: 'another' }])
  await assert.rejects(h.run, /UI_REQUIRED/)
})

test('graduation over-threshold result blocks without a browser write', async () => {
  const h = harness([{ ...good, overThreshold: true }])
  await assert.rejects(h.run, /over-threshold/)
  assert.equal(h.calls.length, 1)
})

test('graduation missing threshold decision is not equivalent to approval', async () => {
  const h = harness([{ ...good, overThreshold: undefined }])
  await assert.rejects(h.run, /over-threshold/)
})

test('graduation disputed result cannot be silently reused', async () => {
  const h = harness([{ ...good, disputeStatus: 'OPEN' }])
  await assert.rejects(h.run, /dispute/)
})

test('graduation failed checks are not overwritten through the normal result form', async () => {
  const h = harness([{ ...good, status: 'FAILED' }])
  await assert.rejects(h.run, /failed checks/)
  assert.equal(h.calls.length, 1)
})

test('graduation manual result preparation refuses missing isolated-test opt-in', async () => {
  const h = harness([good], false)
  await assert.rejects(h.run, /isolated test opt-in/)
  assert.equal(h.calls.length, 0)
})
