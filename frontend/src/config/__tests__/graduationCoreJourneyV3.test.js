import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { GRADUATION_CLEAN_HELP_CARDS } from '../help/graduationCleanHelpCards.js'
import { GRADUATION_CORE_FLOW_HELP_CARDS } from '../help/graduationCoreFlowHelpCards.js'
import { HELP_V3_CORE_JOURNEYS } from '../help/helpCenterV3.js'
import '../help/helpRoleGuidanceRuntime.js'

const here = dirname(fileURLToPath(import.meta.url))
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')

const CORE_IDS = [
  'gd-v3-batch-setup',
  'gd-v3-student-mentor',
  'gd-v3-taskbook',
  'gd-v3-guidance-midterm',
  'gd-v3-final-submission',
  'gd-v3-plagiarism',
  'gd-v3-review',
  'gd-v3-archive'
]

const COMPLETE_JOURNEY = [
  'gd-v3-batch-setup',
  'gd-v3-student-mentor',
  'gd-v2-topic-selection',
  'gd-v3-taskbook',
  'gd-v2-proposal',
  'gd-v3-guidance-midterm',
  'gd-v3-final-submission',
  'gd-v3-plagiarism',
  'gd-v3-review',
  'gd-v2-defense',
  'gd-v2-grade',
  'gd-v3-archive'
]

const allCards = [...GRADUATION_CLEAN_HELP_CARDS, ...GRADUATION_CORE_FLOW_HELP_CARDS]

function body(id) {
  return JSON.stringify(allCards.find((card) => card.id === id))
}

function roleText(id) {
  return JSON.stringify(allCards.find((card) => card.id === id)?.roleGuidance || [])
}

test('V3-03 adds eight unique verified cards and upgrades all graduation cards to no-training contract', () => {
  assert.equal(GRADUATION_CORE_FLOW_HELP_CARDS.length, 8)
  assert.deepEqual(GRADUATION_CORE_FLOW_HELP_CARDS.map((card) => card.id), CORE_IDS)
  assert.equal(new Set(CORE_IDS).size, CORE_IDS.length)
  assert.equal(allCards.length, 12)

  for (const card of allCards) {
    for (const field of [
      'roles', 'entry', 'steps', 'prerequisites', 'permissions',
      'successCriteria', 'troubleshooting', 'nextSteps', 'contactAdminWhen'
    ]) {
      assert.ok(Array.isArray(card[field]) ? card[field].length > 0 : Boolean(card[field]), `${card.id} missing ${field}`)
    }
    assert.ok(card.authorizationPrinciple, `${card.id} missing authorizationPrinciple`)
    assert.ok(card.roleGuidance?.length, `${card.id} missing roleGuidance`)
    for (const row of card.roleGuidance) {
      assert.ok(row.role, `${card.id} role missing role`)
      assert.ok(row.permission, `${card.id} role missing permission`)
      assert.ok(row.scope, `${card.id} role missing scope`)
      assert.ok(row.relation, `${card.id} role missing relation`)
      assert.ok(row.canDo, `${card.id} role missing boundary`)
    }
  }
})

test('V3-03 graduation journey is the ordered twelve-node fact chain', () => {
  const journey = HELP_V3_CORE_JOURNEYS.find((item) => item.key === 'graduation')
  assert.ok(journey)
  assert.equal(journey.title, '毕业设计完整事实链')
  assert.deepEqual(journey.helpIds, COMPLETE_JOURNEY)
  for (const id of COMPLETE_JOURNEY) {
    assert.ok(allCards.some((card) => card.id === id), `journey references unpublished source id ${id}`)
  }
})

