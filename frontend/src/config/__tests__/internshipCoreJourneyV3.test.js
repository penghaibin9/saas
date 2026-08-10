import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { INTERNSHIP_CORE_FLOW_HELP_CARDS } from '../help/internshipCoreFlowHelpCards.js'
import { INTERNSHIP_CLEAN_HELP_CARDS } from '../help/internshipCleanHelpCards.js'
import { HELP_V3_CORE_JOURNEYS } from '../help/helpCenterV3.js'
import '../helpCenterCore.js'

const here = dirname(fileURLToPath(import.meta.url))
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')

const CORE_IDS = [
  'in-v3-batch-lifecycle',
  'in-v3-onboard-compliance',
  'in-v3-risk-incident',
  'in-v3-student-evaluation',
  'in-v3-archive'
]

const COMPLETE_JOURNEY = [
  'in-v3-batch-lifecycle',
  'in-v2-student-application',
  'in-v2-agreement',
  'in-v3-onboard-compliance',
  'in-v2-teacher-process',
  'in-v3-risk-incident',
  'in-v2-student-change',
  'in-v2-enterprise-eval',
  'in-v3-student-evaluation',
  'in-v2-score',
  'in-v3-archive'
]

function body(id) {
  return JSON.stringify(INTERNSHIP_CORE_FLOW_HELP_CARDS.find((card) => card.id === id))
}

test('V3-02 adds five unique verified core cards with the no-training contract', () => {
  assert.equal(INTERNSHIP_CORE_FLOW_HELP_CARDS.length, 5)
  assert.deepEqual(INTERNSHIP_CORE_FLOW_HELP_CARDS.map((card) => card.id), CORE_IDS)
  assert.equal(new Set(CORE_IDS).size, CORE_IDS.length)

  for (const card of INTERNSHIP_CORE_FLOW_HELP_CARDS) {
    for (const field of [
      'roles', 'entry', 'steps', 'prerequisites', 'permissions',
      'successCriteria', 'troubleshooting', 'nextSteps', 'contactAdminWhen'
    ]) {
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

test('V3-02 internship journey is the ordered eleven-node self-service chain', () => {
  const journey = HELP_V3_CORE_JOURNEYS.find((item) => item.key === 'internship')
  assert.ok(journey)
  assert.equal(journey.title, '岗位实习完整办理链')
  assert.deepEqual(journey.helpIds, COMPLETE_JOURNEY)
  for (const id of COMPLETE_JOURNEY) {
    assert.ok(
      INTERNSHIP_CORE_FLOW_HELP_CARDS.some((card) => card.id === id) ||
      INTERNSHIP_CLEAN_HELP_CARDS.some((card) => card.id === id),
      `journey references unpublished source id ${id}`
    )
  }
})

test('batch card locks ADMIN_TENANT guard, frozen rules and readiness state machine', () => {
  const text = body('in-v3-batch-lifecycle')
  for (const token of ['DRAFT', 'RUNNING', 'CLOSED', 'ARCHIVED', 'VOIDED', 'ADMIN_TENANT', 'SCOPED', 'readiness', 'expectedVersion']) {
    assert.match(text, new RegExp(token))
  }
  assert.match(text, /启用.*冻结|冻结.*合规/)
  assert.match(text, /不少于 5 字/)
  assert.match(text, /多个 RUNNING/)
})

test('onboard compliance card refuses one-document-is-enough shortcuts', () => {
  const text = body('in-v3-onboard-compliance')
  for (const token of [
    'enterpriseAccess', 'studentConsent', 'guardianConsent', 'safetyEducation',
    'agreement', 'insurance', 'specialFiling', 'workRights', 'emergency', 'ruleVersion'
  ]) assert.match(text, new RegExp(token))
  assert.match(text, /申请通过.*不等于|协议.*不等于可以上岗/)
  assert.match(text, /compliance\.view.*不是全域写权限/)
})

test('risk and incident card preserves real risk lifecycle and separate incident fact', () => {
  const text = body('in-v3-risk-incident')
  for (const token of ['PENDING_HANDLE', 'PROCESSING', 'RESOLVED', 'CLOSED', 'incident', 'advisor_user_id']) {
    assert.match(text, new RegExp(token))
  }
  assert.match(text, /升级.*不改变.*状态|升级.*不等于关闭/)
  assert.match(text, /事故.*独立|独立正式事实/)
})

test('student evaluation card locks student-version mentor-opinion and independent school review', () => {
  const text = body('in-v3-student-evaluation')
  for (const token of ['SUBMITTED', 'PENDING', 'APPROVED', 'RETURNED', 'expectedVersion', 'advisorOpinion', 'internship.eval.self.review']) {
    assert.match(text, new RegExp(token))
  }
  assert.match(text, /自评总结至少 20 字|至少 20 字/)
  assert.match(text, /指导教师意见.*不少于 5 字|意见不少于 5 字/)
  assert.match(text, /角色二次守卫|独立角色白名单/)
  assert.match(text, /旧.*意见.*失效|清空旧 advisorOpinion/)
})

test('archive card uses authoritative evaluation, immutable snapshot and strict school-only force', () => {
  const text = body('in-v3-archive')
  for (const token of ['archivePassed', 'ruleVersion', 'internship.archive.execute', 'internship.archive.force', 'SCHOOL_ADMIN', 'material_snapshot', 'ZIP']) {
    assert.match(text, new RegExp(token))
  }
  assert.match(text, /10 个汉字|10个汉字/)
  assert.match(text, /依据文件/)
  assert.match(text, /不可变.*快照|冻结.*快照/)
  assert.match(text, /材料.*布尔.*不.*最终真值|材料标签.*不替代权威评估/)
})

test('V3-02 core cards are published only through verified-only runtime', () => {
  assert.match(runtimeSource, /INTERNSHIP_CORE_FLOW_HELP_CARDS/)
  assert.match(runtimeSource, /\.\.\.INTERNSHIP_CORE_FLOW_HELP_CARDS\.map\(\(item\) => item\.id\)/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(INTERNSHIP_CORE_FLOW_HELP_CARDS\)/)
  assert.match(runtimeSource, /internship-v3-core-cards/)
})
