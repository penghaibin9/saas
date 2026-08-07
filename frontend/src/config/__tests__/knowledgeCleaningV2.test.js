import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')
const modelSource = readFileSync(resolve(here, '../helpCenterModel.js'), 'utf8')

test('V2 runtime publishes verified knowledge only instead of trusting every legacy entry', () => {
  assert.match(runtimeSource, /VERIFIED_HELP_CARD_IDS/)
  assert.match(runtimeSource, /VERIFIED_HELP_FLOW_IDS/)
  assert.match(runtimeSource, /VERIFIED_HELP_DOC_IDS = new Set\(\)/)
  assert.match(runtimeSource, /QUARANTINED_UNVERIFIED_HELP_IDS/)
  assert.match(runtimeSource, /quarantineUnverifiedKnowledge\(\)/)
  assert.match(runtimeSource, /removeUnverifiedInPlace\(BASE_HELP_CARDS/)
  assert.match(runtimeSource, /removeUnverifiedInPlace\(HELP_DOCS/)
  assert.match(runtimeSource, /removeUnverifiedInPlace\(HELP_FLOWS/)
})

test('V2 verified card allowlist is grounded in re-audited sources and verified overrides', () => {
  for (const token of [
    'SYSTEM_HELP_CARDS.map',
    'FOUNDATION_HELP_CARDS.map',
    'STUDENT_DATA_HELP_CARDS.map',
    'ALL_MOBILE_HELP_CARDS.map',
    'Object.keys(VERIFIED_HELP_OVERRIDES)',
    'Object.keys(STUDENT_AFFAIRS_VERIFIED_OVERRIDES)',
    'Object.keys(ACADEMIC_AFFAIRS_VERIFIED_OVERRIDES)'
  ]) {
    assert.match(runtimeSource, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
})

test('V2 removes unverified knowledge from sidebar as well as search arrays', () => {
  assert.match(runtimeSource, /const publishedIds = new Set/)
  assert.match(runtimeSource, /section\.items = section\.items\.filter\(\(item\) => publishedIds\.has/)
  assert.match(runtimeSource, /被隔离的旧 help id 返回 null/)
})

test('V2 task-card quality contract requires the seven operational dimensions', () => {
  for (const field of [
    'roles',
    'entry-location',
    'steps',
    'prerequisites',
    'success-criteria',
    'troubleshooting',
    'permission-guidance'
  ]) {
    assert.match(modelSource, new RegExp(field))
  }
  assert.match(modelSource, /knowledge-cleaning-v2-seven-dimensions/)
  assert.match(modelSource, /hasPermissionGuidance/)
})

test('V2 priority help no longer promotes unverified encyclopedia docs', () => {
  assert.doesNotMatch(modelSource, /'doc-lifecycle'/)
  assert.doesNotMatch(modelSource, /'doc-academic-full-flow'/)
  assert.doesNotMatch(modelSource, /'doc-internship-full-flow'/)
  assert.doesNotMatch(modelSource, /'doc-graduation-full-flow'/)
  assert.match(modelSource, /'aa-card-grade-entry'/)
  assert.match(modelSource, /'in-card-eval-score'/)
  assert.match(modelSource, /'gd-card-defense-grade'/)
})
