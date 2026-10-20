import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/internship/InternshipView.vue', import.meta.url), 'utf8')

test('Student PC completes self, enterprise and position evaluation in one work object', () => {
  assert.match(source, /evalForm\.enterpriseRating/)
  assert.match(source, /evalForm\.positionRating/)
  assert.match(source, /enterpriseFeedback/)
  assert.match(source, /positionFeedback/)
  assert.match(source, /expectedVersion: selfEvalMeta\.value\?\.version/)
  assert.match(source, /evalReceipt/)
})

test('Student PC appeal receipt freezes exact score id and version', () => {
  assert.match(source, /evalReceipt\.value = \{ actionLabel: '成绩申诉已提交'/)
  assert.match(source, /result\?\.scoreId/)
  assert.match(source, /result\?\.scoreVersion/)
  assert.match(source, /学校处理时将校验成绩/)
})
