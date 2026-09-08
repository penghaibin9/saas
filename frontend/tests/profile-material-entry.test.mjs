import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

test('teacher PC opens the material center with the exact student profile context', () => {
  const detail = read('frontend/src/views/admin/student/StudentDetailView.vue')
  const center = read('frontend/src/modules/studentAffairs/views/MaterialOperationsView.vue')
  assert.match(detail, /登记档案缺项/)
  assert.match(detail, /bizType:\s*'PROFILE'/)
  assert.match(detail, /bizId:\s*action\.bizType === 'PROFILE'/)
  assert.match(center, /\['PROFILE', 'AID', 'LEAVE', 'FUNDING'\]/)
  assert.match(center, /intent \|\| ''\).*=== 'create'/)
  assert.match(center, /`\/admin\/student\/\$\{context\.bizId\}`/)
})

test('student PC profile links to its scoped profile material list', () => {
  const profile = read('student-portal/src/views/profile/ProfileView.vue')
  const materials = read('student-portal/src/views/affairs/MaterialSupplementView.vue')
  assert.match(profile, /bizType: 'PROFILE'/)
  assert.match(profile, /bizId: info\.studentId/)
  assert.match(materials, /\['PROFILE', 'LEAVE', 'AID', 'FUNDING'\]/)
  assert.match(materials, /router\.push\(\{ name: 'profile' \}\)/)
})

