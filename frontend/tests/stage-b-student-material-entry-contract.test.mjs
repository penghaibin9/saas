import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const main = fs.readFileSync(new URL('../src/main.js', import.meta.url), 'utf8')
const page = fs.readFileSync(new URL('../src/modules/internship/views/InternshipStudentMaterialEntryView.vue', import.meta.url), 'utf8')

test('Stage B high-frequency workflow registers a stable per-student material deep link', () => {
  assert.match(main, /path:\s*'\/admin\/internship\/students\/:id\/materials'/)
  assert.match(main, /name:\s*'internship-student-materials'/)
  assert.match(main, /permissionKey:\s*'internship\.archive\.view'/)
})

test('student material entry reads the authoritative material center, not local fake data', () => {
  assert.match(page, /internshipMaterialCenterApi\.detail\(this\.internshipId\)/)
  assert.match(page, /internshipMaterialCenterApi\.sync\(this\.internshipId\)/)
  assert.match(page, /fileSdk\.preview/)
  assert.match(page, /fileSdk\.download/)
  assert.doesNotMatch(page, /mock|fixture|fakeData/i)
})
