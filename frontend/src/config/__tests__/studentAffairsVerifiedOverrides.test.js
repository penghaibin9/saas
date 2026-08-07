import test from 'node:test'
import assert from 'node:assert/strict'
import { STUDENT_AFFAIRS_VERIFIED_OVERRIDES } from '../help/studentAffairsVerifiedOverrides.js'
import { buildHelpSearchText } from '../helpCenterCore.js'

test('risk help no longer claims one fixed 72-hour SLA for every risk', () => {
  const card = STUDENT_AFFAIRS_VERIFIED_OVERRIDES['sa-card-risk-handle']
  const text = buildHelpSearchText(card)

  assert.match(text, /按风险等级/)
  assert.match(text, /当前生效 sla/)
  assert.match(text, /critical 24小时/)
  assert.match(text, /high 48小时/)
  assert.match(text, /medium 72小时/)
  assert.match(text, /low 120小时/)
  assert.match(text, /学校配置可覆盖/)
  assert.doesNotMatch(text, /分派后72小时未处置，系统自动升级/)
})

test('risk help preserves real timeout scan and lifecycle semantics', () => {
  const card = STUDENT_AFFAIRS_VERIFIED_OVERRIDES['sa-card-risk-handle']
  const text = buildHelpSearchText(card)

  assert.match(text, /assignhours/)
  assert.match(text, /processhours/)
  assert.match(text, /followhours/)
  assert.match(text, /new.*自动分派/s)
  assert.match(text, /assigned \/ processing \/ following.*自动升级/s)
  assert.match(text, /escalated/)
  assert.match(text, /关闭前必须至少有1条处置记录/)
  assert.match(text, /重开/)
})

test('archive help removes unverified encryption watermark promise and keeps real manifest controls', () => {
  const card = STUDENT_AFFAIRS_VERIFIED_OVERRIDES['sa-card-archive']
  const text = buildHelpSearchText(card)

  assert.match(text, /draft → collecting → college_review → sa_confirm → archived/)
  assert.match(text, /xlsx/)
  assert.match(text, /manifest/)
  assert.match(text, /sha-256/)
  assert.match(text, /导出任务/)
  assert.match(text, /(未完成档案包.*阻止归档|未生成完成.*不能进入 archived|档案包.*必须全部生成完成)/)
  assert.match(text, /没有证据.*“加密水印”/)
  assert.doesNotMatch(text, /系统生成加密水印档案包/)
})

test('archive help does not invent a return button when only generic approve adapter is verified', () => {
  const card = STUDENT_AFFAIRS_VERIFIED_OVERRIDES['sa-card-archive']
  const text = buildHelpSearchText(card)

  assert.match(text, /advance.*只接受 approve/)
  assert.match(text, /不再宣称“绝对没有退回”/)
  assert.match(text, /不虚构.*退回按钮/)
})