test('graduation ownership guidance uses stable identities and fails closed instead of authorizing by name', () => {
  const studentMentor = roleText('gd-v3-student-mentor')
  assert.match(studentMentor, /mentor_id/)
  assert.match(studentMentor, /teacher_no/)
  assert.match(studentMentor, /loginName/)
  assert.match(studentMentor, /collegeId/)
  assert.match(studentMentor, /majorId/)
  assert.match(studentMentor, /fail-closed/)
  assert.match(studentMentor, /studentNo \/ studentId/)

  const review = roleText('gd-v3-review')
  assert.match(review, /GD_REVIEWER/)
  assert.match(review, /reviewer_mentor_id/)
  assert.match(review, /姓名仅是快照/)

  const defense = roleText('gd-v2-defense')
  assert.match(defense, /secretary_mentor_id/)
  assert.match(defense, /mentorId 或 expertId/)
  assert.match(defense, /不以姓名匹配/)
})

test('taskbook and midterm cards lock versioned confirmation and rectification state machines', () => {
  const taskbook = body('gd-v3-taskbook')
  for (const token of ['PENDING_CONFIRM', 'CONFIRMED', 'CHANGE_PENDING', 'history', '版本号']) {
    assert.match(taskbook, new RegExp(token))
  }
  assert.match(taskbook, /变更.*重新确认|重新确认.*变更/)
  assert.match(taskbook, /不少于 5 字/)

  const midterm = body('gd-v3-guidance-midterm')
  for (const token of ['PENDING', 'CHECKED_PASS', 'RECTIFYING', 'RECTIFY_SUBMITTED', 'RECTIFIED_PASS', 'CHECKED_FAIL']) {
    assert.match(midterm, new RegExp(token))
  }
  assert.match(midterm, /FAIL.*HIGH|HIGH.*FAIL/)
  assert.match(midterm, /GET.*不.*写|读取.*不会.*建记录/)
})

test('final, plagiarism and review cards refuse shortcuts around authoritative sources and SoD', () => {
  const finalCard = body('gd-v3-final-submission')
  assert.match(finalCard, /FINAL_CHECK/)
  assert.match(finalCard, /初稿.*通过.*定稿|初稿 APPROVED/)
  assert.match(finalCard, /查重.*DONE|查重未 DONE/)
  assert.match(finalCard, /超阈值.*复查.*APPROVED|复查没有 APPROVED/)

  const plagiarism = body('gd-v3-plagiarism')
  for (const token of ['CHECKING', 'DONE', 'FAILED', 'overThreshold', 'recheck_of_id']) {
    assert.match(plagiarism, new RegExp(token))
  }
  assert.match(plagiarism, /新的 CHECKING|创建新的 CHECKING/)
  assert.match(plagiarism, /不能.*覆盖原|不覆盖原/)

  const review = body('gd-v3-review')
  assert.match(review, /SoD/)
  assert.match(review, /不得是该生指导教师/)
  assert.match(review, /APPROVED.*正式定稿|正式定稿.*APPROVED/)
  assert.match(review, /reviewer_mentor_id/)
})

test('archive card locks real evidence manifest preview token and terminal immutability', () => {
  const archive = body('gd-v3-archive')
  for (const token of ['NOT_GENERATED', 'PENDING_SUBMIT', 'SUBMITTED', 'FILED', 'REJECTED', 'Manifest', 'SHA-256', 'previewToken']) {
    assert.match(archive, new RegExp(token))
  }
  assert.match(archive, /任务书.*确认哈希/)
  assert.match(archive, /OPEN \/ PROCESSING 风险|开放风险/)
  assert.match(archive, /ORM.*终态守卫|不可变终态/)
  assert.match(archive, /解档审批/)
  assert.match(archive, /毕业资格.*独立裁决|不等于教务毕业资格/)
})

test('V3-03 core cards are published only through verified-only runtime', () => {
  assert.match(runtimeSource, /GRADUATION_CORE_FLOW_HELP_CARDS/)
  assert.match(runtimeSource, /\.\.\.GRADUATION_CORE_FLOW_HELP_CARDS\.map\(\(item\) => item\.id\)/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(GRADUATION_CORE_FLOW_HELP_CARDS\)/)
  assert.match(runtimeSource, /graduation-v3-core-cards/)
})
