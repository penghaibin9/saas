import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const script=fileURLToPath(new URL('../scripts/check-production-audit-report.mjs',import.meta.url))

function run(content){
  const dir=mkdtempSync(path.join(tmpdir(),'enterprise-audit-report-'))
  const reportPath=path.join(dir,'audit.json')
  writeFileSync(reportPath,content)
  return spawnSync(process.execPath,[script,reportPath],{encoding:'utf8'})
}

function validReport(vulnerabilities={}){
  const rows=Object.values(vulnerabilities)
  return {
    auditReportVersion:2,
    vulnerabilities,
    metadata:{vulnerabilities:{
      info:0,low:0,moderate:0,
      high:rows.filter(value=>String(value?.severity||'').toLowerCase()==='high').length,
      critical:rows.filter(value=>String(value?.severity||'').toLowerCase()==='critical').length,
      total:rows.length,
    }},
  }
}

test('valid npm audit v2 production report is accepted',()=>{
  const result=run(JSON.stringify(validReport()))
  assert.equal(result.status,0,result.stderr)
  assert.match(result.stdout,/audit report validated: high=0, critical=0, total=0/)
})

test('network-error-like audit payload fails closed instead of becoming zero vulnerabilities',()=>{
  const result=run(JSON.stringify({error:{code:'ENETUNREACH',summary:'registry unavailable'}}))
  assert.equal(result.status,1)
  assert.match(result.stderr,/audit report is incomplete or inconsistent/)
  assert.match(result.stderr,/refusing to treat missing audit truth as zero vulnerabilities/)
})

test('invalid audit JSON fails closed as unreadable',()=>{
  const result=run('{not-json')
  assert.equal(result.status,1)
  assert.match(result.stderr,/audit report is unreadable/)
})

test('missing vulnerability counters fail closed instead of defaulting to zero',()=>{
  const report=validReport()
  delete report.metadata.vulnerabilities.high
  const result=run(JSON.stringify(report))
  assert.equal(result.status,1)
  assert.match(result.stderr,/incomplete or inconsistent/)
})

test('metadata cannot hide high severity vulnerability entries',()=>{
  const report=validReport({vue:{severity:'high',via:['advisory']}})
  report.metadata.vulnerabilities.high=0
  const result=run(JSON.stringify(report))
  assert.equal(result.status,1)
  assert.match(result.stderr,/incomplete or inconsistent/)
})

test('metadata total must match vulnerability entries',()=>{
  const report=validReport({vue:{severity:'moderate',via:['advisory']}})
  report.metadata.vulnerabilities.total=0
  const result=run(JSON.stringify(report))
  assert.equal(result.status,1)
  assert.match(result.stderr,/incomplete or inconsistent/)
})
