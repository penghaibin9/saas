import test from 'node:test'
import assert from 'node:assert/strict'
import { VERIFIED_HELP_OVERRIDES } from '../help/verifiedHelpOverrides.js'
import { buildHelpSearchText } from '../helpCenterCore.js'

test('internship score rule correction enforces five components and exact 100 percent', () => {
  const card = VERIFIED_HELP_OVERRIDES['in-card-batch-rules']
  const text = buildHelpSearchText(card)
  assert.match(text, /打卡/)
  assert.match(text, /周报/)
  assert.match(text, /月报总结/)
  assert.match(text, /企业评价/)
  assert.match(text, /学校评价/)
  assert.match(text, /严格等于 100/)
  assert.doesNotMatch(text, /建议合计为 100/)
})

test('internship score workflow correction exposes real return withdraw republish states', () => {
  const card = VERIFIED_HELP_OVERRIDES['in-card-eval-score']
  const text = buildHelpSearchText(card)
  assert.match(text, /待核算/)
  assert.match(text, /待复核/)
  assert.match(text, /已发布/)
  assert.match(text, /已撤回/)
  assert.match(text, /已归档/)
  assert.match(text, /不少于 5 个字/)
  assert.match(text, /撤回后可重新核算/)
  assert.match(text, /最终发布仅限学校管理员/)
  assert.match(text, /企业评价.*不能手工/)
})

test('graduation grade correction uses real ledger, authoritative sources and lifecycle', () => {
  const card = VERIFIED_HELP_OVERRIDES['gd-card-defense-grade']
  const text = buildHelpSearchText(card)

  assert.equal(card.route, '/admin/graduation/grade-ledger')
  assert.match(text, /导师 40%/)
  assert.match(text, /评阅 30%/)
  assert.match(text, /答辩 30%/)
  assert.match(text, /权威评阅/)
  assert.match(text, /权威.*答辩/)
  assert.match(text, /来源快照/)
  assert.match(text, /重新核算/)
  assert.match(text, /待核算\(DRAFT\)/)
  assert.match(text, /已核算\(CALCULATED\)/)
  assert.match(text, /已复核\(REVIEWED\)/)
  assert.match(text, /已发布\(PUBLISHED\)/)
  assert.match(text, /已撤回待重发\(WITHDRAWN\)/)
})

test('graduation appeal correction preserves published-only, single pending and withdraw-recalculate semantics', () => {
  const card = VERIFIED_HELP_OVERRIDES['gd-card-defense-grade']
  const text = buildHelpSearchText(card)
  const appealLink = (card.related || []).find((item) => item.label === '成绩更正申诉')

  assert.equal(appealLink?.route, '/admin/graduation/more?panel=appeals')
  assert.match(text, /只能对已发布成绩发起申诉/)
  assert.match(text, /不少于 5 个字/)
  assert.match(text, /同时只能存在一条待复核申诉/)
  assert.match(text, /受理.*撤回/)
  assert.match(text, /重新核算/)
  assert.match(text, /驳回.*原成绩保持不变/)
  assert.match(text, /不会.*直接改成学生要求的分数/)
})
