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
