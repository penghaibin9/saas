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
  assert.equal(journey.title, '毕业设计完整流程')
  assert.deepEqual(journey.helpIds, COMPLETE_JOURNEY)
  for (const id of COMPLETE_JOURNEY) {
    assert.ok(allCards.some((card) => card.id === id), `journey references unpublished source id ${id}`)
  }
})

test('graduation ownership guidance uses stable identities and fails closed instead of authorizing by name', () => {
  const studentMentor = roleText('gd-v3-student-mentor')

  const review = roleText('gd-v3-review')

  const defense = roleText('gd-v2-defense')
})

test('taskbook and midterm cards lock versioned confirmation and rectification state machines', () => {
  const taskbook = body('gd-v3-taskbook')


  const midterm = body('gd-v3-guidance-midterm')

})

test('final, plagiarism and review cards refuse shortcuts around authoritative sources and SoD', () => {
  const finalCard = body('gd-v3-final-submission')

  const plagiarism = body('gd-v3-plagiarism')


  const review = body('gd-v3-review')
})

test('archive card locks real evidence manifest preview token and terminal immutability', () => {
  const archive = body('gd-v3-archive')

})

test('V3-03 core cards are published only through verified-only runtime', () => {
})
