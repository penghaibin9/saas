import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

test('student profile opens only its own canonical material workspace', () => {
  const profile = read('miniapp/src/pages/student/profile/index.vue')
  const materials = read('miniapp/src/pages/student/affairs/index.vue')
  assert.match(profile, /bizType=PROFILE&bizId=/)
  assert.match(materials, /\['PROFILE', 'LEAVE', 'AID', 'FUNDING'\]/)
  assert.match(materials, /this\.go\('\/pages\/student\/profile\/index'\)/)
  assert.match(materials, /仅显示\{\{ bizLabel\(materialReturnContext\.bizType\) \}\}材料/)
  assert.match(materials, /返回学生档案/)
})

test('teacher material queue understands profile records and returns to student detail', () => {
  const materials = read('miniapp/src/pages/teacher/affairs/index.vue')
  assert.match(materials, /PROFILE: '学生个人档案'/)
  assert.match(materials, /\/pages\/teacher\/student-detail\/index\?id=/)
  assert.match(materials, /\['PROFILE', 'LEAVE', 'AID', 'FUNDING'\]/)
  assert.match(materials, /核对业务材料与当前版本/)
  assert.match(materials, /仅显示\{\{ bizLabel\(materialReturnContext\.bizType\) \}\}材料/)
})
