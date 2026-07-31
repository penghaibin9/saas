import assert from 'node:assert/strict'
import test from 'node:test'

import { localizeVisibleEnumText } from '../src/services/visibleEnumLocalization.js'

test('明确状态枚举 PENDING_REVIEW 显示为待审核', () => {
  assert.equal(localizeVisibleEnumText('PENDING_REVIEW'), '待审核')
})

test('明确请假类型 PERSONAL 显示为事假', () => {
  assert.equal(localizeVisibleEnumText('PERSONAL'), '事假')
})

test('普通正文中的 OPEN、HOME、ACTIVE 保持原文', () => {
  const body = '普通正文 OPEN HOME ACTIVE 保持原文'
  assert.equal(localizeVisibleEnumText(body), body)
})

test('未知业务原文不会被改写', () => {
  assert.equal(localizeVisibleEnumText('ACME_OPEN_HOME'), 'ACME_OPEN_HOME')
  assert.equal(localizeVisibleEnumText('课程名 OPEN 设计基础'), '课程名 OPEN 设计基础')
})
