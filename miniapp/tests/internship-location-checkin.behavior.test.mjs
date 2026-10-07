import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const page = fs.readFileSync(new URL('../src/pages/student-internship/checkin/index.vue', import.meta.url), 'utf8')
const api = fs.readFileSync(new URL('../src/services/realApi.js', import.meta.url), 'utf8')

test('student check-in obtains a server credential before one-shot location submission', () => {
  assert.match(api, /\/mobile\/internship\/checkin\/preflight/)
  assert.match(page, /getCheckinPreflight\(\)/)
  assert.match(page, /checkinToken/)
  assert.match(page, /type: 'gcj02'/)
  assert.doesNotMatch(page, /deviceRiskFlag: 'normal'/)
})

test('student check-in retries poor accuracy and exposes human-review results', () => {
  assert.match(page, /attempts < 3/)
  assert.match(page, /LOW_ACCURACY: '精度不足'/)
  assert.match(page, /LOCATION_UNCERTAIN: '边界待核实'/)
})
