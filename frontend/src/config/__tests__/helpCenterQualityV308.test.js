import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS } from '../help/academicAffairsCleanHelpCards.js'
import { ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS } from '../help/academicAffairsCoreFlowHelpCards.js'
import { GRADUATION_CLEAN_HELP_CARDS } from '../help/graduationCleanHelpCards.js'
import { GRADUATION_CORE_FLOW_HELP_CARDS } from '../help/graduationCoreFlowHelpCards.js'
import { HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS } from '../help/highFrequencyTroubleshootingHelpCards.js'
import { HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS } from '../help/highFrequencyTroubleshootingHelpCardsV305B.js'
import { HIGH_FREQUENCY_TROUBLESHOOTING_V305C_CARDS } from '../help/highFrequencyTroubleshootingHelpCardsV305C.js'
import { INTERNSHIP_CLEAN_HELP_CARDS } from '../help/internshipCleanHelpCards.js'
import { INTERNSHIP_CORE_FLOW_HELP_CARDS } from '../help/internshipCoreFlowHelpCards.js'
import { STUDENT_AFFAIRS_CLEAN_HELP_CARDS } from '../help/studentAffairsCleanHelpCards.js'
import { STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS } from '../help/studentAffairsCoreFlowHelpCards.js'
import {
  HELP_V3_CORE_JOURNEYS,
  HELP_V3_QUICK_QUESTIONS
} from '../help/helpCenterV3.js'

const here = dirname(fileURLToPath(import.meta.url))
const viewSource = readFileSync(resolve(here, '../../views/admin/help/AdminHelpView.vue'), 'utf8')
const publicViewSource = readFileSync(resolve(here, '../../views/help/PublicHelpView.vue'), 'utf8')
const metricClientSource = readFileSync(resolve(here, '../help/helpMetrics.js'), 'utf8')
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')
const modelSource = readFileSync(resolve(here, '../helpCenterModel.js'), 'utf8')
const serviceSource = readFileSync(resolve(here, '../../../../backend/app/services/help_metrics_service.py'), 'utf8')
const apiSource = readFileSync(resolve(here, '../../../../backend/app/api/v1/help_metrics.py'), 'utf8')
const routerSource = readFileSync(resolve(here, '../../../../backend/app/api/v1/router.py'), 'utf8')

const VERIFIED_V3_CARDS = [
  ...ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS,
  ...ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS,
  ...INTERNSHIP_CLEAN_HELP_CARDS,
  ...INTERNSHIP_CORE_FLOW_HELP_CARDS,
  ...GRADUATION_CLEAN_HELP_CARDS,
  ...GRADUATION_CORE_FLOW_HELP_CARDS,
  ...STUDENT_AFFAIRS_CLEAN_HELP_CARDS,
  ...STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS,
  ...HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS,
  ...HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS,
  ...HIGH_FREQUENCY_TROUBLESHOOTING_V305C_CARDS
]
const CARD_MAP = new Map(VERIFIED_V3_CARDS.map((card) => [card.id, card]))

function hasList(card, field) {
  return Array.isArray(card[field]) && card[field].filter(Boolean).length > 0
}

function hasPermissionGuidance(card) {
  if (hasList(card, 'permissions') || hasList(card, 'permissionNotes')) return true
  return /权限|授权|数据范围|allowedActions|角色|管理员|本人授课范围/i.test(JSON.stringify(card))
}

function assertSevenDimensionContract(card) {
  assert.ok(card?.title, `${card?.id} missing title`)
  assert.ok(card?.summary, `${card?.id} missing summary`)
  assert.ok(card?.keywords?.length, `${card?.id} missing keywords`)
  assert.ok(card?.roles?.length, `${card?.id} missing roles`)
  assert.ok(card?.entry || card?.route || card?.mobilePath, `${card?.id} missing entry`)
  for (const field of ['steps', 'prerequisites', 'successCriteria', 'troubleshooting']) {
    assert.ok(hasList(card, field), `${card?.id} missing ${field}`)
  }
  assert.ok(hasPermissionGuidance(card), `${card?.id} missing permission guidance`)
}

