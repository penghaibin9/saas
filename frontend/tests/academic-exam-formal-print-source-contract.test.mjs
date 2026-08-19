import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const view = readFileSync(
  new URL('../src/modules/academicAffairs/views/AaExamSeatingPrintView.vue', import.meta.url),
  'utf8'
)
const api = readFileSync(
  new URL('../src/modules/academicAffairs/api/academic-exam-formal-print.api.js', import.meta.url),
  'utf8'
)

test('official exam print page never falls back to arrangement room seats', () => {
  assert.match(api, /\/formal-print/)
  assert.doesNotMatch(api, /\/seats[`'"?]/)

  assert.match(view, /formalRoomPrint\(id\)/)
  assert.match(view, /documentStatus !== 'OFFICIAL'/)
  assert.match(view, /printIdentity/)
  assert.match(view, /publishedAt/)
  assert.match(view, /rosterIdentity|正式打印证据/)
  assert.match(view, /data\.seats/)
  assert.doesNotMatch(view, /roomSeats\(/)
  assert.doesNotMatch(view, /attendanceStatus/)
})

test('print button is impossible without official document evidence', () => {
  assert.match(view, /document\?\.documentStatus === 'OFFICIAL'/)
  assert.match(view, /v-if="canPrint"/)
  assert.match(view, /if \(!this\.canPrint\)/)
  assert.match(view, /缺少正式打印证据，禁止打印/)
})
