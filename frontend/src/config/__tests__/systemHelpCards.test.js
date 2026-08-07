import test from 'node:test'
import assert from 'node:assert/strict'
import { SYSTEM_HELP_CARDS } from '../help/systemHelpCards.js'
import { buildHelpSearchText, isHelpVisibleForRole } from '../helpCenterCore.js'

const EXPECTED_IDS = [
  'sys-card-staff-account-role',
  'sys-card-role-permission-scope',
  'sys-card-org-foundation',
  'sys-card-student-import',
  'sys-card-import-error-receipt',
  'sys-card-access-diagnosis',
  'sys-card-account-exception'
]

test('system help cards keep stable unique ids', () => {
  assert.deepEqual(SYSTEM_HELP_CARDS.map((card) => card.id), EXPECTED_IDS)
  assert.equal(new Set(EXPECTED_IDS).size, EXPECTED_IDS.length)
})

test('system help cards are complete school-admin task cards', () => {
  for (const card of SYSTEM_HELP_CARDS) {
    assert.ok(card.title)
    assert.ok(card.summary)
    assert.ok(Array.isArray(card.keywords) && card.keywords.length > 0)
    assert.ok(Array.isArray(card.roles) && card.roles.length > 0)
    assert.ok(Array.isArray(card.steps) && card.steps.length >= 3)
    assert.match(card.route, /^\/admin\/system\//)
    assert.equal(isHelpVisibleForRole(card, 'school-admin'), true)
    assert.equal(isHelpVisibleForRole(card, 'teacher'), false)
  }
})

test('critical system help terms are searchable from nested content', () => {
  const importCard = SYSTEM_HELP_CARDS.find((card) => card.id === 'sys-card-student-import')
  const accessCard = SYSTEM_HELP_CARDS.find((card) => card.id === 'sys-card-access-diagnosis')
  const exceptionCard = SYSTEM_HELP_CARDS.find((card) => card.id === 'sys-card-account-exception')

  assert.match(buildHelpSearchText(importCard), /错误行/)
  assert.match(buildHelpSearchText(importCard), /初始账号凭据/)
  assert.match(buildHelpSearchText(accessCard), /403/)
  assert.match(buildHelpSearchText(accessCard), /判定链/)
  assert.match(buildHelpSearchText(exceptionCard), /学籍主档 id/i)
})
