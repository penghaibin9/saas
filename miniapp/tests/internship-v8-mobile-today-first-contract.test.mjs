import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const student = read('src/pages/student-internship/index.vue')
const teacher = read('src/pages/teacher/workbench/index.vue')
const review = read('src/pages/teacher-internship/internship-review/index.vue')
const adapter = read('src/services/teacherSequentialV3Api.js')
const backend = read('../backend/app/modules/internship/services/internship_service.py')

test('V8 Student Mini keeps currentTask first and groups all seventeen routes by live stage', () => {
  const navBlock = student.match(/navItems:\s*\[([\s\S]*?)\n\s*]/)?.[1] || ''
  const paths = [...navBlock.matchAll(/path: '([^']+)'/g)].map((match) => match[1])

  assert.equal(paths.length, 17)
  assert.equal(new Set(paths).size, 17)
  assert.ok(student.indexOf('compliance.currentTask') < student.indexOf('serviceGroups'))
  assert.match(student, /label: '当前必须做'/)
  assert.match(student, /label: this\.canShowDailyWork \? '今天' : '需要帮助'/)
  assert.match(student, /label: '当前阶段服务'/)
  assert.match(student, /label: '更多服务'/)
  assert.match(student, /currentStage\(\)/)
  assert.match(student, /this\.i\?\.statusText === 'ONBOARD'/)
  assert.match(student, /openSub\(n\.path\)/)
})

test('V8 Student Mini honors an exact numeric batch deep link before loading server truth', () => {
  assert.match(student, /onLoad\(options = \{\}\)/)
  assert.match(student, /requestedBatchId = String\(options\.batchId \|\| ''\)\.trim\(\)/)
  assert.match(student, /if \(\/\^\\d\+\$\/\.test\(requestedBatchId\)\)/)
  assert.ok(student.indexOf('this.selectedBatchId = requestedBatchId') < student.indexOf('this.load()'))
  assert.match(student, /this\.persistBatch\(\)/)
})

test('V8 Teacher Mini puts concrete tasks and risks before common services, retaining the full queue', () => {
  const todayObjects = teacher.indexOf('待我处理')
  const riskObjects = teacher.indexOf('需要关注')
  const compatibility = teacher.indexOf('<MobileTeacherCommonServices')
  assert.ok(todayObjects >= 0)
  assert.ok(riskObjects > todayObjects)
  assert.ok(compatibility > riskObjects)
  assert.match(teacher, /v-for="\(t,index\) in priorityTodos"/)
  assert.match(teacher, /go\('\/pages\/teacher\/todos\/index'\)/)
  assert.match(teacher, /v-for="r in wb\.riskStudents"/)
  assert.match(teacher, /:services="commonServices"/)
  assert.match(read('src/components/MobileTeacherCommonServices.vue'), /go\('\/pages\/teacher\/services\/index'\)/)
})

test('V8 Teacher Mini exception decision facts match PC truth and fail closed', () => {
  for (const field of ['positionName', 'accuracy', 'address', 'deviceRisk', 'streak', 'appealStatus', 'decisionFactsComplete', 'missingDecisionFacts']) {
    assert.match(backend, new RegExp(`"${field}"`))
    assert.match(adapter, new RegExp(field))
  }
  for (const label of ['异常时间', '距离信息', '定位精度', '打卡地址', '设备风险', '学生说明', '学生申诉']) {
    assert.match(review, new RegExp(label))
  }
  assert.match(adapter, /decisionFactsComplete: e\.decisionFactsComplete === true/)
  assert.match(review, /!canDecideException\(item\)/)
  assert.match(review, /!canDecideException\(c\)/)
  assert.match(review, /if \(!this\.canDecideException\(c\)\)/)
  assert.match(review, /改在 PC 端核对完整证据/)
})
