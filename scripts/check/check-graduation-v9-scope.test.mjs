import assert from 'node:assert/strict'
import test from 'node:test'

import { patternsFor, validateFiles } from './check-graduation-v9-scope.mjs'

test('S0.5 only allows its own scope gate files', () => {
  assert.deepEqual(validateFiles([
    'scripts/check/check-graduation-v9-scope.mjs',
    'scripts/check/check-graduation-v9-scope.test.mjs',
    '.github/workflows/graduation-v9-scope.yml',
  ], 'S0_5'), [])
  assert.match(validateFiles(['frontend/src/modules/graduation/views/ProposalListView.vue'], 'S0_5')[0], /out of S0_5 allowlist/)
})

test('M1 allows shared batch adapters and the migrated round5 contract, but denies shared HTTP foundation', () => {
  assert.deepEqual(validateFiles([
    'frontend/src/modules/graduation/api/graduation-batch-context.js',
    'frontend/src/modules/graduation/api/graduation-taskbook.api.js',
    'frontend/tests/graduation.v9-batch-context.contract.test.mjs',
    'backend/tests/test_graduation_round5_contracts.py',
  ], 'M1'), [])
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'M1')[0], /shared foundation denied/)
})

test('M2 is isolated from archive and grade canonical services', () => {
  assert.deepEqual(validateFiles([
    'backend/app/modules/graduation/routers/graduation_student_eval.py',
    'backend/app/modules/graduation/services/graduation_student_eval_service.py',
    'backend/tests/test_graduation_v9_student_eval_batch.py',
  ], 'M2'), [])
  assert.match(validateFiles(['backend/app/modules/graduation/services/graduation_archive_service.py'], 'M2')[0], /canonical write\/read mixed service denied/)
})

test('M4 allows only declared product-truth views and contracts', () => {
  assert.deepEqual(validateFiles([
    'frontend/src/modules/graduation/views/AdminGraduationLayout.vue',
    'frontend/src/modules/graduation/views/ProposalListView.vue',
    'frontend/src/modules/graduation/views/FinalSubmissionListView.vue',
    'frontend/tests/graduation.v9-reminder-truth.contract.test.mjs',
  ], 'M4'), [])
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'M4')[0], /shared foundation denied/)
})

test('U1 Dashboard allows only its page, evidence, module-local route repair, and legacy Golden selector contract', () => {
  assert.deepEqual(validateFiles([
    'frontend/src/modules/graduation/views/GraduationDashboardView.vue',
    'frontend/src/modules/graduation/routes.js',
    'e2e/specs/graduation-v9-dashboard-visual.spec.mjs',
    'e2e/specs/golden-rollout-business-pages.spec.mjs',
  ], 'U1'), [])
  assert.match(validateFiles(['frontend/src/layouts/BasePortalLayout.vue'], 'U1')[0], /shared foundation denied/)
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'U1')[0], /shared foundation denied/)
})

test('U2 proposal review stays inside the proposal page/read-model/test/gate-evidence boundary', () => {
  assert.deepEqual(validateFiles([
    'backend/app/modules/graduation/services/__init__.py',
    'backend/app/modules/graduation/services/graduation_service.py',
    'backend/app/modules/graduation/services/graduation_proposal_read_service.py',
    'backend/tests/test_graduation_v9_proposal_pagination.py',
    'frontend/src/modules/graduation/views/ProposalListView.vue',
    'frontend/tests/graduation.v9-proposal-review.contract.test.mjs',
    'e2e/pages/graduation.page.mjs',
    'docs/architecture/file-capability-inventory.d/10-graduation-v9-export.yaml',
  ], 'U2'), [])
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'U2')[0], /shared foundation denied/)
  assert.match(validateFiles(['backend/app/modules/graduation/services/graduation_grade_service.py'], 'U2')[0], /canonical write\/read mixed service denied/)
})

test('U3 final review allows SQL read model, real visual fixture/spec and final export registration only', () => {
  assert.deepEqual(validateFiles([
    'backend/app/modules/graduation/services/__init__.py',
    'backend/app/modules/graduation/services/graduation_final_read_service.py',
    'backend/tests/test_graduation_v9_final_pagination.py',
    'backend/scripts/e2e_seed_graduation_final_prerequisite.py',
    'frontend/src/modules/graduation/views/FinalSubmissionListView.vue',
    'frontend/tests/graduation.v9-final-review.contract.test.mjs',
    'frontend/tests/graduation.v9-final-review-permission.contract.test.mjs',
    'e2e/specs/graduation-v9-final-review-visual.spec.mjs',
    'docs/architecture/file-capability-inventory.d/10-graduation-v9-final-export.yaml',
  ], 'U3'), [])
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'U3')[0], /shared foundation denied/)
  assert.match(validateFiles(['backend/app/modules/graduation/services/graduation_archive_service.py'], 'U3')[0], /canonical write\/read mixed service denied/)
})

test('V9_PR is the union of declared V9.2 card files but keeps global denials', () => {
  assert.ok(patternsFor('V9_PR').length > patternsFor('M1').length)
  assert.deepEqual(validateFiles([
    '.github/workflows/graduation-v9-scope.yml',
    'frontend/src/modules/graduation/api/graduation-taskbook.api.js',
    'backend/app/modules/graduation/routers/graduation_student_eval.py',
    'frontend/tests/graduation.v9-reminder-truth.contract.test.mjs',
    'backend/tests/test_graduation_round5_contracts.py',
    'frontend/src/modules/graduation/routes.js',
    'e2e/specs/graduation-v9-dashboard-visual.spec.mjs',
    'e2e/specs/golden-rollout-business-pages.spec.mjs',
    'backend/app/modules/graduation/services/__init__.py',
    'backend/app/modules/graduation/services/graduation_proposal_read_service.py',
    'backend/tests/test_graduation_v9_proposal_pagination.py',
    'frontend/tests/graduation.v9-proposal-review.contract.test.mjs',
    'e2e/pages/graduation.page.mjs',
    'docs/architecture/file-capability-inventory.d/10-graduation-v9-export.yaml',
    'backend/app/modules/graduation/services/graduation_final_read_service.py',
    'backend/tests/test_graduation_v9_final_pagination.py',
    'backend/scripts/e2e_seed_graduation_final_prerequisite.py',
    'frontend/tests/graduation.v9-final-review.contract.test.mjs',
    'e2e/specs/graduation-v9-final-review-visual.spec.mjs',
    'docs/architecture/file-capability-inventory.d/10-graduation-v9-final-export.yaml',
  ], 'V9_PR'), [])
  assert.match(validateFiles(['frontend/src/layouts/BasePortalLayout.vue'], 'V9_PR')[0], /shared foundation denied/)
})
