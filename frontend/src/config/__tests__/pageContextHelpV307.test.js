import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS } from '../help/academicAffairsCleanHelpCards.js'
import { ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS } from '../help/academicAffairsCoreFlowHelpCards.js'
import { INTERNSHIP_CLEAN_HELP_CARDS } from '../help/internshipCleanHelpCards.js'
import { INTERNSHIP_CORE_FLOW_HELP_CARDS } from '../help/internshipCoreFlowHelpCards.js'
import { GRADUATION_CLEAN_HELP_CARDS } from '../help/graduationCleanHelpCards.js'
import { GRADUATION_CORE_FLOW_HELP_CARDS } from '../help/graduationCoreFlowHelpCards.js'
import { STUDENT_AFFAIRS_CLEAN_HELP_CARDS } from '../help/studentAffairsCleanHelpCards.js'
import { STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS } from '../help/studentAffairsCoreFlowHelpCards.js'
import { HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS } from '../help/highFrequencyTroubleshootingHelpCards.js'

const here = dirname(fileURLToPath(import.meta.url))
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')
const legacyBridgeSource = readFileSync(resolve(here, '../helpContent.js'), 'utf8')
const layoutSource = readFileSync(resolve(here, '../../layouts/BasePortalLayout.vue'), 'utf8')
const mainSource = readFileSync(resolve(here, '../../main.js'), 'utf8')
const adminHelpSource = readFileSync(resolve(here, '../../views/admin/help/AdminHelpView.vue'), 'utf8')
const miniappHelpSource = readFileSync(resolve(here, '../../../../miniapp/src/pages/common/help/index.vue'), 'utf8')

const VERIFIED_DOMAIN_CARDS = [
  ...ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS,
  ...ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS,
  ...INTERNSHIP_CLEAN_HELP_CARDS,
  ...INTERNSHIP_CORE_FLOW_HELP_CARDS,
  ...GRADUATION_CLEAN_HELP_CARDS,
  ...GRADUATION_CORE_FLOW_HELP_CARDS,
  ...STUDENT_AFFAIRS_CLEAN_HELP_CARDS,
  ...STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS
]

function splitRoute(route) {
  const [path, qs = ''] = String(route || '').split('?')
  const panel = new URLSearchParams(qs).get('panel') || ''
  return { path: path.replace(/\/$/, ''), panel }
}

function resolveRoute(cards, fullPath) {
  const cur = splitRoute(fullPath)
  const routed = cards.filter((card) => card.route).map((card) => ({ card, route: splitRoute(card.route) }))
  const exact = routed.find((item) => item.route.path === cur.path && item.route.panel === cur.panel)
  const samePath = exact || routed.find((item) => item.route.path === cur.path)
  const prefix = samePath || routed
    .filter((item) => item.route.path && cur.path.startsWith(item.route.path + '/'))
    .sort((a, b) => b.route.path.length - a.route.path.length)[0]
  return prefix?.card || null
}

test('V3-07 page help is wired to the in-place verified-only runtime before app mount', () => {
  assert.match(mainSource, /import ['"]\.\/config\/helpCenterRuntime['"]/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS\)/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(INTERNSHIP_CLEAN_HELP_CARDS\)/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(GRADUATION_CLEAN_HELP_CARDS\)/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(STUDENT_AFFAIRS_CLEAN_HELP_CARDS\)/)
  assert.match(runtimeSource, /quarantineUnverifiedKnowledge\(\)/)
  assert.ok(runtimeSource.indexOf('quarantineUnverifiedKnowledge()') < runtimeSource.indexOf('export const HELP_CARDS = BASE_HELP_CARDS'))

  // BasePortalLayout keeps its stable compatibility import, while helpCenterRuntime mutates
  // the same HELP_CARDS array before mount; no second page-help knowledge source is created.
  assert.match(layoutSource, /findHelpForRoute\(this\.\$route\.fullPath\)/)
  assert.match(layoutSource, /`\/admin\/help\?topic=\$\{this\.pageHelp\.id\}`/)
  assert.match(legacyBridgeSource, /export function findHelpForRoute\(fullPath\)/)
  assert.match(legacyBridgeSource, /const cards = HELP_CARDS\.map|const cards = HELP_CARDS\.filter/)
})

test('V3-07 covers four commercial PC domains and detail routes fall back to verified task cards', () => {
  const routedCards = VERIFIED_DOMAIN_CARDS.filter((card) => card.route)
  assert.ok(routedCards.length >= 20, `expected broad verified page-help coverage, got ${routedCards.length}`)

  const prefixes = ['/admin/academic-affairs', '/admin/internship', '/admin/graduation', '/admin/student-affairs']
  for (const prefix of prefixes) {
    const card = routedCards.find((item) => splitRoute(item.route).path.startsWith(prefix))
    assert.ok(card, `missing verified route coverage for ${prefix}`)
    assert.equal(resolveRoute(routedCards, card.route)?.id, card.id)

    const detailHit = resolveRoute(routedCards, `${splitRoute(card.route).path}/__v307_detail_probe__`)
    assert.ok(detailHit, `detail route lost page help for ${card.id}`)
    assert.ok(VERIFIED_DOMAIN_CARDS.some((item) => item.id === detailHit.id))
  }
})

test('V3-07 article renders next step, self-check and escalation boundaries', () => {
  assert.match(adminHelpSource, /currentItem\.nextSteps\?\.length/)
  assert.match(adminHelpSource, /办完以后下一步/)
  assert.match(adminHelpSource, /currentItem\.troubleshooting\?\.length/)
  assert.match(adminHelpSource, /做不了时怎么自己排查/)
  assert.match(adminHelpSource, /currentItem\.contactAdminWhen\?\.length/)
  assert.match(adminHelpSource, /什么情况才需要找管理员/)
})

test('V3-07 common blockers have verified 403 and 409 self-service cards', () => {
  const forbidden = HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS.find((item) => item.id === 'tr-v3-permission-scope-403')
  const conflict = HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS.find((item) => item.id === 'tr-v3-version-conflict-409')
  assert.ok(forbidden)
  assert.ok(conflict)
  assert.match(JSON.stringify(forbidden), /403|NO_PERMISSION|NO_DATA_SCOPE/)
  assert.match(JSON.stringify(conflict), /409|DATA_CONFLICT|expectedVersion/)
})

test('V3-07 miniapp continues to reuse the same web help with role and source context', () => {
  assert.match(miniappHelpSource, /role/)
  assert.match(miniappHelpSource, /source/)
  assert.match(miniappHelpSource, /helpCenterUrl/)
  assert.doesNotMatch(miniappHelpSource, /复制.*帮助正文|第二套帮助正文/)
})
