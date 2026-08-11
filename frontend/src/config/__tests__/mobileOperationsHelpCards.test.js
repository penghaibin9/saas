import test from 'node:test'
import assert from 'node:assert/strict'
import { MOBILE_OPERATIONS_HELP_CARDS } from '../help/mobileOperationsHelpCards.js'
import { buildHelpSearchText, isHelpVisibleForRole } from '../helpCenterCore.js'

const EXPECTED_IDS = [
  'mobile-student-orientation-collect',
  'mobile-student-affairs-leave',
  'mobile-student-academic-selection',
  'mobile-teacher-grade-entry'
]

test('second mobile batch stays route-safe and role-scoped', () => {
  assert.deepEqual(MOBILE_OPERATIONS_HELP_CARDS.map((card) => card.id), EXPECTED_IDS)
  for (const card of MOBILE_OPERATIONS_HELP_CARDS) {
    assert.equal(card.route, undefined)
    assert.match(card.mobilePath, /^pages\//)
    assert.deepEqual(card.platforms, ['微信小程序'])
  }
  const grade = MOBILE_OPERATIONS_HELP_CARDS.find((card) => card.id === 'mobile-teacher-grade-entry')
  assert.equal(isHelpVisibleForRole(grade, 'teacher'), true)
  assert.equal(isHelpVisibleForRole(grade, 'student'), false)
})

test('orientation guide preserves readonly identity and network failure semantics', () => {
  const text = buildHelpSearchText(MOBILE_OPERATIONS_HELP_CARDS.find((card) => card.id === 'mobile-student-orientation-collect'))
  assert.match(text, /学院、专业、班级.*不是.*自行改/)
  assert.match(text, /6~20 位数字/)
  assert.match(text, /网络异常.*提交未成功/)
})

test('student affairs leave guide preserves returned resubmit extension cancel and allowedActions', () => {
  const text = buildHelpSearchText(MOBILE_OPERATIONS_HELP_CARDS.find((card) => card.id === 'mobile-student-affairs-leave'))
  assert.match(text, /allowedactions/)
  assert.match(text, /修改后重提/)
  assert.match(text, /修改已保存，但重新提交失败/)
  assert.match(text, /续假/)
  assert.match(text, /销假/)
  assert.match(text, /5~300 字/)
  assert.match(text, /版本/)
})

test('selection guide does not treat displayed capacity as final transaction truth', () => {
  const text = buildHelpSearchText(MOBILE_OPERATIONS_HELP_CARDS.find((card) => card.id === 'mobile-student-academic-selection'))
  assert.match(text, /加载时快照/)
  assert.match(text, /最终能否选上以后端事务校验结果为准/)
  assert.match(text, /selected/)
})

test('teacher grade guide locks sensitive in-memory edits and pre-submit quality report', () => {
  const text = buildHelpSearchText(MOBILE_OPERATIONS_HELP_CARDS.find((card) => card.id === 'mobile-teacher-grade-entry'))
  assert.match(text, /0~100 整数/)
  assert.match(text, /缺考、缓考、免修、作弊/)
  assert.match(text, /当前页面内存/)
  assert.match(text, /不把成绩草稿持久化/)
  assert.match(text, /未保存.*离开.*丢失/)
  assert.match(text, /质量报告/)
  assert.match(text, /提交学院审核后教师端变只读/)
  assert.match(text, /returned/)
})

test('generic teacher approval is intentionally excluded until return and reject are distinct', () => {
  assert.equal(MOBILE_OPERATIONS_HELP_CARDS.some((card) => card.id === 'mobile-teacher-generic-approval'), false)
})
