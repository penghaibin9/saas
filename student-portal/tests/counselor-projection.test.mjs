import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const profile = fs.readFileSync(new URL('../src/views/profile/ProfileView.vue', import.meta.url), 'utf8')

test('学生 PC 档案显示班级权威主辅导员', () => {
  assert.match(profile, /辅导员 \{\{ info\.counselorName \|\| '待分配' \}\}/)
  assert.match(profile, /label: '责任辅导员'/)
})
