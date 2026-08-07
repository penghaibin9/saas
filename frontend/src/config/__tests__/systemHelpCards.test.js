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

test('V2 system help cards satisfy the seven operational dimensions', () => {
  for (const card of SYSTEM_HELP_CARDS) {
    assert.ok(card.title)
    assert.ok(card.summary)
    assert.ok(Array.isArray(card.keywords) && card.keywords.length > 0)
    assert.ok(Array.isArray(card.roles) && card.roles.length > 0, `${card.id}: roles`)
    assert.ok(card.entry, `${card.id}: entry`)
    assert.ok(Array.isArray(card.steps) && card.steps.length >= 3, `${card.id}: steps`)
    assert.ok(Array.isArray(card.prerequisites) && card.prerequisites.length > 0, `${card.id}: prerequisites`)
    assert.ok(Array.isArray(card.successCriteria) && card.successCriteria.length > 0, `${card.id}: successCriteria`)
    assert.ok(Array.isArray(card.troubleshooting) && card.troubleshooting.length > 0, `${card.id}: troubleshooting`)
    assert.ok(Array.isArray(card.permissions) && card.permissions.length > 0, `${card.id}: permissions`)
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
  assert.match(buildHelpSearchText(importCard), /下载权限/)
  assert.match(buildHelpSearchText(accessCard), /403/)
  assert.match(buildHelpSearchText(accessCard), /判定链/)
  assert.match(buildHelpSearchText(accessCard), /数据范围/)
  assert.match(buildHelpSearchText(exceptionCard), /学籍主档 id/i)
  assert.match(buildHelpSearchText(exceptionCard), /高风险权限动作/)
})
