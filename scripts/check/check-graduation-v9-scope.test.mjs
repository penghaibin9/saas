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

test('M7 grade flow allows its router, read/canonical services and regression contract only', () => {
  assert.deepEqual(validateFiles([
    'backend/app/modules/graduation/routers/graduation_sensitive_router.py',
    'backend/app/modules/graduation/services/__init__.py',
    'backend/app/modules/graduation/services/graduation_grade_read_service.py',
    'backend/app/modules/graduation/services/graduation_grade_service.py',
    'backend/tests/test_graduation_round7_pc_grade_contract.py',
  ], 'M7'), [])
  assert.match(validateFiles(['backend/app/modules/graduation/services/graduation_archive_service.py'], 'M7')[0], /out of M7 allowlist/)
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'M7')[0], /shared foundation denied/)
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

test('U4 process workbench allows only process read models, WorkContext UI and real visual evidence', () => {
  assert.deepEqual(validateFiles([
    'backend/app/modules/graduation/routers/graduation_process_sensitive_router.py',
    'backend/app/modules/graduation/services/graduation_process_consistency.py',
    'backend/app/modules/graduation/services/graduation_guidance_stats_read_service.py',
    'backend/tests/test_graduation_v9_process_pagination.py',
    'frontend/src/modules/graduation/api/graduation-student.api.js',
    'frontend/src/modules/graduation/views/GraduationProcessView.vue',
    'frontend/src/modules/graduation/views/GraduationProcessActionView.vue',
    'frontend/src/modules/graduation/views/GraduationProcessActionBaseView.vue',
    'frontend/tests/graduation.v9-process-context.contract.test.mjs',
    'e2e/specs/graduation-v9-process-visual.spec.mjs',
  ], 'U4'), [])
  assert.match(validateFiles(['frontend/src/layouts/BasePortalLayout.vue'], 'U4')[0], /shared foundation denied/)
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'U4')[0], /shared foundation denied/)
  assert.match(validateFiles(['backend/app/modules/graduation/services/graduation_grade_service.py'], 'U4')[0], /canonical write\/read mixed service denied/)
})

test('U5 student list allows only SQL read binding and scale contract', () => {
  assert.deepEqual(validateFiles([
    'backend/app/modules/graduation/services/__init__.py',
    'backend/app/modules/graduation/services/graduation_student_read_service.py',
    'backend/tests/test_graduation_v9_u5_student_list_scale.py',
  ], 'U5'), [])
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'U5')[0], /shared foundation denied/)
  assert.match(validateFiles(['backend/app/modules/graduation/services/graduation_grade_service.py'], 'U5')[0], /canonical write\/read mixed service denied/)
})

test('U6 grade workbench allows only grade views and its targeted validation contract', () => {
  assert.deepEqual(validateFiles([
    '.github/workflows/graduation-targeted-repair.yml',
    'frontend/src/modules/graduation/views/GraduationDefenseGradeView.vue',
    'frontend/src/modules/graduation/views/GraduationDefenseGradeFormView.vue',
  ], 'U6'), [])
  assert.match(validateFiles(['frontend/src/layouts/BasePortalLayout.vue'], 'U6')[0], /shared foundation denied/)
  assert.match(validateFiles(['backend/app/modules/graduation/services/graduation_grade_service.py'], 'U6')[0], /canonical write\/read mixed service denied/)
})

test('U7 archive prework only registers the SQL read binding already present on the branch', () => {
  assert.deepEqual(validateFiles([
    'backend/app/modules/graduation/services/__init__.py',
    'backend/app/modules/graduation/services/graduation_archive_read_service.py',
  ], 'U7'), [])
  assert.match(validateFiles(['backend/app/modules/graduation/services/graduation_archive_service.py'], 'U7')[0], /canonical write\/read mixed service denied/)
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'U7')[0], /shared foundation denied/)
})

test('U8 teacher mobile allows only scoped paging, mobile workbench, evidence and its scope self-test', () => {
  assert.deepEqual(validateFiles([
    'scripts/check/check-graduation-v9-scope.mjs',
    'scripts/check/check-graduation-v9-scope.test.mjs',
    'backend/app/api/v1/mobile_graduation_teacher_context.py',
    'backend/app/modules/graduation/services/graduation_mobile_teacher_query_service.py',
    'backend/tests/test_graduation_premerge_contracts.py',
    'backend/tests/test_graduation_v9_u8_mobile_teacher_paging.py',
    'miniapp/src/pages/teacher/workbench/index.vue',
    'miniapp/tests/graduation.v9-teacher-workbench.contract.test.mjs',
    'e2e/specs/graduation-v9-teacher-mobile-visual.spec.mjs',
  ], 'U8'), [])
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'U8')[0], /shared foundation denied/)
  assert.match(validateFiles(['backend/app/modules/graduation/services/graduation_grade_service.py'], 'U8')[0], /canonical write\/read mixed service denied/)
})

test('V9_PR is the union of declared V9.2 card files but keeps global denials', () => {
  assert.ok(patternsFor('V9_PR').length > patternsFor('M1').length)
  assert.deepEqual(validateFiles([
    '.github/workflows/graduation-v9-scope.yml',
    '.github/workflows/graduation-targeted-repair.yml',
    'frontend/src/modules/graduation/api/graduation-taskbook.api.js',
    'backend/app/modules/graduation/routers/graduation_student_eval.py',
    'frontend/tests/graduation.v9-reminder-truth.contract.test.mjs',
    'backend/tests/test_graduation_round5_contracts.py',
    'backend/app/modules/graduation/routers/graduation_sensitive_router.py',
    'backend/app/modules/graduation/services/graduation_grade_read_service.py',
    'backend/tests/test_graduation_round7_pc_grade_contract.py',
    'frontend/src/modules/graduation/views/GraduationDefenseGradeView.vue',
    'frontend/src/modules/graduation/views/GraduationDefenseGradeFormView.vue',
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
    'backend/app/modules/graduation/services/graduation_process_consistency.py',
    'frontend/src/modules/graduation/views/GraduationProcessView.vue',
    'e2e/specs/graduation-v9-process-visual.spec.mjs',
    'backend/app/modules/graduation/services/graduation_student_read_service.py',
    'backend/tests/test_graduation_v9_u5_student_list_scale.py',
    'backend/app/modules/graduation/services/graduation_archive_read_service.py',
    'backend/app/api/v1/mobile_graduation_teacher_context.py',
    'backend/app/modules/graduation/services/graduation_mobile_teacher_query_service.py',
    'backend/tests/test_graduation_premerge_contracts.py',
  ], 'V9_PR'), [])
  assert.match(validateFiles(['frontend/src/layouts/BasePortalLayout.vue'], 'V9_PR')[0], /shared foundation denied/)
})