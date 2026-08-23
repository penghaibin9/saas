import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

import { validateFiles } from '../../scripts/check/check-graduation-v9-scope.mjs'

const helper = fs.readFileSync(new URL('../src/modules/graduation/utils/form-state.js', import.meta.url), 'utf8')
const proposal = fs.readFileSync(new URL('../src/modules/graduation/views/_shared/ProposalReviewCard.vue', import.meta.url), 'utf8')
const grade = fs.readFileSync(new URL('../src/modules/graduation/views/GraduationDefenseGradeFormView.vue', import.meta.url), 'utf8')
const processAction = fs.readFileSync(new URL('../src/modules/graduation/views/GraduationProcessActionBaseView.vue', import.meta.url), 'utf8')
const finalReview = fs.readFileSync(new URL('../src/modules/graduation/views/FinalSubmissionListView.vue', import.meta.url), 'utf8')

test('U9 graduation conflict contract keeps draft, refreshes truth and requires explicit reconfirm', () => {
  assert.match(helper, /isGraduationConflictResponse/)
  assert.match(helper, /已刷新最新数据/)
  assert.match(helper, /填写的内容已保留/)
  assert.match(helper, /重新确认提交/)
  assert.match(helper, /服务端：/)
})

test('U9 proposal review refreshes a 409 without clearing teacher input or replaying the command', () => {
  assert.match(proposal, /async load\(\{ preserveDraft = false \} = \{\}\)/)
  assert.match(proposal, /await this\.load\(\{ preserveDraft: true \}\)/)
  assert.match(proposal, /graduationConflictMessage/)
  assert.doesNotMatch(proposal, /graduationApi\.reviewProposal[\s\S]*await this\.load\(\{ preserveDraft: true \}\)[\s\S]*graduationApi\.reviewProposal/)
})

test('U9 grade and process forms keep editable drafts while refreshing real server truth', () => {
  assert.match(grade, /captureEditableDraft/)
  assert.match(grade, /restoreEditableDraft/)
  assert.match(grade, /await this\.refreshConflictTruth\(\)/)
  assert.match(processAction, /captureDraft/)
  assert.match(processAction, /restoreDraft/)
  assert.match(processAction, /await this\.refreshConflictTruth\(\)/)
})

test('U9 specialist review/defense forms do not require unrelated grade read permission', () => {
  assert.match(grade, /const GRADE_CONTEXT_FORMS = new Set\(\['calculate', 'returnGrade', 'withdraw'\]\)/)
  assert.match(grade, /async loadStudentContext\(\)/)
  assert.match(grade, /if \(GRADE_CONTEXT_FORMS\.has\(this\.formKey\)\)/)
  assert.doesNotMatch(grade, /const contextCheck = await graduationDefenseGradeApi\.getGrade\(this\.studentId\)/)
  assert.match(grade, /routeBatchId[\s\S]*studentBatchId[\s\S]*当前批次与学生上下文不一致/)
})

test('U9 final review keeps the selected teacher draft and refreshes only current server truth on conflict', () => {
  assert.match(finalReview, /isGraduationConflictResponse/)
  assert.match(finalReview, /const draft = this\.comment/)
  assert.match(finalReview, /await this\.refreshSelectedConflictTruth\(res, draft\)/)
  assert.match(finalReview, /await this\.loadStats\(\)/)
  assert.match(finalReview, /await this\.loadSelectedDetail\(\)/)
  assert.match(finalReview, /this\.comment = draft/)
  assert.match(finalReview, /graduationConflictMessage/)
  assert.match(finalReview, /graduationActionErrorMessage/)
  assert.equal((finalReview.match(/graduationApi\.reviewFinal\(/g) || []).length, 1)
})

test('U9 scope stays module-local and keeps shared foundations denied', () => {
  assert.deepEqual(validateFiles([
    'scripts/check/check-graduation-v9-scope.mjs',
    'frontend/src/modules/graduation/utils/form-state.js',
    'frontend/src/modules/graduation/views/_shared/ProposalReviewCard.vue',
    'frontend/src/modules/graduation/views/GraduationDefenseGradeFormView.vue',
    'frontend/src/modules/graduation/views/GraduationProcessActionBaseView.vue',
    'frontend/src/modules/graduation/views/FinalSubmissionListView.vue',
    'frontend/tests/graduation.v9-form-state.contract.test.mjs',
  ], 'U9'), [])
  assert.match(validateFiles(['frontend/src/services/http/client.js'], 'U9')[0], /shared foundation denied/)
  assert.match(validateFiles(['backend/app/modules/graduation/services/graduation_grade_service.py'], 'U9')[0], /canonical write\/read mixed service denied/)
})