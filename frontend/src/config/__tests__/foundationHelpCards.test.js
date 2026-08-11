import test from 'node:test'
import assert from 'node:assert/strict'
import { FOUNDATION_HELP_CARDS } from '../help/foundationHelpCards.js'
import { buildHelpSearchText, isHelpVisibleForRole } from '../helpCenterCore.js'

const EXPECTED_IDS = [
  'sys-card-first-school-setup',
  'auth-card-staff-login-password',
  'sys-card-login-security-policy',
  'aa-card-term-setup'
]

test('foundation help cards keep stable unique ids and routes', () => {
  assert.deepEqual(FOUNDATION_HELP_CARDS.map((card) => card.id), EXPECTED_IDS)
  assert.equal(new Set(EXPECTED_IDS).size, EXPECTED_IDS.length)
  for (const card of FOUNDATION_HELP_CARDS) {
    assert.ok(card.route.startsWith('/'))
    assert.ok(card.title)
    assert.ok(card.summary)
    assert.ok(Array.isArray(card.steps) && card.steps.length >= 3)
  }
})

test('foundation cards keep role visibility aligned with intended users', () => {
  const setup = FOUNDATION_HELP_CARDS.find((card) => card.id === 'sys-card-first-school-setup')
  const login = FOUNDATION_HELP_CARDS.find((card) => card.id === 'auth-card-staff-login-password')
  const term = FOUNDATION_HELP_CARDS.find((card) => card.id === 'aa-card-term-setup')

  assert.equal(isHelpVisibleForRole(setup, 'school-admin'), true)
  assert.equal(isHelpVisibleForRole(setup, 'teacher'), false)
  assert.equal(isHelpVisibleForRole(login, 'teacher'), true)
  assert.equal(isHelpVisibleForRole(login, 'academic'), true)
  assert.equal(isHelpVisibleForRole(login, 'student'), false)
  assert.equal(isHelpVisibleForRole(term, 'academic'), true)
})

test('foundation search corpus preserves verified limitations and term rules', () => {
  const login = FOUNDATION_HELP_CARDS.find((card) => card.id === 'auth-card-staff-login-password')
  const security = FOUNDATION_HELP_CARDS.find((card) => card.id === 'sys-card-login-security-policy')
  const term = FOUNDATION_HELP_CARDS.find((card) => card.id === 'aa-card-term-setup')

  assert.match(buildHelpSearchText(login), /联系本校系统管理员/)
  assert.match(buildHelpSearchText(login), /6 位验证码/)
  assert.match(buildHelpSearchText(security), /平台底线/)
  assert.match(buildHelpSearchText(term), /2026-2027/)
  assert.match(buildHelpSearchText(term), /当前学期/)
})
