import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

test('native document preview failure uses a fixed user-facing message', () => {
  const source = fs.readFileSync(new URL('../src/services/fileSdk.js', import.meta.url), 'utf8')
  assert.match(source, /fail: \(\) => reject\(\{ code: 'PREVIEW_FAILED', biz: true, message: '当前文件无法预览，请在 PC 端查看' \}\)/)
  assert.doesNotMatch(source, /PREVIEW_FAILED[^\n]+errMsg/)
})
