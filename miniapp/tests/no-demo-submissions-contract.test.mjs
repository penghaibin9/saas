import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

test('formal student service application never creates a local fake record after a write', () => {
  const page = fs.readFileSync(new URL('../src/pages/student/service-apply/index.vue', import.meta.url), 'utf8')
  assert.match(page, /studentApi\.submitServiceApply\(/)
  assert.match(page, /\.then\(\(result\) => \{/)
  assert.doesNotMatch(page, /useSubmissionsStore|localAdd\(/)
  assert.equal(fs.existsSync(new URL('../src/stores/submissions.js', import.meta.url)), false)
})
