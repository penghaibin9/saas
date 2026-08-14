import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

import { validateFiles } from '../../scripts/check/check-graduation-v9-scope.mjs'

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8')

const truth = read('../src/services/graduationTeacherCountTruth.js')
const page = read('../src/pages/teacher/graduation-guide/index.vue')
const request = read('../src/services/request.js')
const backend = read('../../backend/app/api/v1/mobile_graduation_teacher_context.py')

test('U12 miniapp count uses batch-aware server totals, not loaded queue length', () => {
  assert.match(truth, /realRequest\('\/mobile\/teacher\/graduation'\)/)
  assert.match(truth, /proposalTotal:\s*Number\(d\.proposalTotal \|\| 0\)/)
  assert.match(truth, /finalTotal:\s*Number\(d\.finalTotal \|\| 0\)/)
  assert.doesNotMatch(truth, /mockRequest|realFirst\(/)

  assert.match(page, /pendingReviewCount\(\) \{ return this\.proposalTotal \+ this\.finalTotal \}/)
  assert.match(page, /\{\{ proposalTotal \}\} 条/)
  assert.match(page, /\{\{ finalTotal \}\} 条/)
  assert.doesNotMatch(page, /pendingReviewCount\(\) \{ return this\.reviewQueue\.length \+ this\.finalQueue\.length \}/)
})

test('U12 miniapp re-reads authoritative count after review instead of local splice convergence', () => {
  const afterAction = page.match(/afterAction\(\) \{[\s\S]*?\n    \},\n    _confirm/)
  assert.ok(afterAction, 'afterAction block missing')
  assert.match(afterAction[0], /graduationTeacherCountTruth\(\)/)
  assert.match(afterAction[0], /this\.applyReviewTruth\(d\)/)
  assert.doesNotMatch(afterAction[0], /\.splice\(/)
  assert.match(page, /String\(e && e\.code\)\.startsWith\('409'\)[\s\S]*?this\.afterAction\(\)/)
})

test('U12 miniapp and PC count predicates share the selected graduation batch truth', () => {
  assert.match(request, /const GD_TEACHER_PREFIX = '\/mobile\/teacher\/graduation'/)
  assert.match(request, /const batch = getTeacherGraduationBatch\(\)/)
  assert.match(request, /appendQuery\(path, 'batchId', batch\.id\)/)

  assert.match(backend, /def teacher_graduation\([\s\S]*?batchId: int = Query\(\.\.\., ge=1\)/)
  assert.match(backend, /graduation\.list_proposals\([\s\S]*?status="PENDING_REVIEW", batch_id=batch_id\)/)
  assert.match(backend, /"proposalTotal": proposal_total/)
  assert.match(backend, /"finalTotal": final_total/)
})

test('U12 scope stays mobile-only and cannot touch canonical write or shared foundation', () => {
  assert.deepEqual(validateFiles([
    'scripts/check/check-graduation-v9-scope.mjs',
    'miniapp/src/services/graduationTeacherCountTruth.js',
    'miniapp/src/pages/teacher/graduation-guide/index.vue',
    'miniapp/tests/graduation.v9-cross-end-count.contract.test.mjs',
  ], 'U12'), [])
  assert.match(validateFiles(['backend/app/modules/graduation/services/graduation_proposal_service.py'], 'U12')[0], /canonical write\/read mixed service denied/)
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'U12')[0], /shared foundation denied/)
})
