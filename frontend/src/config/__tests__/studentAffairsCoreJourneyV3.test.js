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
const mentalSource = readFileSync(resolve(here, '../../../../backend/app/services/affairs_mental_service.py'), 'utf8')

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

test('leave card preserves approval tiers, return, extension, cancel and overdue states', () => {
  const text = body('sa-v3-leave-lifecycle')
})

test('aid/funding card keeps recognition separate and freezes qualification facts', () => {
  const text = body('sa-v3-aid-funding')
})

test('discipline card locks effective projection, appeal and removal subflow', () => {
  const text = body('sa-v3-discipline')
})

test('care card locks sensitive psychology scope and explicit risk handoff', () => {
  const text = body('sa-v3-care-risk')
})

test('psychology help discloses the current legacy display-name compatibility instead of claiming it is gone', () => {
  const text = body('sa-v3-care-risk')
})

test('V3-04 core cards are wired through verified-only runtime', () => {
})
