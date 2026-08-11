import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/components/MobileStatusTag.vue', import.meta.url), 'utf8')

test('MobileStatusTag 未知状态不回显 raw code', () => {
  assert.match(source, /状态待确认/)
  assert.doesNotMatch(source, /this\.mapped \? this\.mapped\.label : this\.status/)
})
