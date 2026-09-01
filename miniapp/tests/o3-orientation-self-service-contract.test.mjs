import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const pages = read('../src/pages.json')
const api = read('../src/services/realApi.js')
const arrival = read('../src/pages/student/orientation/arrival/index.vue')
const materials = read('../src/pages/student/orientation/materials/index.vue')
const credential = read('../src/pages/student/orientation/code/index.vue')
const overview = read('../src/pages/student/orientation/index.vue')
const timeline = read('../src/components/MobileTimeline.vue')
const statusTag = read('../src/components/MobileStatusTag.vue')

test('O3 student miniapp exposes canonical arrival and material submission', () => {
  assert.match(pages, /orientation\/arrival\/index/)
  assert.match(pages, /orientation\/materials\/index/)
  assert.match(api, /\/mobile\/orientation\/arrival'.*method: 'PUT'/)
  assert.match(api, /\/mobile\/orientation\/materials'.*method: 'POST'/)
  assert.match(arrival, /expectedVersion: Number\(this\.form\.expectedVersion \|\| 0\)/)
  assert.match(materials, /bizType: 'ORIENTATION_MATERIAL'/)
  assert.match(materials, /clientSubmissionId: this\.clientSubmissionId/)
  assert.doesNotMatch(materials, /Math\.random/)
})

test('O3 does not disguise the admission number as a report credential', () => {
  assert.match(api, /status: r\.reportCodeStatus \|\| 'BLOCKED'/)
  assert.match(api, /canIssue: !!r\.checkinCredential\?\.canIssue/)
  assert.match(api, /expiresAt: r\.checkinCredential\?\.expiresAt \|\| ''/)
  assert.match(api, /note: r\.checkinCredential\?\.note \|\| '正式电子报到凭证尚未签发'/)
  assert.match(credential, /尚未签发/)
  assert.match(credential, /identity\.admissionNo/)
  assert.doesNotMatch(api, /reportCode:\s*\{\s*code:\s*r\.admissionNo/)
})

test('orientation overview refreshes on return and gives one clear next action', () => {
  assert.match(overview, /onShow\(\) \{ this\.load\(\) \}/)
  assert.match(overview, /下一步/)
  assert.match(overview, /materialsWaitingReview/)
  assert.match(overview, /材料已提交，等待审核/)
  assert.match(arrival, /start="minDate"/)
  assert.match(arrival, /已为你预选今天/)
  assert.match(arrival, /setTimeout\(\(\) => back\(\), 700\)/)
})

test('orientation timeline has student-facing titles and status labels', () => {
  assert.match(api, /ORIENTATION_STEP_LABELS/)
  assert.match(api, /title: ORIENTATION_STEP_LABELS\[s\.key\]/)
  assert.match(statusTag, /DONE: \{ label: '已完成'/)
  assert.match(statusTag, /DOING: \{ label: '办理中'/)
  assert.match(timeline, /'DONE', 'WAIVED', 'NOT_REQUIRED'/)
})
