import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { STUDENT_AFFAIRS_CLEAN_HELP_CARDS } from '../help/studentAffairsCleanHelpCards.js'
import { STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS } from '../help/studentAffairsCoreFlowHelpCards.js'
import { HELP_V3_CORE_JOURNEYS } from '../help/helpCenterV3.js'
import '../help/helpRoleGuidanceRuntime.js'

const here = dirname(fileURLToPath(import.meta.url))
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')
const mentalSource = readFileSync(resolve(here, '../../../backend/app/services/affairs_mental_service.py'), 'utf8')

const CORE_IDS = ['sa-v3-leave-lifecycle', 'sa-v3-aid-funding', 'sa-v3-discipline', 'sa-v3-care-risk']
const JOURNEY_IDS = [...CORE_IDS, 'sa-card-risk-handle', 'sa-card-archive']

function body(id) {
  return JSON.stringify(STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS.find((card) => card.id === id))
}

test('V3-04 publishes four unique no-training business-line cards', () => {
  assert.deepEqual(STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS.map((card) => card.id), CORE_IDS)
  for (const card of STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS) {
    for (const field of ['roles', 'entry', 'steps', 'prerequisites', 'permissions', 'successCriteria', 'troubleshooting', 'nextSteps', 'contactAdminWhen']) {
      assert.ok(Array.isArray(card[field]) ? card[field].length > 0 : Boolean(card[field]), `${card.id} missing ${field}`)
    }
    assert.ok(card.authorizationPrinciple, `${card.id} missing authorizationPrinciple`)
    assert.ok(card.roleGuidance?.length, `${card.id} missing roleGuidance`)
    for (const row of card.roleGuidance) {
      assert.ok(row.scope, `${card.id} role missing scope`)
      assert.ok(row.relation, `${card.id} role missing relation`)
      assert.ok(row.canDo, `${card.id} role missing boundary`)
    }
  }
})

test('V3-04 journey is four high-frequency lines plus verified risk/archive closure', () => {
  const journey = HELP_V3_CORE_JOURNEYS.find((item) => item.key === 'student-affairs')
  assert.ok(journey)
  assert.equal(journey.title, '学工四条高频办理线')
  assert.deepEqual(journey.helpIds, JOURNEY_IDS)
  for (const id of JOURNEY_IDS) {
    assert.ok(
      STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS.some((card) => card.id === id) ||
      STUDENT_AFFAIRS_CLEAN_HELP_CARDS.some((card) => card.id === id),
      `journey references unpublished source id ${id}`
    )
  }
})

test('leave card preserves approval, return, extension, cancel and overdue states', () => {
  const text = body('sa-v3-leave-lifecycle')
  for (const token of ['COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'STUDENT_AFFAIRS_REVIEW', 'APPROVED', 'RETURNED', 'REJECTED', 'EXTENSION_REVIEW', 'WAIT_CANCEL_LEAVE', 'OVERDUE', 'CLOSED', 'expectedVersion']) assert.match(text, new RegExp(token))
  assert.match(text, /RETURN.*退回.*REJECT|退回.*不等于.*REJECT/)
  assert.match(text, /待办.*指派|assignee/)
})

test('aid/funding card keeps recognition separate and freezes qualification facts', () => {
  const text = body('sa-v3-aid-funding')
  for (const token of ['CLASS_REVIEW', 'COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'SCHOOL_REVIEW', 'PUBLICITY', 'APPROVED', 'SCHOLARSHIP', 'GRANT', 'GRANTED', 'FUNDING_TEACHER']) assert.match(text, new RegExp(token))
  assert.match(text, /困难.*不是同一状态机|困难认定与资助不是同一状态机/)
  assert.match(text, /income_encrypted|敏感数据/)
  assert.match(text, /处分.*成绩.*困难/)
})

test('discipline card locks effective projection, appeal and removal subflow', () => {
  const text = body('sa-v3-discipline')
  for (const token of ['REGISTERED', 'COLLEGE_REVIEW', 'STUDENT_AFFAIRS_REVIEW', 'SCHOOL_REVIEW', 'EFFECTIVE', 'REMOVE_REVIEW', 'REMOVED', 'SUBMITTED', 'REVIEWING', 'UPHELD', 'REVISED', 'REVOKED']) assert.match(text, new RegExp(token))
  assert.match(text, /EFFECTIVE.*不可.*编辑|生效后禁止直接编辑/)
  assert.match(text, /历史.*保留/)
})

test('care card locks sensitive psychology scope and explicit risk handoff', () => {
  const text = body('sa-v3-care-risk')
  for (const token of ['PLANNED', 'SCHEDULED', 'COMPLETED', 'FOLLOW_UP', 'REFERRED', 'FOLLOWING', 'ESCALATED', 'CLOSED', 'PSY_STUDENT', 'teacher_key', 'SENSITIVE_VIEW', 'MENTAL', 'CRITICAL', 'NEW']) assert.match(text, new RegExp(token))
  assert.match(text, /不自动诊断|不会根据文本自动诊断/)
  assert.match(text, /同名.*不能|realName/)
  assert.match(text, /审计.*503|503.*fail-closed/)
})

test('psychology backend source cannot authorize by display name', () => {
  assert.match(mentalSource, /TeacherStudentScope\.teacher_key\.in_\(keys\)/)
  assert.doesNotMatch(mentalSource, /TeacherStudentScope\.teacher_name\.in_\(keys\)/)
  assert.doesNotMatch(mentalSource, /name\s*=\s*u\.get\("realName"\)/)
})

test('V3-04 core cards are wired through verified-only runtime', () => {
  assert.match(runtimeSource, /STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS/)
  assert.match(runtimeSource, /\.\.\.STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS\.map\(\(item\) => item\.id\)/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS\)/)
  assert.match(runtimeSource, /student-affairs-v3-core-cards/)
})
