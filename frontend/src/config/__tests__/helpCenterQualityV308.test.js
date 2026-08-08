import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import {
  ALL_HELP_ENTRIES,
  getHelpEntry,
  searchHelpCenter
} from '../helpCenterModel.js'
import {
  HELP_V3_CORE_JOURNEYS,
  HELP_V3_QUICK_QUESTIONS
} from '../help/helpCenterV3.js'

const here = dirname(fileURLToPath(import.meta.url))
const viewSource = readFileSync(resolve(here, '../../views/admin/help/AdminHelpView.vue'), 'utf8')
const serviceSource = readFileSync(resolve(here, '../../../../backend/app/services/help_metrics_service.py'), 'utf8')
const apiSource = readFileSync(resolve(here, '../../../../backend/app/api/v1/help_metrics.py'), 'utf8')
const routerSource = readFileSync(resolve(here, '../../../../backend/app/api/v1/router.py'), 'utf8')

test('V3-08 keeps every published help id unique and every commercial journey node complete', () => {
  const ids = ALL_HELP_ENTRIES.map((entry) => entry.id)
  assert.equal(new Set(ids).size, ids.length, 'published help ids must be unique')

  for (const id of HELP_V3_CORE_JOURNEYS.flatMap((journey) => journey.helpIds)) {
    const entry = getHelpEntry(id)
    assert.ok(entry, `${id} must resolve through verified-only runtime`)
    assert.equal(entry.quality.isComplete, true, `${id} must satisfy the help quality contract`)
  }
})

test('V3-08 quick problem entries all produce at least one verified result', () => {
  for (const item of HELP_V3_QUICK_QUESTIONS) {
    const results = searchHelpCenter(item.query, { role: 'all', limit: 100 })
    assert.ok(results.length > 0, `${item.label} must not lead to a zero-result dead end`)
  }
})

test('V3-08 metrics persist real low-sensitivity events without storing search plaintext', () => {
  for (const token of [
    'HELP_SEARCH_HIT',
    'HELP_SEARCH_NO_RESULT',
    'HELP_ARTICLE_VIEW',
    'HELP_FEEDBACK_HELPFUL',
    'HELP_FEEDBACK_NOT_HELPFUL',
    'queryFingerprint',
    'sha256',
    'SecurityAuditLog'
  ]) assert.match(serviceSource, new RegExp(token))

  assert.match(serviceSource, /trueSelfServiceResolutionRate[^\n]*None/)
  assert.match(serviceSource, /需打通真实人工升级\/工单闭环后才能计算/)
  assert.doesNotMatch(serviceSource, /detail(?:\.update)?\([^)]*["']query["']\s*:/s)
})

test('V3-08 API separates event collection from school-level metric reading', () => {
  assert.match(apiSource, /@router\.post\("\/events"/)
  assert.match(apiSource, /@router\.get\("\/summary"/)
  assert.match(apiSource, /Depends\(get_current_user\)/)
  assert.match(apiSource, /enforce_permission\(user, "systemAdmin\.audit\.view"\)/)
  assert.match(routerSource, /help_metrics_router/)
})

test('V3-08 page records searches, article views and explicit solved feedback', () => {
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
  ]) assert.match(viewSource, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
})
