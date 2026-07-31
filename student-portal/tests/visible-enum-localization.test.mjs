import assert from 'node:assert/strict'
import test from 'node:test'

import {
  localizeStatusSuffixText,
  localizeTrailingEnumInParentheses,
  localizeVisibleEnumText
} from '../src/services/visibleEnumLocalization.js'

test('明确状态枚举 PENDING_REVIEW 显示为待审核', () => {
  assert.equal(localizeVisibleEnumText('PENDING_REVIEW'), '待审核')
})

test('明确请假类型 PERSONAL 显示为事假', () => {
  assert.equal(localizeVisibleEnumText('PERSONAL'), '事假')
})

test('普通正文中的 OPEN、HOME、ACTIVE 保持原文', () => {
  const body = '普通正文 OPEN HOME ACTIVE 保持原文'
  assert.equal(localizeVisibleEnumText(body), body)
  assert.equal(localizeStatusSuffixText(body), body)
  assert.equal(localizeTrailingEnumInParentheses(body), body)
})

test('只转换明确的状态句尾和申请类型括号', () => {
  assert.equal(localizeStatusSuffixText('你的请假申请当前状态：PENDING_REVIEW'), '你的请假申请当前状态：待审核')
  assert.equal(localizeTrailingEnumInParentheses('学生请假（PERSONAL）'), '学生请假（事假）')
})

test('未知业务原文不会被改写', () => {
  assert.equal(localizeVisibleEnumText('ACME_OPEN_HOME'), 'ACME_OPEN_HOME')
  assert.equal(localizeVisibleEnumText('课程名 OPEN 设计基础'), '课程名 OPEN 设计基础')
  assert.equal(localizeStatusSuffixText('企业名 ACME_OPEN_HOME'), '企业名 ACME_OPEN_HOME')
  assert.equal(localizeTrailingEnumInParentheses('材料名（ACME_OPEN_HOME）'), '材料名（ACME_OPEN_HOME）')
})
