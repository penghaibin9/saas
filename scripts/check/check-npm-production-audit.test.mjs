import assert from 'node:assert/strict'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import test from 'node:test'

const script = new URL('./check-npm-production-audit.mjs', import.meta.url)

function run({ report, waivers = [], app = 'frontend' }) {
  const dir = mkdtempSync(path.join(tmpdir(), 'npm-prod-audit-'))
  const reportPath = path.join(dir, 'audit.json')
  const waiverPath = path.join(dir, 'waivers.json')
  writeFileSync(reportPath, JSON.stringify(report))
  writeFileSync(waiverPath, JSON.stringify({ version: 1, waivers }))
  return spawnSync(process.execPath, [script.pathname, reportPath, app, waiverPath], {
    encoding: 'utf8',
  })
}

function audit(vulnerabilities = {}) {
  const counts = { info: 0, low: 0, moderate: 0, high: 0, critical: 0, total: 0 }
  for (const value of Object.values(vulnerabilities)) {
    const severity = String(value.severity || '').toLowerCase()
    if (severity in counts) counts[severity] += 1
    counts.total += 1
  }
  return { auditReportVersion: 2, vulnerabilities, metadata: { vulnerabilities: counts } }
}

test('clean production dependency graph passes', () => {
  const result = run({ report: audit() })
  assert.equal(result.status, 0, result.stderr)
  assert.match(result.stdout, /production runtime dependency gate passed/)
})

test('unwaived production high or critical vulnerability fails closed', () => {
  const result = run({ report: audit({
    vulnerable_runtime: { severity: 'high', via: [{ source: 12345, title: 'runtime advisory' }] },
  }) })
  assert.equal(result.status, 1)
  assert.match(result.stderr, /BLOCKED high vulnerable_runtime/)
})

test('narrow non-expired waiver may temporarily admit exactly one package and severity', () => {
  const result = run({
    report: audit({ vulnerable_runtime: { severity: 'high', via: ['transitive-package'] } }),
    waivers: [{
      app: 'frontend', package: 'vulnerable_runtime', severity: 'high',
      reason: 'Upstream fixed release is scheduled and runtime exposure is mitigated.',
      expires: '2099-12-31',
    }],
  })
  assert.equal(result.status, 0, result.stderr)
  assert.match(result.stdout, /WAIVED high vulnerable_runtime/)
})

test('expired, wrong-app, wrong-package or weak-reason waivers never open the gate', () => {
  const cases = [
    { app: 'frontend', package: 'vulnerable_runtime', severity: 'high', reason: 'expired exception with owner', expires: '2020-01-01' },
    { app: 'miniapp', package: 'vulnerable_runtime', severity: 'high', reason: 'wrong application cannot authorize this graph', expires: '2099-12-31' },
    { app: 'frontend', package: 'other', severity: 'high', reason: 'wrong package cannot authorize this graph', expires: '2099-12-31' },
    { app: 'frontend', package: 'vulnerable_runtime', severity: 'high', reason: 'short', expires: '2099-12-31' },
  ]
  for (const waiver of cases) {
    const result = run({
      report: audit({ vulnerable_runtime: { severity: 'high', via: ['transitive-package'] } }),
      waivers: [waiver],
    })
    assert.equal(result.status, 1, JSON.stringify(waiver))
  }
})
