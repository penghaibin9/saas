import test from 'node:test'
import assert from 'node:assert/strict'
import { MOBILE_HELP_CARDS } from '../help/mobileHelpCards.js'
import { buildHelpSearchText, isHelpVisibleForRole } from '../helpCenterCore.js'

const EXPECTED_IDS = [
  'mobile-student-internship-checkin',
  'mobile-student-internship-weekly',
  'mobile-student-graduation-topic',
  'mobile-teacher-todos',
  'mobile-teacher-internship-process',
  'mobile-teacher-graduation-topic-review'
]

test('mobile help cards keep stable ids and never expose miniapp paths as PC routes', () => {
  assert.deepEqual(MOBILE_HELP_CARDS.map((card) => card.id), EXPECTED_IDS)
  assert.equal(new Set(EXPECTED_IDS).size, EXPECTED_IDS.length)
  for (const card of MOBILE_HELP_CARDS) {
    assert.equal(card.route, undefined)
    assert.match(card.mobilePath, /^pages\//)
    assert.deepEqual(card.platforms, ['微信小程序'])
    assert.ok(card.entry.includes('小程序'))
    assert.ok(Array.isArray(card.steps) && card.steps.length >= 4)
  }
})

test('student and teacher mobile cards stay role-separated', () => {
  const studentCheckin = MOBILE_HELP_CARDS.find((card) => card.id === 'mobile-student-internship-checkin')
  const teacherInternship = MOBILE_HELP_CARDS.find((card) => card.id === 'mobile-teacher-internship-process')

  assert.equal(isHelpVisibleForRole(studentCheckin, 'student'), true)
  assert.equal(isHelpVisibleForRole(studentCheckin, 'teacher'), false)
  assert.equal(isHelpVisibleForRole(teacherInternship, 'teacher'), true)
  assert.equal(isHelpVisibleForRole(teacherInternship, 'student'), false)
})

test('student checkin guide preserves privacy, no-location and non-cheating semantics', () => {
  const card = MOBILE_HELP_CARDS.find((item) => item.id === 'mobile-student-internship-checkin')
  const text = buildHelpSearchText(card)
  assert.match(text, /只在.*一次定位/)
  assert.match(text, /不后台持续定位/)
  assert.match(text, /无定位打卡/)
  assert.match(text, /人工核实/)
  assert.match(text, /不是.*自动作弊判定/)
  assert.match(text, /网络异常.*未成功/)
})

test('student weekly guide locks minimum length, duplicate and network semantics', () => {
  const card = MOBILE_HELP_CARDS.find((item) => item.id === 'mobile-student-internship-weekly')
  const text = buildHelpSearchText(card)
  assert.match(text, /至少 10 个字/)
  assert.match(text, /不要重复提交/)
  assert.match(text, /网络异常.*提交未成功/)
  assert.match(text, /导师批阅/)
})

test('teacher internship guide preserves return reason, offline guard and manual abnormal judgement', () => {
  const card = MOBILE_HELP_CARDS.find((item) => item.id === 'mobile-teacher-internship-process')
  const text = buildHelpSearchText(card)
  assert.match(text, /退回意见至少 5 个字/)
  assert.match(text, /离线.*不能/)
  assert.match(text, /认定有效/)
  assert.match(text, /异常计入/)
  assert.match(text, /人工判断/)
  assert.match(text, /409/)
  assert.match(text, /消息推送功能开放前/)
})

test('teacher todo guide does not claim quick action bypasses business workflow', () => {
  const card = MOBILE_HELP_CARDS.find((item) => item.id === 'mobile-teacher-todos')
  const text = buildHelpSearchText(card)
  assert.match(text, /“快速处理”.*进入对应业务办理页/)
  assert.match(text, /不是.*一键跳过/)
})

test('graduation mobile guides preserve choice and change-review constraints', () => {
  const student = MOBILE_HELP_CARDS.find((item) => item.id === 'mobile-student-graduation-topic')
  const teacher = MOBILE_HELP_CARDS.find((item) => item.id === 'mobile-teacher-graduation-topic-review')
  const studentText = buildHelpSearchText(student)
  const teacherText = buildHelpSearchText(teacher)

  assert.match(studentText, /点选顺序就是志愿/)
  assert.match(studentText, /至少 5 个字/)
  assert.match(studentText, /matched \/ confirmed/)
  assert.match(teacherText, /同一轮其他志愿会自动关闭/)
  assert.match(teacherText, /403\/no_permission\/no_data_scope/)
  assert.match(teacherText, /409\/data_conflict/)
})
