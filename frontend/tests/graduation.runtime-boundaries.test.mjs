import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'

const apiUrl = new URL('../src/modules/graduation/api/graduation-defense-grade.api.js', import.meta.url)
const apiSource = fs.readFileSync(apiUrl, 'utf8')
  .replace(/^import .*\n/gm, '')
  .replace(/\bexport const /g, 'const ')
  .replace(/^export default .*$/gm, '')

// Execute the production adapter; only transport and auth dependencies are
// doubles. These tests are not evidence of real database or browser execution.
function apiHarness({ permissions = ['graduationDesign.plagiarism.result'], batchId = '42' } = {}) {
  const requests = []
  const context = {
    request: async (url, options) => {
      requests.push({ url, options })
      return { id: '17', status: 'DONE', rate: `${options.body.rate}%` }
    },
    useGraduationBatchStore: () => ({ selectedBatchId: batchId }),
    getPermissionPatterns: () => permissions,
    matchPermission: (patterns, permission) => patterns.includes(permission)
  }
  const api = vm.runInNewContext(`${apiSource}\n;graduationDefenseGradeApi`, context, { timeout: 1000 })
  return { api, requests }
}

for (const [input, expected] of [[12, '12'], [0, '0'], [100, '100'], [12.5, '12.5'], [' 12.50% ', '12.50']]) {
  test(`plagiarism adapter transports ${JSON.stringify(input)} as the frozen string DTO`, async () => {
    const h = apiHarness()
    const result = await h.api.setPlagiarismResult('17', input, 'https://school.example/report')
    assert.equal(result.code, 0)
    assert.equal(h.requests.length, 1)
    const { url, options } = h.requests[0]
    assert.equal(url, '/graduation/gd-plagiarism/17/result')
    assert.equal(options.method, 'POST')
    assert.equal(options.params.batchId, '42')
    assert.equal(typeof options.body.rate, 'string')
    assert.equal(options.body.rate, expected)
    assert.equal(options.body.reportUrl, 'https://school.example/report')
  })
}

test('plagiarism adapter rejects blank, non-finite and out-of-range values before transport', async () => {
  for (const value of ['', '  ', '%', null, undefined, NaN, Infinity, -1, 101, true, {}, '12x']) {
    const h = apiHarness()
    const result = await h.api.setPlagiarismResult('17', value)
    assert.equal(result.code, 'VALIDATION_ERROR', `unexpected result for ${String(value)}`)
    assert.equal(h.requests.length, 0)
  }
})

test('plagiarism type normalization never bypasses the original permission or batch gate', async () => {
  for (const options of [{ permissions: [] }, { batchId: '' }, { permissions: null }]) {
    const h = apiHarness(options)
    const result = await h.api.setPlagiarismResult('17', 12)
    assert.notEqual(result.code, 0)
    assert.equal(h.requests.length, 0)
  }
})

const gateUrl = new URL('../../scripts/check/check-graduation-browser-architecture.mjs', import.meta.url)
const scenarioPath = fileURLToPath(new URL('../../e2e/lib/graduation-scenario-fixture.mjs', import.meta.url))
const gateSource = fs.readFileSync(gateUrl, 'utf8')
  .replace(/^#!.*\n/, '')
  .replace(/^import .*\n/gm, '')
  .replaceAll('import.meta.url', 'entryUrl')
const scenarioSource = fs.readFileSync(scenarioPath, 'utf8')

function runGate(scenario = scenarioSource) {
  const result = []
  // Run the unchanged gate except for an in-memory mutation of its scenario
  // input. No repository file, Gold baseline, or runtime permission is changed.
  vm.runInNewContext(gateSource, {
    assert: { ...assert, deepEqual: (actual, expected, message) =>
      assert.deepEqual(JSON.parse(JSON.stringify(actual)), JSON.parse(JSON.stringify(expected)), message) },
    fs: { ...fs, readFileSync: (target, ...args) =>
      String(target) === scenarioPath ? scenario : fs.readFileSync(target, ...args) },
    path, fileURLToPath, entryUrl: gateUrl.href,
    process: { exitCode: 0 },
    console: { log: value => result.push(value), error: () => {} }
  }, { timeout: 5000 })
  return result
}

test('browser architecture gate accepts the actual strengthened exact-final scenario', () => {
  const output = runGate()
  assert.ok(output.some(line => String(line).includes('"status": "GREEN"')))
})

for (const [name, from, to] of [
  ['server read', 'record = relevant(await readRows())', 'record = receipt'],
  ['exact check id', "String(record?.id) === checkId && record.status === 'DONE'", "record.status === 'DONE'"],
  ['done state', "&& record.status === 'DONE'", "&& record.status === 'CHECKING'"],
  ['threshold', '&& record.overThreshold === false', '&& true'],
  ['saved rate', "&& Number(String(record.rate).replace('%', '')) === 12", '&& true'],
  ['final identity', "String(item.gdFinalId || '') === String(row.id)", 'true'],
  ['student identity', "String(item.gdStudentId || '') === String(fixture.gdStudentId)", 'true'],
  ['awaited prerequisite', "if (finalType(row) === '定稿') await ensurePlagiarismCompleted(page, fixture, row)", "if (finalType(row) === '定稿') void ensurePlagiarismCompleted(page, fixture, row)"]
]) {
  test(`browser architecture gate rejects removal of ${name}`, () => {
    assert.ok(scenarioSource.includes(from), `mutation target missing: ${name}`)
    const mutated = scenarioSource.replaceAll(from, to)
    assert.throws(() => runGate(mutated), /plagiarism|final approval/i)
  })
}
