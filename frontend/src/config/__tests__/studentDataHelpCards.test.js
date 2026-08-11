import test from 'node:test'
import assert from 'node:assert/strict'
import { STUDENT_DATA_HELP_CARDS } from '../help/studentDataHelpCards.js'
import { buildHelpSearchText, isHelpVisibleForRole } from '../helpCenterCore.js'

const EXPECTED_IDS = [
  'student-card-single-create',
  'student-card-list-filter',
  'student-card-secure-export'
]

test('student data help cards keep stable unique ids and real routes', () => {
  assert.deepEqual(STUDENT_DATA_HELP_CARDS.map((card) => card.id), EXPECTED_IDS)
  assert.equal(new Set(EXPECTED_IDS).size, EXPECTED_IDS.length)
  for (const card of STUDENT_DATA_HELP_CARDS) {
    assert.ok(card.route.startsWith('/admin/student/'))
    assert.ok(card.title)
    assert.ok(card.summary)
    assert.ok(Array.isArray(card.steps) && card.steps.length >= 3)
  }
})

test('student data guides preserve intended role visibility', () => {
  const create = STUDENT_DATA_HELP_CARDS.find((card) => card.id === 'student-card-single-create')
  const list = STUDENT_DATA_HELP_CARDS.find((card) => card.id === 'student-card-list-filter')
  const exportCard = STUDENT_DATA_HELP_CARDS.find((card) => card.id === 'student-card-secure-export')

  assert.equal(isHelpVisibleForRole(create, 'academic'), true)
  assert.equal(isHelpVisibleForRole(create, 'student'), false)
  assert.equal(isHelpVisibleForRole(list, 'student-affairs'), true)
  assert.equal(isHelpVisibleForRole(exportCard, 'academic'), true)
})

test('single create guide preserves permanent student number and controlled restore rules', () => {
  const card = STUDENT_DATA_HELP_CARDS.find((item) => item.id === 'student-card-single-create')
  const text = buildHelpSearchText(card)
  assert.match(text, /永久唯一/)
  assert.match(text, /已作废/)
  assert.match(text, /原 studentId/i)
  assert.match(text, /不会自动恢复登录账号/)
  assert.match(text, /student\.profile\.restore/)
})

test('secure export guide states backend truth and does not promise selected-row isolation', () => {
  const card = STUDENT_DATA_HELP_CARDS.find((item) => item.id === 'student-card-secure-export')
  const text = buildHelpSearchText(card)
  assert.match(text, /当前数据范围/)
  assert.match(text, /手机号脱敏/)
  assert.match(text, /首行/)
  assert.match(text, /任务归属/)
  assert.match(text, /导出所选/)
  assert.match(text, /并未接收前端所选学生 id/i)
})
