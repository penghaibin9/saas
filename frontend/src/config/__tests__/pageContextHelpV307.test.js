import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import {
  HELP_CARDS,
  VERIFIED_HELP_CARD_IDS,
  findHelpForRoute,
  searchHelp
} from '../helpCenterRuntime.js'

const here = dirname(fileURLToPath(import.meta.url))
const layoutSource = readFileSync(resolve(here, '../../layouts/BasePortalLayout.vue'), 'utf8')
const mainSource = readFileSync(resolve(here, '../../main.js'), 'utf8')
const adminHelpSource = readFileSync(resolve(here, '../../views/admin/help/AdminHelpView.vue'), 'utf8')
const miniappHelpSource = readFileSync(resolve(here, '../../../../miniapp/src/pages/common/help/index.vue'), 'utf8')

function pathOf(route) {
  return String(route || '').split('?')[0].replace(/\/$/, '')
}

test('V3-07 page help uses the runtime-cleaned card array before the app mounts', () => {
  assert.match(mainSource, /import ['"]\.\/config\/helpCenterRuntime['"]/)
  assert.match(layoutSource, /findHelpForRoute\(this\.\$route\.fullPath\)/)
  assert.match(layoutSource, /`\/admin\/help\?topic=\$\{this\.pageHelp\.id\}`/)

  const routedCards = HELP_CARDS.filter((card) => card.route)
  assert.ok(routedCards.length >= 20, `expected broad page-help coverage, got ${routedCards.length}`)
  for (const card of routedCards) {
    assert.ok(VERIFIED_HELP_CARD_IDS.has(card.id), `routed card escaped verified-only gate: ${card.id}`)
    const hit = findHelpForRoute(card.route)
    assert.ok(hit, `route has no page-help hit: ${card.route}`)
    assert.ok(VERIFIED_HELP_CARD_IDS.has(hit.id), `page-help resolved quarantined id: ${hit.id}`)
  }
})

test('V3-07 covers the four commercial PC domains and detail pages fall back to verified task cards', () => {
  const prefixes = ['/admin/academic-affairs', '/admin/internship', '/admin/graduation', '/admin/student-affairs']
  for (const prefix of prefixes) {
    const card = HELP_CARDS.find((item) => pathOf(item.route).startsWith(prefix))
    assert.ok(card, `missing verified route coverage for ${prefix}`)
    const baseHit = findHelpForRoute(card.route)
    assert.equal(baseHit?.id, card.id)

    const basePath = pathOf(card.route)
    const detailHit = findHelpForRoute(`${basePath}/__v307_detail_probe__`)
    assert.ok(detailHit, `detail route lost page help for ${card.id}`)
    assert.ok(VERIFIED_HELP_CARD_IDS.has(detailHit.id))
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

test('V3-07 common blockers resolve to verified 403 and 409 self-service cards', () => {
  const forbidden = searchHelp('403')
  const conflict = searchHelp('409')
  assert.ok(forbidden.some((item) => item.id === 'tr-v3-permission-scope-403'))
  assert.ok(conflict.some((item) => item.id === 'tr-v3-version-conflict-409'))
  assert.ok(VERIFIED_HELP_CARD_IDS.has('tr-v3-permission-scope-403'))
  assert.ok(VERIFIED_HELP_CARD_IDS.has('tr-v3-version-conflict-409'))
})

test('V3-07 miniapp continues to reuse the same web help with role and source context', () => {
  assert.match(miniappHelpSource, /role/)
  assert.match(miniappHelpSource, /source/)
  assert.match(miniappHelpSource, /helpCenterUrl/)
  assert.doesNotMatch(miniappHelpSource, /复制.*帮助正文|第二套帮助正文/)
})
