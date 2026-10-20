import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/pages/teacher/approval/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/^import .*$/gm, '').replace('export default', 'return')

test('approval return uses normal history with a teacher-home fallback', () => {
  const calls = []
  const page = new Function('back', script)(url => calls.push(url))
  page.methods.goBack()
  assert.deepEqual(calls, ['/pages/teacher/workbench/index'])
})

test('approval header and both empty/error state boundaries have a return action', () => {
  assert.match(source, /@click="goBack"/)
  const boundaries = source.match(/<MobileGlobalState\b[^>]*>/g)
  assert.equal(boundaries.length, 2)
  for (const boundary of boundaries) assert.match(boundary, /@back="goBack"/)
})
