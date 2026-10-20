import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const complianceView = fs.readFileSync(
  new URL('../src/modules/internship/views/InternshipComplianceView.vue', import.meta.url),
  'utf8'
)
const complianceService = fs.readFileSync(
  new URL('../../backend/app/modules/internship/services/internship_compliance_service.py', import.meta.url),
  'utf8'
)

// Overview context and full student coverage: internship.compliance-ui.behavior.test.mjs.

test('W6 compliance tabs are visually grouped without deleting deep-link keys', () => {
  for (const group of ['上岗门禁', '事故处置', '例外审批', '监管留痕']) {
    assert.match(complianceView, new RegExp(group))
  }
  for (const key of ['overview', 'consents', 'safety', 'filings', 'incidents', 'exemptions', 'evidence']) {
    assert.match(complianceView, new RegExp(`key: '${key}'`))
  }
  assert.match(complianceView, /'\$route\.query\.tab'/)
  assert.match(complianceView, /ensureGroupLoaded\(tab\)/)
})

test('W6 compliance projection carries both onboarding and archive server truth', () => {
  assert.match(complianceService, /"blockers": onboard\["blockers"\], "archiveBlockers": archive\["blockers"\]/)
  assert.match(complianceService, /"sourceVersion": int\(rec\.version or 0\)/)
  assert.match(complianceService, /"recentChange": rec\.updated_at\.isoformat\(\)/)
})

// Agreement dossier navigation and stale-response coverage: internship.agreement-ui.behavior.test.mjs.
