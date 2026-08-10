import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS } from '../help/highFrequencyTroubleshootingHelpCards.js'
import { HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS } from '../help/highFrequencyTroubleshootingHelpCardsV305B.js'
import { HIGH_FREQUENCY_TROUBLESHOOTING_V305C_CARDS } from '../help/highFrequencyTroubleshootingHelpCardsV305C.js'
import { HELP_V3_QUICK_QUESTIONS } from '../help/helpCenterV3.js'

const here = dirname(fileURLToPath(import.meta.url))
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')
const responseSource = readFileSync(resolve(here, '../../../../backend/app/core/response.py'), 'utf8')
const exceptionSource = readFileSync(resolve(here, '../../../../backend/app/core/exceptions.py'), 'utf8')
const excelSource = readFileSync(resolve(here, '../../components/common/excel/AppExcelImportDrawer.vue'), 'utf8')
const fileApiSource = readFileSync(resolve(here, '../../../../backend/app/api/v1/file.py'), 'utf8')
const dataExchangeSource = readFileSync(resolve(here, '../../../../backend/app/api/v1/data_exchange.py'), 'utf8')

const FIRST_IDS = [
  'tr-v3-permission-scope-403',
  'tr-v3-version-conflict-409',
  'tr-v3-assignee-not-configured',
  'tr-v3-returned-cannot-continue',
  'tr-v3-publish-blocked',
  'tr-v3-import-error-rows',
  'tr-v3-todo-still-pending',
  'tr-v3-sensitive-data-denied'
]

const SECOND_IDS = [
  'tr-v3-login-auth-401',
  'tr-v3-module-readonly',
  'tr-v3-file-upload',
  'tr-v3-rate-limited-429',
  'tr-v3-export-job',
  'tr-v3-service-5xx'
]

const CLOSEOUT_IDS = [
  'tr-v3-validation-400',
  'tr-v3-not-found-404'
]

const ALL_CARDS = [
  ...HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS,
  ...HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS,
  ...HIGH_FREQUENCY_TROUBLESHOOTING_V305C_CARDS
]

function body(id) {
  return JSON.stringify(ALL_CARDS.find((card) => card.id === id))
}

function assertSelfServiceContract(card) {
  for (const field of ['roles', 'entry', 'steps', 'prerequisites', 'permissions', 'successCriteria', 'troubleshooting', 'nextSteps', 'contactAdminWhen']) {
    assert.ok(Array.isArray(card[field]) ? card[field].length > 0 : Boolean(card[field]), `${card.id} missing ${field}`)
  }
  assert.ok(card.authorizationPrinciple, `${card.id} missing authorizationPrinciple`)
  assert.ok(card.keywords?.length, `${card.id} missing keywords`)
}

