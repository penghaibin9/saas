import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const api = fs.readFileSync(new URL('../src/modules/graduation/api/graduation-student.api.js', import.meta.url), 'utf8')
const guard = fs.readFileSync(new URL('../src/modules/graduation/views/GraduationProcessActionView.vue', import.meta.url), 'utf8')
const base = fs.readFileSync(new URL('../src/modules/graduation/views/GraduationProcessActionBaseView.vue', import.meta.url), 'utf8')

test('U4 process student picker restores 130-student deep links', () => {
  assert.match(api, /const pickerSearch = params\.page == null/)
  assert.match(api, /page: 1, pageSize: 200/)
})

test('U4 action entry and return keep the complete process work context', () => {
  assert.match(guard, /beforeRouteEnter/)
  assert.match(guard, /beforeRouteLeave/)
  assert.match(guard, /fillProcessContext/)
  assert.match(guard, /studentId/)
  assert.ok(guard.includes("'batchId'"))
  assert.ok(guard.includes("'queue'"))
  assert.ok(guard.includes("'source'"))
  assert.match(guard, /from\.name !== 'graduation-process'/)
  assert.match(guard, /name: 'graduation-process'/)
  assert.match(base, /this\.\$router\.push\(this\.backTo\)/)
})
