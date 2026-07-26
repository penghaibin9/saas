import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

// 本文件位于 frontend/tests；仓库根目录需向上两级。
const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

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

test('student portal request serializes pagination query parameters', () => {
  const request = read('student-portal/src/services/request.js')
  const affairs = read('student-portal/src/services/affairsFourEndApi.js')
  assert.match(request, /function withQuery\(path, params\)/)
  assert.match(request, /params \|\| query/)
  assert.match(affairs, /myCreditAppeals: \(page = 1, pageSize = 100\)/)
})

test('both student clients reject empty or non-positive credit claims', () => {
  const mini = read('miniapp/src/services/affairsAppealApi.js')
  const portal = read('student-portal/src/services/affairsFourEndApi.js')
  for (const source of [mini, portal]) {
    assert.match(source, /Number\.isFinite\(value\)/)
    assert.match(source, /value <= 0/)
    assert.match(source, /最多保留2位小数/)
  }
})
