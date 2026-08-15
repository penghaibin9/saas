import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const workflow=fs.readFileSync(new URL('../../.github/workflows/internship-enterprise-portal.yml',import.meta.url),'utf8')

test('A02 targeted workflow enforces locked production dependency audit with evidence',()=>{
  assert.match(workflow,/npm ci --no-audit --no-fund/)
  assert.match(workflow,/npm audit --omit=dev --json > audit-production\.json \|\| true/)
  assert.match(workflow,/Validate production audit report completeness/)
  assert.match(workflow,/check-production-audit-report\.mjs audit-production\.json/)
  assert.match(workflow,/check-npm-production-audit\.mjs/)
  assert.match(workflow,/audit-production\.json/)
  assert.match(workflow,/enterprise-portal\n\s+\.\.\/\.github\/security\/npm-production-audit-waivers\.json/)
  assert.match(workflow,/a02-enterprise-portal-npm-audit/)
  assert.match(workflow,/if-no-files-found: error/)
  assert.match(workflow,/retention-days: 14/)
})

test('A02 dependency audit remains production fail-closed rather than development-noise blocking',()=>{
  assert.match(workflow,/--omit=dev/)
  assert.match(workflow,/Enforce production high\/critical dependency policy/)
  assert.doesNotMatch(workflow,/npm audit --audit-level=moderate/)
})
