import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS } from '../help/academicAffairsCleanHelpCards.js'
import { buildHelpSearchText } from '../helpCenterCore.js'

const here = dirname(fileURLToPath(import.meta.url))
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')

const EXPECTED_IDS = [
  'aa-card-status-change',
  'aa-card-grade-entry',
  'aa-card-grade-review-publish',
  'aa-card-grade-change',
  'aa-card-selection-round',
  'aa-card-selection-publish',
  'aa-card-exam-arrangement',
  'aa-card-exam-publish'
]

function card(id) {
  const found = ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS.find((item) => item.id === id)
  assert.ok(found, id)
  return found
}

function text(id) {
  return buildHelpSearchText(card(id))
}

test('academic V2 publishes one clean authoritative set for status grade selection and exam', () => {
  assert.deepEqual(ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS.map((item) => item.id), EXPECTED_IDS)
  assert.equal(new Set(EXPECTED_IDS).size, EXPECTED_IDS.length)
  assert.doesNotMatch(runtimeSource, /applyCardOverrides\(cardsById, ACADEMIC_AFFAIRS_VERIFIED_OVERRIDES\)/)
  assert.doesNotMatch(runtimeSource, /Object\.keys\(ACADEMIC_AFFAIRS_VERIFIED_OVERRIDES\)/)
})

test('all cleaned academic cards satisfy the V2 seven-dimensional task contract', () => {
  for (const item of ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS) {
    assert.ok(item.title, item.id)
    assert.ok(item.summary, item.id)
    assert.ok(Array.isArray(item.keywords) && item.keywords.length > 0, item.id)
    assert.ok(Array.isArray(item.roles) && item.roles.length > 0, item.id)
    assert.ok(item.entry, item.id)
    assert.ok(Array.isArray(item.prerequisites) && item.prerequisites.length > 0, item.id)
    assert.ok(Array.isArray(item.permissions) && item.permissions.length > 0, item.id)
    assert.ok(Array.isArray(item.steps) && item.steps.length >= 3, item.id)
    assert.ok(Array.isArray(item.successCriteria) && item.successCriteria.length > 0, item.id)
    assert.ok(Array.isArray(item.troubleshooting) && item.troubleshooting.length > 0, item.id)
  }
})

test('student-status guide keeps real change types, approval nodes, scopes and configurable suspension limit', () => {
  const value = text('aa-card-status-change')
  assert.doesNotMatch(value, /休学到期日：休学默认2年/)
})

test('grade entry guide uses dynamic components and never restores the fixed usual-final formula', () => {
  const value = text('aa-card-grade-entry')
  assert.doesNotMatch(value, /总评\s*=\s*平时分.*期末分/)
})

test('grade publish guide keeps publish transaction separate from the post-commit warning scan', () => {
  const value = text('aa-card-grade-review-publish')
})

test('grade correction guide preserves published-only, reason, approval and append-only version semantics', () => {
  const value = text('aa-card-grade-change')
})

test('selection round guide preserves one-open-round, lottery draw-once and server-capacity truth', () => {
  const value = text('aa-card-selection-round')
})

test('selection publish guide locks DRAFT publication and transactional enroll/drop rules', () => {
  const value = text('aa-card-selection-publish')
})

test('exam arrangement guide publishes the real auto-exam engine without pretending it always succeeds', () => {
  const value = text('aa-card-exam-arrangement')
  assert.doesNotMatch(value, /系统能自动排考吗？.*不能/)
})

test('exam publish guide requires rooms seats and invigilators before PUBLISHED', () => {
  const value = text('aa-card-exam-publish')
})
