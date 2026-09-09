import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(
  new URL('../src/modules/system/api/system.api.js', import.meta.url),
  'utf8'
)

test('permission-only role saves preserve an existing CUSTOM scope target', () => {
  assert.match(source, /if \(scopeTarget !== undefined\) body\.scopeTarget = scopeTarget/)
  assert.doesNotMatch(source, /scopeTarget:\s*scopeTarget\s*\|\|\s*\{\}/)
})
