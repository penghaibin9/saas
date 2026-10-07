import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

const source = fs.readFileSync(new URL('../src/pages/student/campus-service/mental-survey/index.vue', import.meta.url), 'utf8').replaceAll('\r', '')
const teacherPage = fs.readFileSync(new URL('../src/pages/teacher/affairs/mental/index.vue', import.meta.url), 'utf8').replaceAll('\r', '')
const contract = fs.readFileSync(new URL('../src/services/affairsContractApi.js', import.meta.url), 'utf8').replaceAll('\r', '')
const legacyApi = fs.readFileSync(new URL('../src/services/realApi.js', import.meta.url), 'utf8').replaceAll('\r', '')

test('student mobile self-survey uses one focused sheet instead of one card per question', () => {
  assert.match(source, /class="ms__sheet"/)
  assert.match(source, /class="ms__question" v-for=/)
  assert.doesNotMatch(source, /class="card stack-sm" v-for=/)
})

test('student mobile exposes contact intent and only safe history fields', () => {
  assert.match(source, /wantsContact = !wantsContact/)
  assert.match(source, /submitPsySurvey\(answers, this\.wantsContact\)/)
  assert.match(source, /h\.wantsContact/)
  assert.match(source, /h\.triggeredAttention/)
  assert.doesNotMatch(source, /h\.answers|reasonSummary|counselorNote/)
})

test('teacher mobile mental actions carry the server version through every client path', () => {
  assert.match(teacherPage, /affairsContractApi\.followMental\(this\.active\.referralId, content, version\)/)
  assert.match(teacherPage, /affairsContractApi\.escalateMental\(this\.active\.referralId, content, version\)/)
  assert.match(teacherPage, /affairsContractApi\.closeMental\(this\.active\.referralId, content, version\)/)
  assert.match(contract, /data: \{ content, version \}/)
  assert.match(legacyApi, /teacherMentalFollow = \(refId, content, version\)/)
  assert.match(legacyApi, /data: \{ conclusion, version \}/)
})
