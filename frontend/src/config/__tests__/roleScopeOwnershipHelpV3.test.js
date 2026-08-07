import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildHelpSearchText,
  resolveHelpRole
} from '../helpCenterCore.js'
import { ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS } from '../help/academicAffairsCleanHelpCards.js'
import { ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS } from '../help/academicAffairsCoreFlowHelpCards.js'
import { INTERNSHIP_CLEAN_HELP_CARDS } from '../help/internshipCleanHelpCards.js'
import { HELP_V3_CORE_JOURNEYS } from '../help/helpCenterV3.js'

const academicCards = [
  ...ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS,
  ...ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS
]

function roleText(card) {
  return JSON.stringify(card.roleGuidance || [])
}

test('real runtime role templates resolve to help relevance groups', () => {
  assert.equal(resolveHelpRole('ACADEMIC_ADMIN'), 'academic')
  assert.equal(resolveHelpRole('ACADEMIC_TEACHER'), 'teacher')
  assert.equal(resolveHelpRole('COLLEGE_ADMIN'), 'school-admin')
  assert.equal(resolveHelpRole('INTERN_MENTOR'), 'teacher')
  assert.equal(resolveHelpRole('SECURITY_AUDITOR'), 'school-admin')
  assert.equal(resolveHelpRole('EMPLOYMENT_TEACHER'), 'teacher')
  assert.equal(resolveHelpRole('PSYCHOLOGY_TEACHER'), 'student-affairs')
  assert.equal(resolveHelpRole('FUNDING_TEACHER'), 'student-affairs')
  assert.equal(resolveHelpRole('GD_DEFENSE_SECRETARY'), 'teacher')
})

test('all verified academic V2/V3 cards expose permission + scope + business relation guidance', () => {
  assert.ok(academicCards.length >= 14)
  for (const card of academicCards) {
    assert.ok(card.authorizationPrinciple, `${card.id} missing authorizationPrinciple`)
    assert.ok(Array.isArray(card.roleGuidance) && card.roleGuidance.length > 0, `${card.id} missing roleGuidance`)
    const section = (card.sections || []).find((item) => item.key === 'authorization-role-scope')
    assert.ok(section, `${card.id} missing rendered role section`)
    assert.ok(section.body.includes('permissionCode'))
    for (const row of card.roleGuidance) {
      assert.ok(row.role)
      assert.ok(row.scope)
      assert.ok(row.relation)
      assert.ok(row.canDo)
    }
  }
})

test('academic teacher help cannot imply broad admin authority', () => {
  const gradeEntry = academicCards.find((card) => card.id === 'aa-card-grade-entry')
  const gradeText = roleText(gradeEntry)
  assert.match(gradeText, /ACADEMIC_TEACHER/)
  assert.match(gradeText, /本人授课课程/)
  assert.match(gradeText, /真实授课/)
  assert.match(gradeText, /不能学院审核、教务发布/)

  const schedule = academicCards.find((card) => card.id === 'aa-v3-schedule')
  const scheduleText = roleText(schedule)
  assert.match(scheduleText, /COUNSELOR/)
  assert.match(scheduleText, /本人所带班级/)
  assert.match(scheduleText, /只能查看本班课表/)
})

test('internship clean cards expose stable owner, scoped role and self-service handoff guidance', () => {
  const expected = [
    'in-v2-student-application',
    'in-v2-agreement',
    'in-v2-student-change',
    'in-v2-teacher-process',
    'in-v2-enterprise-eval',
    'in-v2-score'
  ]
  for (const id of expected) {
    const card = INTERNSHIP_CLEAN_HELP_CARDS.find((item) => item.id === id)
    assert.ok(card, `missing ${id}`)
    assert.ok(card.authorizationPrinciple, `${id} missing authorizationPrinciple`)
    assert.ok(card.roleGuidance?.length, `${id} missing roleGuidance`)
    assert.ok(card.nextSteps?.length, `${id} missing nextSteps`)
    assert.ok(card.contactAdminWhen?.length, `${id} missing contactAdminWhen`)
  }

  const processText = roleText(INTERNSHIP_CLEAN_HELP_CARDS.find((item) => item.id === 'in-v2-teacher-process'))
  assert.match(processText, /INTERN_MENTOR/)
  assert.match(processText, /advisor_user_id/)
  assert.match(processText, /姓名只作展示/)
  assert.match(processText, /SECURITY_AUDITOR/)
  assert.match(processText, /监督只读/)

  const scoreText = roleText(INTERNSHIP_CLEAN_HELP_CARDS.find((item) => item.id === 'in-v2-score'))
  assert.match(scoreText, /internship\.score\.view \/ manage/)
  assert.match(scoreText, /没有 internship\.score\.publish/)
  assert.match(scoreText, /最终发布、撤回/)
})

test('authorization guidance is searchable and V3 internship journey uses canonical clean ids', () => {
  const card = academicCards.find((item) => item.id === 'aa-card-grade-entry')
  const searchText = buildHelpSearchText(card)
  assert.match(searchText, /permissioncode/)
  assert.match(searchText, /本人授课课程/)
  assert.match(searchText, /真实授课/)

  const internship = HELP_V3_CORE_JOURNEYS.find((item) => item.key === 'internship')
  assert.ok(internship)
  assert.ok(internship.helpIds.includes('in-v2-student-change'))
  assert.ok(internship.helpIds.includes('in-v2-enterprise-eval'))
  assert.ok(!internship.helpIds.includes('in-v2-change'))
  assert.ok(!internship.helpIds.includes('in-v2-enterprise-evaluation'))
})
