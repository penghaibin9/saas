import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const here = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(here, '../src/pages/teacher/defense-score/index.vue'), 'utf8')

test('defense score queue only accepts the latest load response', () => {
  assert.match(source, /loadToken:\s*0/)
  assert.match(source, /const token = \+\+this\.loadToken/)
  assert.match(source, /if \(token !== this\.loadToken\) return/)
  assert.match(source, /onUnload\(\) \{ \+\+this\.loadToken \}/)
})

test('defense score refresh drops stale local draft after canonical write or conflict', () => {
  const deletes = source.match(/delete this\.drafts\[d\.gdStudentId\]/g) || []
  assert.equal(deletes.length, 2)
  assert.match(source, /toast\('已保存'\)[\s\S]*delete this\.drafts\[d\.gdStudentId\][\s\S]*this\.load\(\)/)
  assert.match(source, /DATA_CONFLICT[\s\S]*delete this\.drafts\[d\.gdStudentId\][\s\S]*this\.load\(\)/)
})
