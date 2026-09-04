#!/usr/bin/env node
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const workflowRoot = path.join(root, '.github/workflows')
const graduationStyleRoot = path.join(root, 'frontend/src/modules/graduation/styles')
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')
const mustIndex = (source, marker) => {
  const index = source.indexOf(marker)
  assert.notEqual(index, -1, `missing architecture marker: ${marker}`)
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
const legacyW77 = '.github/workflows/graduation-w77-exact-head-e2e.yml'

assert.equal(
  fs.existsSync(path.join(root, legacyW77)),
  false,
  `${legacyW77} duplicates the canonical browser runtime and targeted backend validation`,
)

for (const workflow of [production, graduation, gold]) {
  assert.match(workflow, /uses: \.\/\.github\/actions\/browser-runtime/)
  assert.doesNotMatch(workflow, /python -m alembic upgrade head/)
  assert.doesNotMatch(workflow, /nohup uvicorn/)
  assert.doesNotMatch(workflow, /e2e_bootstrap_graduation_accounts_ci\.py/)
}

for (const name of fs.readdirSync(workflowRoot).filter((entry) => /\.ya?ml$/.test(entry))) {
  const workflow = fs.readFileSync(path.join(workflowRoot, name), 'utf8')
  assert.doesNotMatch(
    workflow,
    /npm run test:graduation|e2e\/specs\/graduation-lifecycle\.spec\.mjs/,
    `${name} directly owns the canonical Graduation lifecycle browser suite; use graduation-browser-gate.yml`,
  )
}

const graduationStyleFiles = fs.readdirSync(graduationStyleRoot)
  .filter((entry) => entry.endsWith('.css'))
  .sort()
assert.deepEqual(
  graduationStyleFiles,
  ['graduation-workspaces.css'],
  'Graduation presentation must have one stable module-local stylesheet; round/hotfix files are forbidden',
)
assert.doesNotMatch(
  mainEntry,
  /modules\/graduation\/styles/,
  'frontend/src/main.js must not broadcast Graduation page styles to the whole application',
)
assert.match(
  graduationLayout,
  /@\/modules\/graduation\/styles\/graduation-workspaces\.css/,
  'AdminGraduationLayout must own the one Graduation workspace stylesheet',
)
assert.match(graduationStyles, /\.gd-business-view/)
assert.match(graduationStyles, /\.gd-student-page/)
assert.match(graduationStyles, /\.mc-summary/)
assert.match(graduationStyles, /\.rk-rules/)

assert.match(action, /bootstrap-browser-runtime\.sh/)
assert.match(bootstrap, /python -m alembic upgrade head/)
assert.match(bootstrap, /e2e_bootstrap_graduation_accounts_ci\.py/)
assert.match(bootstrap, /student-portal/)
assert.match(bootstrap, /teacher miniapp H5/)
assert.match(bootstrap, /BROWSER_RUNTIME_PROFILE/)
assert.match(bootstrap, /run_api_bootstrap/)
assert.match(bootstrap, /require_backend_ready/)
assert.match(bootstrap, /node scripts\/check\/check-graduation-browser-architecture\.mjs/)

const migrate = mustIndex(bootstrap, 'python -m alembic upgrade head')
const dbBase = mustIndex(bootstrap, 'python scripts/e2e_seed_academic_b_selection.py')
const dbFormation = mustIndex(bootstrap, 'python scripts/e2e_seed_academic_b_w4_formation.py')
const backendStart = mustIndex(bootstrap, 'nohup uvicorn app.main:app')
const backendReady = mustIndex(bootstrap, 'wait_for_url "$BACKEND_HEALTH_URL" "backend API"')
const accountBootstrap = mustIndex(bootstrap, 'python scripts/e2e_bootstrap_graduation_accounts_ci.py')
const passwordReset = mustIndex(bootstrap, 'python scripts/e2e_reset_graduation_passwords.py')
const accountVerify = mustIndex(bootstrap, 'python scripts/e2e_verify_graduation_accounts.py')
const counselorBootstrap = mustIndex(bootstrap, 'python scripts/e2e_bootstrap_affairs_counselor_ci.py')
const w5Seed = mustIndex(bootstrap, 'python scripts/e2e_seed_academic_b_w5_selection.py')
const internshipSeed = mustIndex(bootstrap, 'python scripts/e2e_seed_internship_sandbox.py')
const clientStart = mustIndex(bootstrap, 'phase "client-surfaces"')

assert.ok(migrate < dbBase, 'database migration must precede DB-only domain seeds')
assert.ok(dbBase < dbFormation, 'Academic B prerequisite order must remain deterministic')
assert.ok(dbFormation < backendStart, 'DB-only organization facts must exist before backend startup')
assert.ok(backendStart < backendReady, 'backend must start before readiness is asserted')
for (const apiStep of [accountBootstrap, passwordReset, accountVerify, counselorBootstrap]) {
  assert.ok(backendReady < apiStep, 'every API-backed bootstrap must run after backend readiness')
}
assert.ok(
  accountBootstrap < passwordReset && passwordReset < accountVerify,
  'canonical identity import, password normalization and verification order is fixed',
)
assert.ok(accountVerify < w5Seed, 'identity-dependent W5 facts require verified canonical accounts')
assert.ok(counselorBootstrap < w5Seed, 'counselor identity must be stable before dependent facts')
assert.ok(
  w5Seed < internshipSeed && internshipSeed < clientStart,
  'identity-dependent DB facts must settle before any client starts',
)

assert.match(production, /production-non-graduation/)
assert.match(runner, /! -name 'graduation\*\.spec\.mjs'/)
assert.match(runner, /! -name '\*-visual\.spec\.mjs'/)
assert.match(graduation, /graduation-functional/)
assert.match(graduation, /24-page audit/)
assert.match(runner, /find specs -maxdepth 1 -type f -name 'graduation\*\.spec\.mjs'/)

assert.match(targeted, /tests\/test_graduation\*\.py tests\/test_aa_graduation\*\.py/)
const retiredW77Proofs = [
  'backend/tests/test_graduation_e2e_acceptance_gates.py',
  'backend/tests/test_graduation_mobile_teacher_views.py',
  'backend/tests/test_graduation_review.py',
  'backend/tests/test_graduation_stable_identity.py',
  'backend/tests/test_graduation_review_w71_w73_mysql.py',
  'backend/tests/test_graduation_student_feedback_w75_pc_contract.py',
  'backend/tests/test_graduation_review_w76_runtime.py',
  'backend/tests/test_graduation_review_w76_todo_message_stats_contract.py',
]
for (const proof of retiredW77Proofs) {
  assert.equal(fs.existsSync(path.join(root, proof)), true, `missing retired W7.7 proof: ${proof}`)
  assert.match(path.basename(proof), /^test_graduation.*\.py$/)
}

assert.match(gold, /workflow_dispatch:/)
assert.doesNotMatch(gold, /\n\s+pull_request:/)
assert.match(gold, /cancel-in-progress: false/)
assert.match(gold, /graduation-gold/)
assert.match(runner, /build-graduation-gold-candidate\.py/)
assert.match(runner, /candidate\.patch/)

for (const source of [finalVisual, crossClient]) {
  assert.match(source, /graduation-scenario-fixture\.mjs/)
  assert.match(source, /ensureFinalPending/)
  assert.doesNotMatch(source, /e2e_seed_graduation_final_prerequisite\.py/)
  assert.doesNotMatch(source, /function buildPreviewablePdf/)
}

assert.match(scenario, /ensureProposalApproved/)
assert.match(scenario, /ensureFinalPending/)
assert.match(scenario, /PROPOSAL_APPROVED/)
assert.match(scenario, /FINAL_PENDING/)
assert.match(scenario, /documentPages = 20/)
assert.match(scenario, /expectRenderedPdfCanvas/)

// Graduation-only actors belong to a module registry, not the shared config.
assert.doesNotMatch(e2eConfig, /E2E_GRADUATION_(?:REVIEWER|DEFENSE|SECRETARY)/)
assert.match(graduationRoleAccounts, /reviewer: account\('E2E_GRADUATION_REVIEWER'/)
assert.match(graduationRoleAccounts, /defenseExpert: account\('E2E_GRADUATION_DEFENSE'/)
assert.match(graduationRoleAccounts, /defenseChair: account\('E2E_GRADUATION_DEFENSE_B'/)
assert.match(graduationRoleAccounts, /defenseSecretary: account\('E2E_GRADUATION_SECRETARY'/)
assert.match(scenario, /ensureDefenseScoringContext/)
assert.match(scenario, /memberMentorIds: \[Number\(expert\.id\)\]/)
assert.match(scenario, /Defense group .* did not read back as published/)
assert.match(deepLink, /login\.login\(graduationRoles\.defenseExpert\)/)
assert.match(deepLink, /ensureDefenseScoringContext\(adminApi, fixture\)/)
assert.doesNotMatch(deepLink, /login\(config\.mentor\)[\s\S]{0,1200}formKey: 'scoreEntry'/)
assert.doesNotMatch(journeys, /const DEFENSE_EXPERT\s*=/)
assert.match(journeys, /loginTeacherMini\(handoff, graduationRoles\.defenseExpert\)/)

// Exact miniapp task deep links open review directly.
assert.match(crossClient, /exact-task-direct-review/)
assert.match(crossClient, /成果批阅 · 第 1 \/ 1 条/)
assert.doesNotMatch(crossClient, /getByText\('成果待批阅'[\s\S]{0,600}去批阅成果/)

// Archive journeys are read-before-write and preserve the leaf query contract.
assert.match(scenario, /ensureArchiveProjection/)
assert.match(scenario, /Archive projection did not read back/)
assert.match(journeys, /ensureArchiveProjection\(adminApi, fixture\)/)
assert.match(journeys, /'毕设材料归档': \{ panel: 'archive' \}/)
assert.match(journeys, /assertRoleHomeDestination\(page, entryLabel, expectedPath\)/)

console.log('[graduation-browser-architecture] GREEN: one browser owner, one style owner, phased runtime, module-local actors, exact task locks, readback scenarios and manual Gold policy')
