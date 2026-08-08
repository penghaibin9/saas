import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS } from '../help/highFrequencyTroubleshootingHelpCards.js'
import { HELP_V3_QUICK_QUESTIONS } from '../help/helpCenterV3.js'

const here = dirname(fileURLToPath(import.meta.url))
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')
const responseSource = readFileSync(resolve(here, '../../../../backend/app/core/response.py'), 'utf8')
const excelSource = readFileSync(resolve(here, '../../components/common/excel/AppExcelImportDrawer.vue'), 'utf8')

const IDS = [
  'tr-v3-permission-scope-403',
  'tr-v3-version-conflict-409',
  'tr-v3-assignee-not-configured',
  'tr-v3-returned-cannot-continue',
  'tr-v3-publish-blocked',
  'tr-v3-import-error-rows',
  'tr-v3-todo-still-pending',
  'tr-v3-sensitive-data-denied'
]

function body(id) {
  return JSON.stringify(HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS.find((card) => card.id === id))
}

test('V3-05 starts with eight verified self-service fault cards', () => {
  assert.deepEqual(HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS.map((card) => card.id), IDS)
  for (const card of HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS) {
    for (const field of ['roles', 'entry', 'steps', 'prerequisites', 'permissions', 'successCriteria', 'troubleshooting', 'nextSteps', 'contactAdminWhen']) {
      assert.ok(Array.isArray(card[field]) ? card[field].length > 0 : Boolean(card[field]), `${card.id} missing ${field}`)
    }
    assert.ok(card.authorizationPrinciple, `${card.id} missing authorizationPrinciple`)
    assert.ok(card.keywords?.length, `${card.id} missing keywords`)
  }
})

test('403 and 409 cards follow the frozen backend response contract', () => {
  assert.match(responseSource, /"NO_PERMISSION": 403001/)
  assert.match(responseSource, /"NO_DATA_SCOPE": 403002/)
  assert.match(responseSource, /"DATA_CONFLICT": 409001/)
  assert.match(responseSource, /"APPROVAL_VERSION_CONFLICT": 409001/)
  assert.match(responseSource, /"IDEMPOTENCY_CONFLICT": 409001/)

  const permission = body('tr-v3-permission-scope-403')
  assert.match(permission, /NO_PERMISSION/)
  assert.match(permission, /NO_DATA_SCOPE/)
  assert.match(permission, /403001/)
  assert.match(permission, /403002/)

  const conflict = body('tr-v3-version-conflict-409')
  assert.match(conflict, /APPROVAL_VERSION_CONFLICT/)
  assert.match(conflict, /IDEMPOTENCY_CONFLICT/)
  assert.match(conflict, /expectedVersion/)
})

test('assignee and returned cards teach repair instead of bypass', () => {
  assert.match(responseSource, /"ASSIGNEE_NOT_CONFIGURED": 400001/)
  const assignee = body('tr-v3-assignee-not-configured')
  assert.match(assignee, /WorkflowTask/)
  assert.match(assignee, /UnifiedTodo/)
  assert.match(assignee, /不能.*绕过|不要绕过/)

  const returned = body('tr-v3-returned-cannot-continue')
  assert.match(returned, /RETURNED/)
  assert.match(returned, /REJECTED/)
  assert.match(returned, /RESUBMIT/)
  assert.match(returned, /allowedActions/)
})

test('Excel fault card matches the common preview and error-row contract', () => {
  for (const token of ['invalidRows', 'previewToken', '下载错误行', '失败数据未导入']) {
    assert.match(excelSource, new RegExp(token))
  }
  const text = body('tr-v3-import-error-rows')
  assert.match(text, /invalidRows/)
  assert.match(text, /previewToken/)
  assert.match(text, /错误行/)
})

test('V3-05 cards are published only through the verified runtime', () => {
  assert.match(runtimeSource, /HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS/)
  assert.match(runtimeSource, /\.\.\.HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS\.map\(\(item\) => item\.id\)/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS\)/)
  assert.match(runtimeSource, /troubleshooting-v3-cards/)
})

test('problem-mode quick questions can reach the first troubleshooting library', () => {
  const queries = HELP_V3_QUICK_QUESTIONS.map((item) => item.query)
  for (const query of ['权限', '退回', '数据范围', '409', '发布', '错误行', '待办']) {
    assert.ok(queries.includes(query), `${query} must remain a quick problem entry`)
  }
  const corpus = JSON.stringify(HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS)
  for (const query of queries) {
    assert.ok(corpus.includes(query) || query === '提交', `quick question ${query} should match V3-05 or existing task knowledge`)
  }
})