test('V3-08 keeps commercial journey ids unique, published and contract-complete', () => {
  const ids = HELP_V3_CORE_JOURNEYS.flatMap((journey) => journey.helpIds)
  assert.equal(new Set(ids).size, ids.length, 'commercial journey ids must be unique')
  for (const id of ids) {
    const card = CARD_MAP.get(id)
    assert.ok(card, `${id} must be backed by a re-audited V3 card source`)
    assertSevenDimensionContract(card)
  }
  assert.match(runtimeSource, /VERIFIED_HELP_CARD_IDS/)
  assert.match(modelSource, /qualityGaps/)
})

test('V3-08 quick problem entries all match the verified V3 search corpus', () => {
  const corpus = JSON.stringify(VERIFIED_V3_CARDS).toLowerCase()
  for (const item of HELP_V3_QUICK_QUESTIONS) {
    assert.ok(corpus.includes(String(item.query).toLowerCase()), `${item.label} must not lead to a zero-result dead end`)
  }
})

test('V3-08 metrics persist real low-sensitivity events without storing enumerable search plaintext', () => {
  for (const token of [
    'HELP_SEARCH_HIT',
    'HELP_SEARCH_NO_RESULT',
    'HELP_ARTICLE_VIEW',
    'HELP_FEEDBACK_HELPFUL',
    'HELP_FEEDBACK_NOT_HELPFUL',
    'queryFingerprint',
    'sha256',
    'hmac.new',
    'help-search-fingerprint:v2:',
    'SecurityAuditLog'
  ]) assert.match(serviceSource, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))

  assert.match(serviceSource, /trueSelfServiceResolutionRate[^\n]*None/)
  assert.match(serviceSource, /需打通真实人工升级\/工单闭环后才能计算/)
  assert.doesNotMatch(serviceSource, /detail(?:\.update)?\([^)]*["']query["']\s*:/s)
  assert.doesNotMatch(serviceSource, /sha256\(\(["']help-search:v1:/)
})

test('V3-08 API separates event collection from school-level metric reading', () => {
  assert.match(apiSource, /@router\.post\("\/events"/)
  assert.match(apiSource, /@router\.get\("\/summary"/)
  assert.match(apiSource, /Depends\(get_current_user\)/)
  assert.match(apiSource, /enforce_permission\(user, "systemAdmin\.audit\.view"\)/)
  assert.match(routerSource, /help_metrics_router/)
})

test('V3-08 management page records searches, article views and explicit solved feedback', () => {
  for (const token of [
    'recordHelpMetric',
    "eventType: 'SEARCH'",
    "eventType: 'ARTICLE_VIEW'",
    "submitArticleFeedback('HELPFUL')",
    "submitArticleFeedback('NOT_HELPFUL')",
    '搜索命中率',
    '明确反馈解决率',
    '真正自助解决率',
    '不伪造“真实自助解决率”'
  ]) assert.ok(viewSource.includes(token), `${token} must stay wired into the Help Center page`)
})

test('V3-08 metric writes stay non-blocking and never use the global auth redirect request path', () => {
  assert.match(metricClientSource, /getToken/)
  assert.match(metricClientSource, /postMetric/)
  assert.match(metricClientSource, /help\/metrics\/events/)
  assert.match(metricClientSource, /help\/metrics\/public\/events/)
  assert.doesNotMatch(metricClientSource, /request\(['"]\/help\/metrics\/events/)
})

test('V3-08 public help surface records tenant-aware search, view and feedback through scoped capability', () => {
  for (const token of [
    'recordPublicHelpMetric',
    "eventType: 'SEARCH'",
    "eventType: 'ARTICLE_VIEW'",
    "submitArticleFeedback('HELPFUL')",
    "submitArticleFeedback('NOT_HELPFUL')",
    'publicMetricToken'
  ]) assert.ok(publicViewSource.includes(token), `${token} must stay wired into public help`)

  assert.match(metricClientSource, /help\/metrics\/public\/events/)
  assert.match(apiSource, /@router\.post\("\/public-session"/)
  assert.match(apiSource, /@router\.post\("\/public\/events"/)
  assert.match(serviceSource, /HELP_METRICS_PUBLIC/)
  assert.match(serviceSource, /PUBLIC_METRIC_TOKEN_TTL_SECONDS\s*=\s*600/)
  assert.doesNotMatch(publicViewSource, /gx_pc_token_v1|getToken\(/)
})
