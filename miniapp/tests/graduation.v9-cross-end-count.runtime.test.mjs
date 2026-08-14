import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const page = fs.readFileSync(new URL('../src/pages/teacher/graduation-guide/index.vue', import.meta.url), 'utf8')
const helper = fs.readFileSync(new URL('../src/services/graduationTeacherCountTruth.js', import.meta.url), 'utf8')

test('U12 count refresh stays server-driven after every proposal/final action', () => {
  assert.match(helper, /proposalTotal:\s*Number\(d\.proposalTotal \|\| 0\)/)
  assert.match(helper, /finalTotal:\s*Number\(d\.finalTotal \|\| 0\)/)
  assert.match(page, /afterAction\(\)[\s\S]*?graduationTeacherCountTruth\(\)[\s\S]*?this\.applyReviewTruth\(d\)/)
  assert.match(page, /pendingReviewCount\(\) \{ return this\.proposalTotal \+ this\.finalTotal \}/)
})
