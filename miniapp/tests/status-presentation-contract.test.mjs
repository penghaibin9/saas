import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/components/MobileStatusTag.vue', import.meta.url), 'utf8')

test('MobileStatusTag 未知状态不回显 raw code', () => {
  assert.match(source, /状态待确认/)
  assert.doesNotMatch(source, /this\.mapped \? this\.mapped\.label : this\.status/)
  assert.match(source, /HAS_CHINESE_TEXT/)
  assert.match(source, /function readableLabel\(label, mapped\)/)
})

test('统一消息阅读状态使用可读文案，而非未知状态占位', () => {
  assert.match(source, /UNREAD:\s*\{\s*label:\s*'未读'/)
  assert.match(source, /READ:\s*\{\s*label:\s*'已读'/)
  assert.match(source, /SENT:\s*\{\s*label:\s*'已发送'/)
  assert.match(source, /PENDING_ACK:\s*\{\s*label:\s*'待确认'/)
})

test('成绩复查终态使用正式业务文案', () => {
  assert.match(source, /UPHELD:\s*\{\s*label:\s*'维持原成绩'/)
  assert.match(source, /ADJUSTED:\s*\{\s*label:\s*'成绩已调整'/)
})

test('补考重修和专业分流的处理中状态有中文业务文案', () => {
  assert.match(source, /TEACHER_REVIEW:\s*\{\s*label:\s*'任课教师审核中'/)
  assert.match(source, /ALLOCATED:\s*\{\s*label:\s*'已分配'/)
  assert.match(source, /UNALLOCATED:\s*\{\s*label:\s*'待学校调剂'/)
})

test('实习首页使用的已生效、已核验、到岗和无记录状态均有可读文案', () => {
  assert.match(source, /EFFECTIVE:\s*\{\s*label:\s*'已生效'/)
  assert.match(source, /VERIFIED:\s*\{\s*label:\s*'已核验'/)
  assert.match(source, /ONBOARD:\s*\{\s*label:\s*'已到岗'/)
  assert.match(source, /NONE:\s*\{\s*label:\s*'暂无记录'/)
})
