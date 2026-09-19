import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('teacher activity workspace closes the full onsite flow with explicit versions', () => {
  const page = read('src/pages/teacher/affairs/activity/index.vue')
  const api = read('src/services/affairsContractApi.js')
  const pages = read('src/pages.json')

  assert.match(pages, /"path": "affairs\/activity\/index"/)
  assert.match(page, /截止报名/)
  assert.match(page, /开始活动/)
  assert.match(page, /生成签到码/)
  assert.match(page, /结束活动/)
  assert.match(page, /确认名单并生成积分/)
  assert.match(page, /this\.selected\.version/)
  assert.match(page, /participantSummary\.checkedIn === 0/)
  assert.match(api, /transitionTeacherActivity:[\s\S]*data: \{ action, version \}/)
  assert.match(api, /confirmTeacherActivity:[\s\S]*data: \{ version \}/)
})

test('teacher activity deep link uses the business activity id', () => {
  const page = read('src/pages/teacher/affairs/activity/index.vue')
  const entry = read('src/pages/teacher/affairs/index.vue')
  assert.match(page, /query\.activityId \|\| query\.recordId/)
  assert.match(entry, /\/pages\/teacher\/affairs\/activity\/index/)
  assert.match(page, /getTeacherActivityParticipants\(selected\.activityId, \{ page, pageSize: 20 \}\)/)
})
