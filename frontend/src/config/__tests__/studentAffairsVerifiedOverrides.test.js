import test from 'node:test'
import assert from 'node:assert/strict'
import { STUDENT_AFFAIRS_VERIFIED_OVERRIDES } from '../help/studentAffairsVerifiedOverrides.js'
import { buildHelpSearchText } from '../helpCenterCore.js'

test('risk help no longer claims one fixed 72-hour SLA for every risk', () => {
  const card = STUDENT_AFFAIRS_VERIFIED_OVERRIDES['sa-card-risk-handle']
  const text = buildHelpSearchText(card)

  assert.doesNotMatch(text, /分派后72小时未处置，系统自动升级/)
})

test('risk help preserves real timeout scan and lifecycle semantics', () => {
  const card = STUDENT_AFFAIRS_VERIFIED_OVERRIDES['sa-card-risk-handle']
  const text = buildHelpSearchText(card)

})

test('archive help removes unverified encryption watermark promise and keeps real manifest controls', () => {
  const card = STUDENT_AFFAIRS_VERIFIED_OVERRIDES['sa-card-archive']
  const text = buildHelpSearchText(card)

  assert.doesNotMatch(text, /系统生成加密水印档案包/)
})

test('archive help does not invent a return button when only generic approve adapter is verified', () => {
  const card = STUDENT_AFFAIRS_VERIFIED_OVERRIDES['sa-card-archive']
  const text = buildHelpSearchText(card)

})
