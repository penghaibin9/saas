#!/usr/bin/env node
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const workflowRoot = path.join(root, '.github/workflows')
const graduationStyleRoot = path.join(root, 'frontend/src/modules/graduation/styles')
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')
const exists = (relative) => fs.existsSync(path.join(root, relative))
const semanticSource = (source) => source.replace(/\\\//g, '/').replace(/\s+/g, ' ').trim()
const results = []

function contract(name, check) {
  try {
    check()
    results.push({ name, status: 'PASS' })
    console.log(`[graduation-browser-architecture] PASS ${name}`)
  } catch (error) {
    results.push({ name, status: 'FAIL', message: error?.message || String(error) })
    console.error(`[graduation-browser-architecture] FAIL ${name}`)
    console.error(error?.stack || error)
    console.error(JSON.stringify({ contract: 'graduation-browser-architecture-v3', results }, null, 2))
    process.exitCode = 1
    throw error
  }
}

function markerIndex(source, marker, contractName) {
  const index = source.indexOf(marker)
  assert.notEqual(index, -1, `${contractName}: missing marker ${marker}`)
  return index
}

const production = read('.github/workflows/playwright-production-e2e.yml')
const graduation = read('.github/workflows/graduation-browser-gate.yml')
const gold = read('.github/workflows/graduation-v6-gold-candidate.yml')
const targeted = read('.github/workflows/graduation-targeted-repair.yml')
const action = read('.github/actions/browser-runtime/action.yml')
const bootstrap = read('scripts/e2e/bootstrap-browser-runtime.sh')
const runner = read('scripts/e2e/run-browser-suite.sh')
const e2eConfig = read('e2e/lib/config.mjs')
const graduationRoleAccounts = read('e2e/lib/graduation-role-accounts.mjs')
const scenario = read('e2e/lib/graduation-scenario-fixture.mjs')
const deepLink = read('e2e/specs/graduation-v6-deep-link-workflows.spec.mjs')
const journeys = read('e2e/specs/graduation-v8-golden-journeys.spec.mjs')
const finalVisual = read('e2e/specs/graduation-v9-final-review-visual.spec.mjs')
const crossClient = read('e2e/specs/graduation-v6-thesis-cross-client.spec.mjs')
const mainEntry = read('frontend/src/main.js')
const graduationLayout = read('frontend/src/modules/graduation/views/AdminGraduationLayout.vue')
const graduationStyles = read('frontend/src/modules/graduation/styles/graduation-workspaces.css')

contract('one-browser-owner', () => {
  assert.equal(exists('.github/workflows/graduation-w77-exact-head-e2e.yml'), false,
    'retired W7.7 workflow must not return')
  for (const [name, workflow] of [
    ['playwright-production-e2e.yml', production],
    ['graduation-browser-gate.yml', graduation],
    ['graduation-v6-gold-candidate.yml', gold]
  ]) {
    assert.match(workflow, /uses: \.\/\.github\/actions\/browser-runtime/,
      `${name} must use the shared browser runtime`)
    assert.doesNotMatch(workflow, /python -m alembic upgrade head|nohup uvicorn|e2e_bootstrap_graduation_accounts_ci\.py/,
      `${name} must not duplicate runtime bootstrap`)
  }
  for (const name of fs.readdirSync(workflowRoot).filter((entry) => /\.ya?ml$/.test(entry))) {
    const workflow = fs.readFileSync(path.join(workflowRoot, name), 'utf8')
    assert.doesNotMatch(workflow,
      /npm run test:graduation|e2e\/specs\/graduation-lifecycle\.spec\.mjs/,
      `${name} directly owns the canonical Graduation lifecycle suite`)
  }
})

contract('one-style-owner', () => {
  const styleFiles = fs.readdirSync(graduationStyleRoot).filter((entry) => entry.endsWith('.css')).sort()
  assert.deepEqual(styleFiles, ['graduation-workspaces.css'],
    'Graduation must keep one stable module-local stylesheet')
  assert.doesNotMatch(mainEntry, /modules\/graduation\/styles/,
    'main.js must not broadcast Graduation styles globally')
  assert.match(graduationLayout, /@\/modules\/graduation\/styles\/graduation-workspaces\.css/,
    'AdminGraduationLayout must own the stylesheet import')
  for (const selector of ['.gd-business-view', '.gd-student-page', '.mc-summary', '.rk-rules']) {
    assert.ok(graduationStyles.includes(selector), `graduation-workspaces.css missing ${selector}`)
  }
})

contract('phased-runtime-bootstrap', () => {
  assert.match(action, /bootstrap-browser-runtime\.sh/)
  for (const marker of [
    'python -m alembic upgrade head',
    'python scripts/e2e_bootstrap_graduation_accounts_ci.py',
    'student-portal',
    'teacher miniapp H5',
    'BROWSER_RUNTIME_PROFILE',
    'run_api_bootstrap',
    'require_backend_ready',
    'node scripts/check/check-graduation-browser-architecture.mjs'
  ]) assert.ok(bootstrap.includes(marker), `bootstrap missing ${marker}`)

  const migrate = markerIndex(bootstrap, 'python -m alembic upgrade head', 'phased-runtime-bootstrap')
  const dbBase = markerIndex(bootstrap, 'python scripts/e2e_seed_academic_b_selection.py', 'phased-runtime-bootstrap')
  const dbFormation = markerIndex(bootstrap, 'python scripts/e2e_seed_academic_b_w4_formation.py', 'phased-runtime-bootstrap')
  const backendStart = markerIndex(bootstrap, 'nohup uvicorn app.main:app', 'phased-runtime-bootstrap')
  const backendReady = markerIndex(bootstrap, 'wait_for_url "$BACKEND_HEALTH_URL" "backend API"', 'phased-runtime-bootstrap')
  const accountBootstrap = markerIndex(bootstrap, 'python scripts/e2e_bootstrap_graduation_accounts_ci.py', 'phased-runtime-bootstrap')
  const passwordReset = markerIndex(bootstrap, 'python scripts/e2e_reset_graduation_passwords.py', 'phased-runtime-bootstrap')
  const accountVerify = markerIndex(bootstrap, 'python scripts/e2e_verify_graduation_accounts.py', 'phased-runtime-bootstrap')
  const counselorBootstrap = markerIndex(bootstrap, 'python scripts/e2e_bootstrap_affairs_counselor_ci.py', 'phased-runtime-bootstrap')
  const w5Seed = markerIndex(bootstrap, 'python scripts/e2e_seed_academic_b_w5_selection.py', 'phased-runtime-bootstrap')
  const internshipSeed = markerIndex(bootstrap, 'python scripts/e2e_seed_internship_sandbox.py', 'phased-runtime-bootstrap')
  const clientStart = markerIndex(bootstrap, 'phase "client-surfaces"', 'phased-runtime-bootstrap')

  assert.ok(migrate < dbBase && dbBase < dbFormation && dbFormation < backendStart,
    'DB-only facts must be deterministic and precede backend startup')
  assert.ok(backendStart < backendReady, 'backend startup must precede readiness')
  for (const apiStep of [accountBootstrap, passwordReset, accountVerify, counselorBootstrap]) {
    assert.ok(backendReady < apiStep, 'API identity bootstrap must follow backend readiness')
  }
  assert.ok(accountBootstrap < passwordReset && passwordReset < accountVerify,
    'identity import, password normalization and verification order is fixed')
  assert.ok(accountVerify < w5Seed && counselorBootstrap < w5Seed,
    'identity-dependent fixtures require verified actors')
  assert.ok(w5Seed < internshipSeed && internshipSeed < clientStart,
    'identity-dependent facts must settle before clients start')
})

contract('suite-and-gold-ownership', () => {
  assert.ok(production.includes('production-non-graduation'),
    'platform Playwright must exclude Graduation ownership')
  assert.match(runner, /! -name 'graduation\*\.spec\.mjs'/)
  assert.match(runner, /! -name '\*-visual\.spec\.mjs'/)
  assert.ok(graduation.includes('graduation-functional') && graduation.includes('24-page audit'),
    'Graduation gate must own functional and 24-page audit suites')
  assert.match(runner, /find specs -maxdepth 1 -type f -name 'graduation\*\.spec\.mjs'/)
  assert.ok(targeted.includes('tests/test_graduation*.py') && targeted.includes('tests/test_aa_graduation*.py'),
    'targeted workflow must own Graduation backend proofs')

  const retiredProofs = [
    'backend/tests/test_graduation_e2e_acceptance_gates.py',
    'backend/tests/test_graduation_mobile_teacher_views.py',
    'backend/tests/test_graduation_review.py',
    'backend/tests/test_graduation_stable_identity.py',
    'backend/tests/test_graduation_review_w71_w73_mysql.py',
    'backend/tests/test_graduation_student_feedback_w75_pc_contract.py',
    'backend/tests/test_graduation_review_w76_runtime.py',
    'backend/tests/test_graduation_review_w76_todo_message_stats_contract.py'
  ]
  for (const proof of retiredProofs) assert.equal(exists(proof), true, `missing backend proof ${proof}`)

  assert.match(gold, /workflow_dispatch:/)
  assert.doesNotMatch(gold, /\n\s+pull_request:/)
  assert.match(gold, /cancel-in-progress: false/)
  assert.ok(gold.includes('graduation-gold'), 'Gold workflow must use the dedicated candidate suite')
  assert.match(runner, /build-graduation-gold-candidate\.py/)
  assert.match(runner, /candidate\.patch/)
})

contract('shared-graduation-scenarios', () => {
  for (const [name, source] of [['final visual', finalVisual], ['cross client', crossClient]]) {
    assert.ok(source.includes('graduation-scenario-fixture.mjs'), `${name} must use the scenario factory`)
    assert.ok(source.includes('ensureFinalPending'), `${name} must use ensureFinalPending`)
    assert.doesNotMatch(source, /e2e_seed_graduation_final_prerequisite\.py|function buildPreviewablePdf/,
      `${name} must not own a duplicate final fixture`)
  }
  for (const marker of [
    'ensureProposalApproved', 'ensureFinalPending', 'PROPOSAL_APPROVED',
    'FINAL_PENDING', 'documentPages = 20', 'expectRenderedPdfCanvas'
  ]) assert.ok(scenario.includes(marker), `scenario factory missing ${marker}`)
})

contract('module-local-real-role-actors', () => {
  assert.doesNotMatch(e2eConfig, /E2E_GRADUATION_(?:REVIEWER|DEFENSE|SECRETARY)/,
    'shared E2E config must stay domain-neutral')
  for (const marker of [
    "reviewer: account('E2E_GRADUATION_REVIEWER'",
    "defenseExpert: account('E2E_GRADUATION_DEFENSE'",
    "defenseChair: account('E2E_GRADUATION_DEFENSE_B'",
    "defenseSecretary: account('E2E_GRADUATION_SECRETARY'"
  ]) assert.ok(graduationRoleAccounts.includes(marker), `role registry missing ${marker}`)
  assert.ok(scenario.includes('ensureDefenseScoringContext'), 'scenario must own defense context')
  assert.ok(scenario.includes('memberMentorIds: [Number(expert.id)]'), 'expert must occupy a real group seat')
  assert.ok(scenario.includes('did not read back as published'), 'published group must be server-readback')
  assert.ok(deepLink.includes('login.login(graduationRoles.defenseExpert)'),
    'score workflow must login as the dedicated expert')
  assert.ok(deepLink.includes('ensureDefenseScoringContext(adminApi, fixture)'),
    'score workflow must create the real role relation graph')
  assert.doesNotMatch(deepLink, /login\(config\.mentor\)[\s\S]{0,1200}formKey: 'scoreEntry'/,
    'mentor must not masquerade as a defense judge')
  assert.doesNotMatch(journeys, /const DEFENSE_EXPERT\s*=/,
    'journeys must not keep a private role account')
  assert.ok(journeys.includes('loginTeacherMini(handoff, graduationRoles.defenseExpert)'),
    'defense journey must use the module role registry')
})

contract('exact-miniapp-task-contract', () => {
  const normalized = semanticSource(crossClient)
  assert.ok(crossClient.includes('exact-task-direct-review'), 'exact task evidence marker missing')
  assert.ok(normalized.includes('成果批阅 · 第 1 / 1 条'),
    'exact task must assert the direct review header semantically')
  assert.equal(crossClient.includes("getByText('成果待批阅'"), false,
    'exact task must not wait for the bypassed list title')
  for (const key of ['batchId', 'gdStudentId', 'recordId', 'materialVersion', 'fileVersionId']) {
    assert.ok(crossClient.includes(key), `exact task evidence missing ${key}`)
  }
})

contract('archive-readback-and-leaf-query', () => {
  assert.ok(scenario.includes('ensureArchiveProjection'), 'archive scenario helper missing')
  assert.ok(scenario.includes('Archive projection did not read back'), 'archive scenario must fail on missing readback')
  assert.ok(journeys.includes('ensureArchiveProjection(adminApi, fixture)'),
    'archive journey must prepare server truth')
  const normalized = semanticSource(journeys)
  assert.ok(normalized.includes("'毕设材料归档': { panel: 'archive' }"),
    'archive role-home contract must require panel=archive')
  assert.ok(journeys.includes('assertRoleHomeDestination(page, entryLabel, expectedPath)'),
    'every role-home leaf must validate the destination query contract')
})

console.log(JSON.stringify({
  contract: 'graduation-browser-architecture-v3',
  status: 'GREEN',
  passed: results.length,
  results
}, null, 2))
