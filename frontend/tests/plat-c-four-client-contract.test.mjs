import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const read = path => readFileSync(resolve(repo, path), 'utf8')

test('PLAT-C private clients consume one source-authorized server contract', () => {
  const staffApi = read('frontend/src/modules/platform/documentLifecycle/api/document-lifecycle.api.js')
  const studentApi = read('student-portal/src/services/documentLifecycleApi.js')
  const miniApi = read('miniapp/src/services/documentLifecycleApi.js')
  for (const source of [staffApi, studentApi, miniApi]) {
    assert.match(source, /platform-c\/students/)
    assert.match(source, /document-intelligence/)
    assert.doesNotMatch(source, /mock|fallback|presigned|storageUrl/i)
  }
  assert.match(staffApi, /leftExpectedSha256/)
  assert.match(staffApi, /rightExpectedSha256/)
  assert.match(studentApi, /leftExpectedSha256/)
  assert.match(miniApi, /leftExpectedSha256/)
})

test('teacher and student miniapp surfaces are distinct and summary-only', () => {
  const teacher = read('miniapp/src/components/documentLifecycle/TeacherLifecycleTimeline.vue')
  const student = read('miniapp/src/components/documentLifecycle/StudentLifecycleMilestones.vue')
  const summary = read('miniapp/src/components/documentLifecycle/LifecycleSummary.vue')
  assert.match(teacher, /mode="teacher"/)
  assert.match(student, /mode="student"/)
  assert.match(summary, /复杂比较请前往管理端/)
  assert.doesNotMatch(summary, /changes|generatedFileObjectId|download/i)
})

test('Student360 keeps direct-domain sections while C7 registers timeline shadow parity', () => {
  const projection = read('backend/app/services/teacher_mobile_student360_projection_service.py')
  assert.match(projection, /"sections"/)
  assert.match(projection, /shadow_fact_timeline/)
  assert.match(projection, /"timelineShadow"/)
  assert.match(projection, /for event in events/)
  assert.doesNotMatch(projection, /"timeline":\s*timeline_shadow/)
})
