import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const api = fs.readFileSync(new URL('../src/modules/student/api/student.api.js', import.meta.url), 'utf8')

test('student center reads school display vocabulary and keeps a local fallback', () => {
  assert.match(api, /request\('\/school\/dictionaries\/effective',\s*\{ params: \{ consumer: 'studentCenter' \} \}\)\.catch\(\(\) => null\)/)
  assert.match(api, /statusOptions:\s*\{ \.\.\.STATUS_OPTIONS, \.\.\.\(dictionaryResult\?\.statusOptions \|\| \{\}\) \}/)
})

test('dictionary failure cannot block the student center permission context', () => {
  assert.match(api, /dictionaryResult\]\s*=\s*await Promise\.all/)
  assert.match(api, /request\('\/rbac\/current-context'\)/)
})
