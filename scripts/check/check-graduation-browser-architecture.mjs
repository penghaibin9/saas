#!/usr/bin/env node
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

const production = read('.github/workflows/playwright-production-e2e.yml')
const graduation = read('.github/workflows/graduation-browser-gate.yml')
const gold = read('.github/workflows/graduation-v6-gold-candidate.yml')
const action = read('.github/actions/browser-runtime/action.yml')
const bootstrap = read('scripts/e2e/bootstrap-browser-runtime.sh')
const runner = read('scripts/e2e/run-browser-suite.sh')
const scenario = read('e2e/lib/graduation-scenario-fixture.mjs')
const finalVisual = read('e2e/specs/graduation-v9-final-review-visual.spec.mjs')
const crossClient = read('e2e/specs/graduation-v6-thesis-cross-client.spec.mjs')

for (const workflow of [production, graduation, gold]) {
  assert.match(workflow, /uses: \.\/\.github\/actions\/browser-runtime/)
  assert.doesNotMatch(workflow, /python -m alembic upgrade head/)
  assert.doesNotMatch(workflow, /nohup uvicorn/)
  assert.doesNotMatch(workflow, /e2e_bootstrap_graduation_accounts_ci\.py/)
}

assert.match(action, /bootstrap-browser-runtime\.sh/)
assert.match(bootstrap, /python -m alembic upgrade head/)
assert.match(bootstrap, /e2e_bootstrap_graduation_accounts_ci\.py/)
assert.match(bootstrap, /student-portal/)
assert.match(bootstrap, /teacher miniapp H5/)
assert.match(bootstrap, /BROWSER_RUNTIME_PROFILE/)

assert.match(production, /production-non-graduation/)
assert.match(runner, /! -name 'graduation\*\.spec\.mjs'/)
assert.match(runner, /! -name '\*-visual\.spec\.mjs'/)
assert.match(graduation, /graduation-functional/)
assert.match(graduation, /24-page audit/)

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

console.log('[graduation-browser-architecture] GREEN: runtime, suites, scenarios and Gold policy are centralized')
