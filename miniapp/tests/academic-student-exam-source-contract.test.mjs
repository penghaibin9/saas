import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(
  new URL('../src/pages/student/academic-affairs/exam.vue', import.meta.url),
  'utf8'
)

test('student exam page renders one canonical published schedule section', () => {
  const headingMatches = page.match(/<text class="section-head__title">我的考试安排<\/text>/g) || []
  assert.equal(headingMatches.length, 1, '我的考试安排 must render exactly once')
  assert.match(page, /studentApi\.getMyExamSchedule\(\)/)
  assert.match(page, /教务发布考场座位后，准考证与考场信息会出现在此/)
  assert.match(page, /考场 \{\{ it\.classroom/)
  assert.match(page, /座位 \{\{ it\.seatNo/)
  assert.match(page, /准考证 \{\{ it\.admissionNo/)
})

test('student ticket action is only exposed for a non-empty published schedule', () => {
  assert.match(
    page,
    /v-if="d\.schedule && d\.schedule\.length"[\s\S]*?@click="printTicket"[\s\S]*?>打印准考证<\/text>/
  )
  assert.match(page, /if \(!\(this\.d && this\.d\.schedule && this\.d\.schedule\.length\)\) return/)
  assert.match(page, /studentApi\.printExamTicket\('个人准考证'\)/)
  assert.match(page, /已留痕并复制准考证摘要/)
})
