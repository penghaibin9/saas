import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const requestSource = fs.readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
const guardianSource = fs.readFileSync(new URL('../src/services/guardianApi.js', import.meta.url), 'utf8')

test('student and guardian requests use the same-origin Vite proxy when no explicit API origin is configured', () => {
  for (const source of [requestSource, guardianSource]) {
    assert.match(source, /const configuredBase = import\.meta\.env\.VITE_API_BASE_URL/)
    assert.match(source, /if \(configuredBase\) return String\(configuredBase\)\.replace/)
    assert.doesNotMatch(source, /return ['"]http:\/\/localhost:8000['"]/)
  }

  assert.match(requestSource, /fetch\(`\$\{API_BASE\}\$\{API_PREFIX\}/)
  assert.match(guardianSource, /fetch\(`\$\{API_BASE\}\$\{API_PREFIX\}/)
})
