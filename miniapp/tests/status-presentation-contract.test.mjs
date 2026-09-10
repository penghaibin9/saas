import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/components/MobileStatusTag.vue', import.meta.url), 'utf8')

test('MobileStatusTag 未知状态不回显 raw code', () => {
  assert.match(source, /状态待确认/)
  assert.doesNotMatch(source, /this\.mapped \? this\.mapped\.label : this\.status/)
})

test('成绩复查终态使用正式业务文案', () => {
  assert.match(source, /UPHELD:\s*\{\s*label:\s*'维持原成绩'/)
  assert.match(source, /ADJUSTED:\s*\{\s*label:\s*'成绩已调整'/)
})
