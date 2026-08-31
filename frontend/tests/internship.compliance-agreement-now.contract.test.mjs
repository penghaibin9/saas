import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const complianceView = fs.readFileSync(
  new URL('../src/modules/internship/views/InternshipComplianceView.vue', import.meta.url),
  'utf8'
)
const agreementView = fs.readFileSync(
  new URL('../src/modules/internship/views/AgreementView.vue', import.meta.url),
  'utf8'
)
const complianceService = fs.readFileSync(
  new URL('../../backend/app/modules/internship/services/internship_compliance_service.py', import.meta.url),
  'utf8'
)
const agreementService = fs.readFileSync(
  new URL('../../backend/app/modules/internship/services/internship_agreement_service.py', import.meta.url),
  'utf8'
)

test('W6 compliance overview puts exact blocked students before metrics', () => {
  assert.match(complianceView, /onboardingBlockedRows\(\)\s*\{\s*return \(this\.stats\.drilldowns\?\.BLOCKED \|\| \[\]\)\.slice\(0, 5\)/)
  assert.match(complianceView, /为什么到这里/)
  assert.match(complianceView, /最近核验/)
  assert.match(complianceView, /下一责任人/)
  assert.match(complianceView, /openStudent\(row\)/)

  const concreteIndex = complianceView.indexOf('class="mp-card compliance-now"')
  const metricsIndex = complianceView.indexOf('class="sa-grid sa-grid--metrics"')
  assert.ok(concreteIndex >= 0 && metricsIndex > concreteIndex)
})

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

test('W6 agreement list leads with bounded exact objects and preserves dossier authority', () => {
  assert.match(agreementView, /priorityRows\(\)\s*\{\s*return this\.rows\.slice\(0, 3\)\s*\}/)
  assert.match(agreementView, /为什么到这里/)
  assert.match(agreementView, /最近状态/)
  assert.match(agreementView, /下一责任人/)
  assert.match(agreementView, /openDossier\(row\)/)
  assert.match(agreementService, /"updatedAt": _iso\(a\.updated_at\) or ""/)

  const concreteIndex = agreementView.indexOf('class="ag-now"')
  const kpiIndex = agreementView.indexOf('<ModuleSummaryStrip')
  assert.ok(concreteIndex >= 0 && kpiIndex > concreteIndex)
})