test('V3-05 closes with sixteen verified self-service fault cards', () => {
  assert.deepEqual(HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS.map((card) => card.id), FIRST_IDS)
  assert.deepEqual(HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS.map((card) => card.id), SECOND_IDS)
  assert.deepEqual(HIGH_FREQUENCY_TROUBLESHOOTING_V305C_CARDS.map((card) => card.id), CLOSEOUT_IDS)
  assert.equal(ALL_CARDS.length, 16)
  for (const card of ALL_CARDS) assertSelfServiceContract(card)
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

test('second batch follows auth, module, rate-limit and service-error contracts', () => {
  for (const pattern of [
    /"UNAUTHORIZED": 401/,
    /"WECHAT_AUTH_REQUIRED": 401/,
    /"MODULE_NOT_AUTHORIZED": 403/,
    /"MODULE_EXPIRED_READONLY": 403/,
    /"RATE_LIMITED": 429/,
    /"TENANT_GUARD_UNAVAILABLE": 503/,
    /"SERVER_ERROR": 500/
  ]) assert.match(exceptionSource, pattern)

  assert.match(body('tr-v3-login-auth-401'), /UNAUTHORIZED/)
  assert.match(body('tr-v3-login-auth-401'), /WECHAT_AUTH_REQUIRED/)
  assert.match(body('tr-v3-module-readonly'), /MODULE_NOT_AUTHORIZED/)
  assert.match(body('tr-v3-module-readonly'), /MODULE_EXPIRED_READONLY/)
  assert.match(body('tr-v3-rate-limited-429'), /RATE_LIMITED/)
  assert.match(body('tr-v3-service-5xx'), /traceId/)
  assert.match(body('tr-v3-service-5xx'), /fail-closed/)
})

test('closeout cards follow validation and not-found contracts', () => {
  assert.match(exceptionSource, /"VALIDATION_ERROR": 400/)
  assert.match(exceptionSource, /"REJECT_REASON_REQUIRED": 400/)
  assert.match(exceptionSource, /"DATA_NOT_FOUND": 404/)
  assert.match(exceptionSource, /"TENANT_NOT_FOUND": 404/)
  assert.match(exceptionSource, /"ROLE_NOT_FOUND": 404/)
  assert.match(exceptionSource, /RequestValidationError/)
  assert.match(exceptionSource, /"field"/)

  const validation = body('tr-v3-validation-400')
  assert.match(validation, /VALIDATION_ERROR/)
  assert.match(validation, /REJECT_REASON_REQUIRED/)
  assert.match(validation, /field\/msg/)

  const notFound = body('tr-v3-not-found-404')
  assert.match(notFound, /DATA_NOT_FOUND/)
  assert.match(notFound, /404/)
  assert.match(notFound, /不反复修改 URL|不手工拼接路径/)
})

test('file-upload fault card follows upload-session and scan contracts', () => {
  for (const token of ['FILE_TYPE_NOT_ALLOWED', 'FILE_TOO_LARGE', '/upload-sessions', '/scan-status', 'readyForBusiness']) {
    assert.match(fileApiSource, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  const text = body('tr-v3-file-upload')
  assert.match(text, /FILE_TYPE_NOT_ALLOWED/)
  assert.match(text, /FILE_TOO_LARGE/)
  assert.match(text, /scanStatus/)
  assert.match(text, /readyForBusiness/)
})

test('export fault card follows the real task-center download-ticket contract', () => {
  assert.match(dataExchangeSource, /\/exports\/\{job_id\}/)
  assert.match(dataExchangeSource, /download-ticket/)
  assert.match(dataExchangeSource, /创建短时一次性下载票据/)
  assert.match(dataExchangeSource, /撤销导出任务并使票据失效/)
  const text = body('tr-v3-export-job')
  assert.match(text, /ExportJob/)
  assert.match(text, /SUCCEEDED/)
  assert.match(text, /EXPIRED/)
  assert.match(text, /download-ticket/)
})

test('V3-05 cards are published only through the verified runtime', () => {
  assert.match(runtimeSource, /HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS/)
  assert.match(runtimeSource, /HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS/)
  assert.match(runtimeSource, /HIGH_FREQUENCY_TROUBLESHOOTING_V305C_CARDS/)
  assert.match(runtimeSource, /\.\.\.HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS\.map\(\(item\) => item\.id\)/)
  assert.match(runtimeSource, /\.\.\.HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS\.map\(\(item\) => item\.id\)/)
  assert.match(runtimeSource, /\.\.\.HIGH_FREQUENCY_TROUBLESHOOTING_V305C_CARDS\.map\(\(item\) => item\.id\)/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS\)/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(HIGH_FREQUENCY_TROUBLESHOOTING_V305B_CARDS\)/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(HIGH_FREQUENCY_TROUBLESHOOTING_V305C_CARDS\)/)
  assert.match(runtimeSource, /troubleshooting-v3-cards/)
})

test('problem-mode quick questions reach the closed troubleshooting library', () => {
  const queries = HELP_V3_QUICK_QUESTIONS.map((item) => item.query)
  for (const query of ['权限', '退回', '数据范围', '409', '发布', '错误行', '待办', '401', '模块未授权', '文件上传', '导出任务', '校验失败', '404']) {
    assert.ok(queries.includes(query), `${query} must remain a quick problem entry`)
  }
  const corpus = JSON.stringify(ALL_CARDS)
  for (const query of queries) {
    assert.ok(corpus.includes(query) || query === '提交', `quick question ${query} should match V3-05 or existing task knowledge`)
  }
})
