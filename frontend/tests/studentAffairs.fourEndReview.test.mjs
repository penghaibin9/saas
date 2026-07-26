import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('teacher miniapp approves the version visible in the list', () => {
  const source = read('miniapp/src/pages/teacher/affairs-review/index.vue')
  assert.match(source, /visibleVersion\(row, detail\)/)
  assert.match(source, /const visible = this\.versionOf\(row\)/)
  assert.match(source, /记录已被他人修改，请刷新后重新查看并确认/)
  assert.doesNotMatch(source, /version:\s*detail\.version/)
})

test('PC dorm checkout sends the visible bed version', () => {
  const api = read('frontend/src/modules/studentAffairs/api/dormReliability.api.js')
  const page = read('frontend/src/modules/studentAffairs/views/dorm/DormCheckinView.vue')
  assert.match(api, /body:\s*\{\s*version\s*\}/)
  assert.match(page, /version:\s*bd\.version/)
  assert.match(page, /dormReliabilityApi\.checkout\(this\.outDlg\.bedId, this\.outDlg\.version\)/)
})

test('student activity checkin never exposes manual checkin action', () => {
  const source = read('miniapp/src/pages/student/affairs/activity.vue')
  assert.match(source, /输入签到码/)
  assert.match(source, /secureActivityCheckin/)
  assert.doesNotMatch(source, /method:\s*['"]MANUAL['"]/)
})

test('student returned applications preserve version through edit and resubmit', () => {
  const aid = read('miniapp/src/pages/student/affairs/aid.vue')
  const funding = read('miniapp/src/pages/student/affairs/funding.vue')
  assert.match(aid, /version/)
  assert.match(funding, /version/)
  assert.match(aid, /resubmit/)
  assert.match(funding, /resubmit/)
})
