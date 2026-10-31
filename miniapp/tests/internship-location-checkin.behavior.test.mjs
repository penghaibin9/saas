import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { checkinCalendarLabel,checkinLocationPolicy } from '../src/services/checkinPresentation.mjs'

const page = fs.readFileSync(new URL('../src/pages/student-internship/checkin/index.vue', import.meta.url), 'utf8')
const api = fs.readFileSync(new URL('../src/services/realApi.js', import.meta.url), 'utf8')

test('student check-in obtains a server credential before one-shot location submission', () => {
  assert.match(api, /\/mobile\/internship\/checkin\/preflight/)
  assert.match(page, /getCheckinPreflight\(this\.timezoneName, this\.i\.batchId\)/)
  assert.match(page, /checkinToken/)
  assert.equal(checkinLocationPolicy(false,false).type,'gcj02')
  assert.equal(checkinLocationPolicy(false,true).type,'wgs84')
  assert.doesNotMatch(page, /deviceRiskFlag: 'normal'/)
})

test('student check-in retries poor accuracy and exposes human-review results', () => {
  assert.match(page, /attempts < 3/)
  assert.equal(checkinCalendarLabel('LOW_ACCURACY'),'精度不足')
  assert.equal(checkinCalendarLabel('LOCATION_UNCERTAIN'),'待核验')
})
