import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('T4 Student360 consumes dedicated real projection and has no PC placeholder actions', () => {
  const page = read('src/pages/teacher/student-detail/index.vue')
  const api = read('src/services/teacherStudent360V3Api.js')
  assert.match(api, /realRequest\(`\/teacher-mobile\/students\/\$\{encodeURIComponent/)
  assert.match(page, /teacherStudent360V3Api\.get\(this\.id\)/)
  assert.doesNotMatch(page, /teacherApi\.getStudent360/)
  assert.doesNotMatch(page, /请在 PC 端|尚未配置|拨打/)
  for (const key of ['RECORD_CONTACT', 'NEW_TALK', 'FAMILY_CONTACT', 'EMPLOYMENT_FOLLOWUP']) {
    assert.match(page, new RegExp(key))
  }
})

test('T4 Student360 object actions pass one student context to mature pages', () => {
  const page = read('src/pages/teacher/student-detail/index.vue')
  assert.match(page, /pages\/teacher\/family-contact\/index/)
  assert.match(page, /pages\/teacher\/affairs\/talk\/index/)
  assert.match(page, /pages\/teacher\/employment-follow\/index/)
  assert.match(page, /pages\/teacher\/affairs\/mental\/index/)
  assert.match(page, /studentId:/)
  assert.match(page, /employmentStudentId/)
  assert.match(page, /internshipId/)
  assert.match(page, /onShow\(\).*this\.load\(\)/s)
})

test('T4 talk and family contact accept locked Student360 prefill without weakening backend authority', () => {
  const talk = read('src/pages/teacher/affairs/talk/index.vue')
  const family = read('src/pages/teacher/family-contact/index.vue')
  assert.match(talk, /applyPrefill\(q \|\| \{\}\)/)
  assert.match(talk, /this\.form\.studentIds = \[studentId\]/)
  assert.match(talk, /teacherApi\.createTalk/)
  assert.match(talk, /prefillLocked/)
  assert.match(family, /applyPrefill\(q \|\| \{\}\)/)
  assert.match(family, /teacherApi\.createFamilyContact/)
  assert.match(family, /prefillLocked/)
})

test('T4 mental prefill must still pass specialty candidate authorization', () => {
  const mental = read('src/pages/teacher/affairs/mental/index.vue')
  assert.match(mental, /getStudentCandidates\('MENTAL'\)/)
  assert.match(mental, /this\.students\.find\(\(x\) => String\(x\.studentId\) === this\.prefillStudentId\)/)
  assert.match(mental, /当前学生不在心理专项授权范围内/)
  assert.match(mental, /getMentalDetail\(this\.active\.referralId, reason\)/)
  assert.match(mental, /affairsContractApi\.followMental/)
  assert.match(mental, /affairsContractApi\.escalateMental/)
  assert.match(mental, /affairsContractApi\.closeMental/)
})

test('T4 employment followup uses canonical write and returns to Student360 after success', () => {
  const page = read('src/pages/teacher/employment-follow/index.vue')
  assert.match(page, /employmentStudentId/)
  assert.match(page, /teacherApi\.createFollowup/)
  assert.match(page, /fromStudent360/)
  assert.match(page, /uni\.navigateBack\(\)/)
})

test('T4 Student360 sensitive zone contains summaries only', () => {
  const page = read('src/pages/teacher/student-detail/index.vue')
  assert.match(page, /明细需专项授权与审计/)
  assert.match(page, /不展示事由与文书正文/)
  assert.doesNotMatch(page, /phone|手机号|身份证|counselorNote|reasonSummary/)
})

test('T4 Student360 timeline never renders or projects free-text reason', () => {
  const page = read('src/pages/teacher/student-detail/index.vue')
  const projection = read('../backend/app/services/teacher_mobile_student360_projection_service.py')
  const timelineBlock = projection.slice(projection.indexOf('"timeline": ['), projection.indexOf('"context": {'))
  assert.match(page, /stageText\(event\.stage\)/)
  assert.doesNotMatch(page, /event\.reason/)
  assert.doesNotMatch(timelineBlock, /"reason"\s*:|event\.reason/)
})
