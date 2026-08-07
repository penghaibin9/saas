import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS } from '../help/academicAffairsCoreFlowHelpCards.js'
import { HELP_V3_CORE_JOURNEYS } from '../help/helpCenterV3.js'

const here = dirname(fileURLToPath(import.meta.url))
const runtimeSource = readFileSync(resolve(here, '../helpCenterRuntime.js'), 'utf8')

const EXPECTED_NEW_IDS = [
  'aa-v3-program-course',
  'aa-v3-teaching-task',
  'aa-v3-schedule',
  'aa-v3-credit-gpa',
  'aa-v3-makeup-retake',
  'aa-v3-graduation-qualification'
]

const EXPECTED_JOURNEY = [
  'aa-card-status-change',
  'aa-v3-program-course',
  'aa-v3-teaching-task',
  'aa-v3-schedule',
  'aa-card-selection-publish',
  'aa-card-exam-publish',
  'aa-card-grade-review-publish',
  'aa-v3-credit-gpa',
  'aa-v3-makeup-retake',
  'aa-v3-graduation-qualification'
]

function text(card) {
  return JSON.stringify(card)
}

test('V3-01 adds six unique academic self-service cards with the full no-training contract', () => {
  assert.equal(ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS.length, 6)
  assert.deepEqual(ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS.map((card) => card.id), EXPECTED_NEW_IDS)
  assert.equal(new Set(EXPECTED_NEW_IDS).size, EXPECTED_NEW_IDS.length)

  for (const card of ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS) {
    for (const field of [
      'roles',
      'entry',
      'steps',
      'prerequisites',
      'successCriteria',
      'troubleshooting',
      'permissions',
      'nextSteps',
      'contactAdminWhen'
    ]) {
      assert.ok(Array.isArray(card[field]) ? card[field].length > 0 : Boolean(card[field]), `${card.id} missing ${field}`)
    }
  }
})

test('V3-01 academic journey is the ordered ten-node fact chain', () => {
  const academic = HELP_V3_CORE_JOURNEYS.find((journey) => journey.key === 'academic')
  assert.ok(academic)
  assert.equal(academic.title, '教务完整事实链')
  assert.deepEqual(academic.helpIds, EXPECTED_JOURNEY)
})

test('V3-01 cards are published only through the verified-only runtime', () => {
  assert.match(runtimeSource, /ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS/)
  assert.match(runtimeSource, /\.\.\.ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS\.map\(\(item\) => item\.id\)/)
  assert.match(runtimeSource, /replaceOrRegisterCards\(ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS\)/)
  assert.match(runtimeSource, /academic-v3-core-cards/)
})

test('course and program card preserves versioning, two-review and binding truth', () => {
  const card = ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS.find((item) => item.id === 'aa-v3-program-course')
  const body = text(card)
  for (const token of ['COLLEGE_REVIEW', 'ACADEMIC_REVIEW', 'ENABLED', 'PUBLISHED', 'SUPERSEDED', 'creditSum', 'creditGap', 'prevVersionId']) {
    assert.match(body, new RegExp(token))
  }
  assert.match(body, /毕业总学分/)
  assert.match(body, /课程学分合计/)
})

test('teaching-task and schedule cards lock the READY handoff and publish gate', () => {
  const task = text(ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS.find((item) => item.id === 'aa-v3-teaching-task'))
  for (const token of ['PENDING_ASSIGN', 'TEACHER_CONFIRMED', 'COLLEGE_CONFIRMED', 'APPROVED', 'READY', 'teacher_key']) {
    assert.match(task, new RegExp(token))
  }
  assert.match(task, /分配任课教师/)
  assert.match(task, /课表项/)
  assert.match(task, /不能静默/)

  const schedule = text(ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS.find((item) => item.id === 'aa-v3-schedule'))
  for (const token of ['READY', 'DRAFT', 'PRE_PUBLISHED', 'PUBLISHED', '409']) {
    assert.match(schedule, new RegExp(token))
  }
  assert.match(schedule, /教室.*容量|容量.*教室/)
  assert.match(schedule, /周学时/)
  assert.match(schedule, /重新回到 DRAFT/)
})

test('credit and GPA card states the current formula and explicitly refuses fake per-school configurability', () => {
  const body = text(ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS.find((item) => item.id === 'aa-v3-credit-gpa'))
  assert.match(body, /\(成绩-50\)\/10/)
  assert.match(body, /60→1\.0/)
  assert.match(body, /100→5\.0/)
  assert.match(body, /课程绩点×课程学分/)
  assert.match(body, /尚未参数化/)
  assert.match(body, /不能承诺.*每校可自由配置 GPA 算法/)
  assert.match(body, /学校制度要求另一套 GPA 映射.*当前规则中心尚未支持/)
})

test('makeup card requires reviewed formal writeback and does not overwrite the original failed fact', () => {
  const body = text(ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS.find((item) => item.id === 'aa-v3-makeup-retake'))
  for (const token of ['PUBLISHED', 'SCORING', 'REVIEWED', 'FINISHED', 'MAKEUP', 'CAP60']) {
    assert.match(body, new RegExp(token))
  }
  assert.match(body, /正式不及格记录/)
  assert.match(body, /正式成绩/)
  assert.match(body, /不能通过成绩页面直接覆盖|不能用手工改原成绩/)
})

test('graduation qualification card keeps PASS FAIL UNKNOWN and effective-grade evidence semantics', () => {
  const body = text(ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS.find((item) => item.id === 'aa-v3-graduation-qualification'))
  for (const token of ['PASS', 'FAIL', 'UNKNOWN', 'CREDIT', 'COURSE_REQUIRED', 'COURSE_ELECTIVE', 'PRACTICE', 'INTERNSHIP', 'GRADUATION_DESIGN', 'DISCIPLINE']) {
    assert.match(body, new RegExp(token))
  }
  assert.match(body, /UNKNOWN.*不等于 PASS|UNKNOWN 不能直接判通过/)
  assert.match(body, /唯一.*培养方案|唯一解析/)
  assert.match(body, /有效成绩/)
})
