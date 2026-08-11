import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/modules/messageCenter/views/MessageComposeView.vue', import.meta.url), 'utf8')

test('消息深链业务 ID 始终按不透明字符串传递', () => {
  assert.doesNotMatch(source, /Number\(value\)/)
  assert.doesNotMatch(source, /parseInt\(value/)
  assert.match(source, /params\[key\] = value/)
})
