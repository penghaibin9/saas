import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

import { validateFiles } from '../../scripts/check/check-graduation-v9-scope.mjs'

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8')

const pcWorkbench = read('../../student-portal/src/views/graduation/GraduationWorkbenchView.vue')
const pcApi = read('../../student-portal/src/services/portalApi.js')
const pcService = read('../../backend/app/student_portal/services/graduation_service.py')
const pcGuard = read('../../backend/app/api/v1/student_portal_graduation_guard.py')
const miniPage = read('../../miniapp/src/pages/student/graduation/index.vue')
const miniTaskbook = read('../../miniapp/src/pages/student/graduation/taskbook/index.vue')
const miniApi = read('../../miniapp/src/services/studentApi.js')
const miniReal = read('../../miniapp/src/services/realApi.js')
const mobileGuard = read('../../backend/app/api/v1/mobile_graduation_guard.py')

test('U10 taskbook confirmation binds the version actually rendered on both student surfaces', () => {
  assert.match(pcWorkbench, /我已阅读并确认任务书第 \{\{ taskbook\.taskbookVersion \|\| '—' \}\} 版/)
  assert.match(pcWorkbench, /portalApi\.signGraduationTaskbook\(taskbook\.value\.taskbookVersion\)/)
  assert.match(pcApi, /signGraduationTaskbook: \(taskbookVersion = renderedGraduationTaskbookVersion\)/)
  assert.match(pcApi, /body: \{ confirm: true, taskbookVersion \}/)
  assert.match(pcGuard, /confirm_with_evidence\(/)
  assert.match(pcGuard, /expected_version=payload\.get\("taskbookVersion"\) or payload\.get\("expectedVersion"\)/)

  assert.match(miniTaskbook, /v\{\{ t\.taskbookVersion \}\}/)
  assert.match(miniTaskbook, /confirmGraduationTaskbook\(this\.t\.taskbookVersion\)/)
  assert.match(miniApi, /confirmGraduationTaskbook: \(taskbookVersion\)/)
  assert.match(miniApi, /data: \{ taskbookVersion \}/)
  assert.match(mobileGuard, /confirm_with_evidence\(/)
  assert.match(mobileGuard, /expected_version=payload\.get\("taskbookVersion"\) or payload\.get\("expectedVersion"\)/)
})

test('U10 proposal and final submissions carry material expectedVersion on PC and miniapp', () => {
  assert.match(pcWorkbench, /expectedVersion: materialVersion\('PROPOSAL_REPORT'\)/)
  assert.match(pcWorkbench, /expectedVersion: materialVersion\(isFinal \? 'THESIS_FINAL' : 'THESIS_DRAFT'\)/)
  assert.match(miniPage, /expectedVersion: this\.materialVersion\('PROPOSAL_REPORT'\)/)
  assert.match(miniPage, /expectedVersion: this\.materialVersion\(finalType === '定稿' \? 'THESIS_FINAL' : 'THESIS_DRAFT'\)/)
  assert.match(pcService, /"expectedVersion": body\.get\("expectedVersion"\)/)
  assert.match(miniReal, /gdSubmitProposal = \(data\)[\s\S]*?\/mobile\/graduation\/proposal/)
  assert.match(miniReal, /gdSubmitFinal = \(data\)[\s\S]*?\/mobile\/graduation\/final/)
})

test('U10 midterm remediation and grade appeal expose the same server-owned state rules', () => {
  assert.match(pcWorkbench, /rectifyGraduationMidterm/)
  assert.match(pcWorkbench, /grade\.latestAppeal\?\.status === 'PENDING'/)
  assert.match(pcWorkbench, /grade\.canAppeal !== false/)
  assert.match(pcWorkbench, /appealReason\.value\.trim\(\)/)
  assert.match(miniPage, /midterm\.status === 'RECTIFYING'/)
  assert.match(miniPage, /submitGraduationMidtermRectify/)
  assert.match(miniPage, /grade\.latestAppeal && grade\.latestAppeal\.status === 'PENDING'/)
  assert.match(miniPage, /grade\.canAppeal !== false/)
  assert.match(miniPage, /appealReason\.trim\(\)\.length < 5/)
  assert.match(miniApi, /appealGraduationGrade: \(reason\) => real\.gdGradeAppeal\(reason\)/)
})

test('U10 student graduation core never falls back to mock truth', () => {
  assert.match(miniApi, /getGraduationProposal: \(\) => real\.gdProposal\(\)/)
  assert.match(miniApi, /getGraduationFinal: \(\) => real\.gdFinal\(\)/)
  assert.match(miniApi, /getGraduationMidterm: \(\) => real\.gdMidterm\(\)/)
  assert.match(miniApi, /getGraduationGrade: \(\) => real\.gdGrade\(\)/)
  assert.doesNotMatch(miniApi, /getGraduationProposal:[^\n]*realFirst/)
  assert.doesNotMatch(miniApi, /getGraduationFinal:[^\n]*realFirst/)
  assert.match(pcApi, /graduationProposal: \(\) => request\('\/portal\/graduation\/proposal'\)/)
  assert.match(pcApi, /graduationFinal: \(\) => request\('\/portal\/graduation\/final'\)/)
  assert.match(pcApi, /graduationGrade: \(\) => request\('\/portal\/graduation\/grade'\)/)
})

test('U10 student PC delegates the six reviewed capabilities to authoritative student services', () => {
  for (const signature of [
    /return stu\.graduation_taskbook\(user\)/,
    /return stu\.graduation_submit_proposal\(user, \{/,
    /return stu\.graduation_midterm_rectify\(user, content\)/,
    /return stu\.graduation_submit_final\(user, \{/,
    /return stu\.graduation_grade\(user\)/,
    /return stu\.graduation_grade_appeal\(user, reason\)/,
  ]) assert.match(pcService, signature)
})

test('U10 scope is contract-only unless a real dual-end mismatch is proven', () => {
  assert.deepEqual(validateFiles([
    'scripts/check/check-graduation-v9-scope.mjs',
    'frontend/tests/graduation.v9-student-dual-end.contract.test.mjs',
    'backend/tests/test_graduation_v9_u10_student_dual_end.py',
  ], 'U10'), [])
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'U10')[0], /shared foundation denied/)
  assert.match(validateFiles(['student-portal/src/views/graduation/GraduationWorkbenchView.vue'], 'U10')[0], /out of U10 allowlist/)
  assert.match(validateFiles(['miniapp/src/pages/student/graduation/index.vue'], 'U10')[0], /out of U10 allowlist/)
})
