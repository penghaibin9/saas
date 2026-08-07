import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { STUDENT_AFFAIRS_CLEAN_HELP_CARDS } from '../help/studentAffairsCleanHelpCards.js'
import { MOBILE_CLEAN_HELP_CARDS } from '../help/mobileCleanHelpCards.js'

const here = dirname(fileURLToPath(import.meta.url))
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')
const mobileHelpPageSource = readFileSync(resolve(here, '../../../../miniapp/src/pages/common/help/index.vue'), 'utf8')
const mobilePagesSource = readFileSync(resolve(here, '../../../../miniapp/src/pages.json'), 'utf8')
const mobileEnvSource = readFileSync(resolve(here, '../../../../miniapp/src/config/env.js'), 'utf8')
const studentMeSource = readFileSync(resolve(here, '../../../../miniapp/src/pages/student/me/index.vue'), 'utf8')
const teacherMeSource = readFileSync(resolve(here, '../../../../miniapp/src/pages/teacher/me/index.vue'), 'utf8')

function assertOperationalContract(card) {
  assert.ok(card.id)
  assert.ok(card.title)
  assert.ok(Array.isArray(card.roles) && card.roles.length > 0, `${card.id}: roles`)
  assert.ok(card.entry, `${card.id}: entry`)
  assert.ok(Array.isArray(card.prerequisites) && card.prerequisites.length > 0, `${card.id}: prerequisites`)
  assert.ok(Array.isArray(card.permissions) && card.permissions.length > 0, `${card.id}: permissions`)
  assert.ok(Array.isArray(card.steps) && card.steps.length > 0, `${card.id}: steps`)
  assert.ok(Array.isArray(card.successCriteria) && card.successCriteria.length > 0, `${card.id}: successCriteria`)
  assert.ok(Array.isArray(card.troubleshooting) && card.troubleshooting.length > 0, `${card.id}: troubleshooting`)
}

test('student affairs clean source only republishes the re-audited high-confidence PC tasks', () => {
  assert.deepEqual(
    STUDENT_AFFAIRS_CLEAN_HELP_CARDS.map((card) => card.id).sort(),
    ['sa-card-archive', 'sa-card-risk-handle']
  )
  STUDENT_AFFAIRS_CLEAN_HELP_CARDS.forEach(assertOperationalContract)

  const risk = STUDENT_AFFAIRS_CLEAN_HELP_CARDS.find((card) => card.id === 'sa-card-risk-handle')
  assert.match(risk.summary, /不是统一72小时/)
  assert.match(risk.warnings.join(' '), /24 \/ 48 \/ 72 \/ 120/)
  assert.match(risk.permissions.join(' '), /后端权限点|服务端/)

  const archive = STUDENT_AFFAIRS_CLEAN_HELP_CARDS.find((card) => card.id === 'sa-card-archive')
  assert.match(archive.summary, /DRAFT.*COLLECTING.*COLLEGE_REVIEW.*SA_CONFIRM.*ARCHIVED/)
  assert.match(archive.summary, /SHA-256/)
  assert.match(archive.warnings.join(' '), /没有充分代码证据/)
})

test('miniapp clean source gives every published card the seven-dimension operational contract', () => {
  assert.ok(MOBILE_CLEAN_HELP_CARDS.length > 1)
  MOBILE_CLEAN_HELP_CARDS.forEach(assertOperationalContract)

  const unified = MOBILE_CLEAN_HELP_CARDS.find((card) => card.id === 'mobile-unified-help-entry')
  assert.ok(unified)
  assert.equal(unified.mobilePath, 'pages/common/help/index')
  assert.match(unified.prerequisites.join(' '), /VITE_HELP_CENTER_URL/)
  assert.match(unified.prerequisites.join(' '), /业务域名/)
  assert.match(unified.permissions.join(' '), /不能代替后端授权/)
})

test('miniapp unified help entry is wired in both role surfaces and forwards role/source to the web help center', () => {
  assert.match(mobilePagesSource, /pages\/common\/help\/index/)
  assert.match(studentMeSource, /key: 'help'.*帮助与反馈/)
  assert.match(studentMeSource, /go\('\/pages\/common\/help\/index'\)/)
  assert.match(teacherMeSource, /key: 'help'.*帮助与反馈/)
  assert.match(teacherMeSource, /go\('\/pages\/common\/help\/index'\)/)
  assert.match(mobileHelpPageSource, /ENV\.helpCenterUrl/)
  assert.match(mobileHelpPageSource, /role: normalizeHelpRole\(session\)/)
  assert.match(mobileHelpPageSource, /source: 'miniapp'/)
  assert.match(mobileEnvSource, /VITE_HELP_CENTER_URL/)
  assert.match(mobileEnvSource, /微信公众平台.*业务域名/)
})

test('runtime is driven by clean sources for internship, graduation, student affairs and miniapp', () => {
  for (const token of [
    'INTERNSHIP_CLEAN_HELP_CARDS.map',
    'GRADUATION_CLEAN_HELP_CARDS.map',
    'STUDENT_AFFAIRS_CLEAN_HELP_CARDS.map',
    'MOBILE_CLEAN_HELP_CARDS.map',
    'replaceOrRegisterCards(INTERNSHIP_CLEAN_HELP_CARDS)',
    'replaceOrRegisterCards(GRADUATION_CLEAN_HELP_CARDS)',
    'replaceOrRegisterCards(STUDENT_AFFAIRS_CLEAN_HELP_CARDS)',
    'replaceOrRegisterCards(MOBILE_CLEAN_HELP_CARDS)'
  ]) {
    assert.match(runtimeSource, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.doesNotMatch(runtimeSource, /Object\.keys\(STUDENT_AFFAIRS_VERIFIED_OVERRIDES\)/)
  assert.doesNotMatch(runtimeSource, /applyCardOverrides\(cardsById, STUDENT_AFFAIRS_VERIFIED_OVERRIDES\)/)
})

test('generic teacher mobile approval is still not promoted as a verified return/reject workflow', () => {
  const approvalCards = MOBILE_CLEAN_HELP_CARDS.filter((card) => /通用审批|审批中心/.test(`${card.module || ''} ${card.title || ''}`))
  assert.equal(approvalCards.length, 0)
})
