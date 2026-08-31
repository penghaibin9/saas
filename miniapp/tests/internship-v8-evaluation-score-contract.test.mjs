import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const teacherScore = read('src/pages/teacher/internship-score/index.vue')
const selfEval = read('src/pages/student/internship/self-eval/index.vue')

test('Teacher Mini triggers authoritative compute without forging component scores', () => {
  assert.match(teacherScore, /sourceReadiness\?\.enterpriseEvaluation/)
  assert.match(teacherScore, /sourceReadiness\?\.studentSelfEvaluation/)
  assert.match(teacherScore, /sourceReadiness\?\.advisorEvaluation/)
  assert.match(teacherScore, /PENDING_PUBLISH/)
  assert.match(teacherScore, /existing\.version/)
  assert.match(teacherScore, /receipt/)
  assert.doesNotMatch(teacherScore, /body\.(checkinScore|weeklyScore|monthlyScore|enterpriseScore|schoolScore)/)
  assert.doesNotMatch(teacherScore, /SCORE_FIELDS/)
})

test('Student Mini preserves self-evaluation draft on 409 and never auto-replays', () => {
  assert.match(selfEval, /enterpriseRating/)
  assert.match(selfEval, /positionRating/)
  assert.match(selfEval, /expectedVersion: this\.evalData\.version/)
  assert.match(selfEval, /草稿已保留/)
  assert.match(selfEval, /系统不会自动重放/)
  assert.match(selfEval, /receipt/)
  const conflict = selfEval.indexOf("if (String(e?.code || '').includes('409')")
  assert.ok(conflict >= 0)
  assert.equal(selfEval.slice(conflict, conflict + 500).includes('this.load()'), false)
})
