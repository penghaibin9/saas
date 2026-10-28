import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtempSync,writeFileSync} from 'node:fs'
import {tmpdir} from 'node:os'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'

const script=fileURLToPath(new URL('../scripts/check-production-audit-report.mjs',import.meta.url))
function check(severity){
  const directory=mkdtempSync(path.join(tmpdir(),'standalone-audit-'))
  const report=path.join(directory,'audit.json')
  writeFileSync(report,JSON.stringify({auditReportVersion:2,vulnerabilities:{example:{severity}},
    metadata:{vulnerabilities:{high:severity==='high'?1:0,critical:severity==='critical'?1:0,total:1}}}))
  return spawnSync(process.execPath,[script,report],{encoding:'utf8'})
}

test('standalone production gate rejects complete high and critical reports without a parent workflow',()=>{
  for(const severity of ['high','critical']){
    const result=check(severity)
    assert.equal(result.status,1,result.stdout)
    assert.match(result.stderr,/禁止生成交付包/)
  }
})

test('standalone production gate retains the high and critical threshold',()=>{
  const result=check('moderate')
  assert.equal(result.status,0,result.stderr)
  assert.match(result.stdout,/audit report validated: high=0, critical=0, total=1/)
})
