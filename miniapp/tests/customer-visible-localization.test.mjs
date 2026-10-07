import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = (relative) => readFileSync(new URL(`../src/pages/${relative}`, import.meta.url), 'utf8')
const source = (relative) => readFileSync(new URL(`../src/${relative}`, import.meta.url), 'utf8')

test('教师移动端以中文展示业务状态，同时保留核对编号', () => {
  const integrity = page('teacher/platform-integrity/index.vue')
  assert.match(integrity, /exceptionTypeLabel\(item\.exceptionType\)/)
  assert.match(integrity, /integrityStatusLabel\(item\.status\)/)
  assert.match(integrity, /异常编号 \{\{ item\.exceptionType/)
  assert.doesNotMatch(integrity, />\{\{ item\.status \}\} · \{\{ item\.severity \}\}</)

  const affairs = page('teacher/affairs/index.vue')
  assert.match(affairs, /任务项编号 \{\{ detail\.itemKey \}\}/)
  assert.match(affairs, /batchItemStatusLabel\(detail\.status\)/)

  const internship = page('teacher-internship/internship-review/index.vue')
  assert.match(internship, /item\.typeLabel \|\| '打卡异常'/)
  assert.match(internship, /异常编号/)
  assert.doesNotMatch(internship, /异常类型<\/text><text[^>]*>\{\{ (?:item|c)\.type \}\}/)
})

test('教师工作台和学生详情不直接裸露英文状态', () => {
  const workbench = page('teacher/workbench/index.vue')
  assert.match(workbench, /internshipBatchStatus\(selectedInternshipBatch\.status\)/)
  assert.match(workbench, /r\.typeLabel \|\| riskTypeLabel\(r\.type\)/)

  const detail = page('teacher/student-detail/index.vue')
  assert.match(detail, /studentStatusText\(s\.base\.status\)/)
  assert.doesNotMatch(detail, /\{\{ s\.base\.status \|\|/)
})

test('迎新、教务、实习和就业页面用中文标签并保留业务编号', () => {
  const greenChannel = page('teacher/orientation/green-channel/index.vue')
  assert.match(greenChannel, /applyTypeLabel\(a\.applyType\)/)
  assert.match(greenChannel, /statusLabel\(a\.status, a\.statusLabel\)/)

  const schedule = page('teacher/schedule-change/index.vue')
  assert.match(schedule, /conflictTypeLabel\(conflictResult\.type\)/)
  assert.doesNotMatch(schedule, /（\{\{ conflictResult\.type \}\}）/)

  const approval = page('teacher/approval/index.vue')
  assert.match(approval, /approvalTypeLabel\(a\.type\)/)
  assert.match(approval, /#\{\{ a\.taskId \}\}/)

  const risk = page('teacher-internship/internship-risk/index.vue')
  assert.match(risk, /riskStatusLabel\(r\.status, r\.statusLabel\)/)
  assert.match(risk, /`\$\{label\} #\$\{r\.sourceId\}`/)
  assert.doesNotMatch(risk, /审计 outbox/)

  const employment = page('student/employment/index.vue')
  assert.match(employment, /materialTypeText\(m\.type, m\.typeLabel\)/)
  assert.match(employment, /followWayText\(f\.way\)/)

  const profile = page('student/profile/index.vue')
  assert.match(profile, /enrollStatusLabel\(p\.status\.enrollStatus\)/)

  const evaluation = page('teacher/evaluation/index.vue')
  assert.match(evaluation, /batchStatusLabel\(t\.batchStatus\)/)
})

test('补考重修页面和错误展示层不向学生透出内部英文状态或原因码', () => {
  const makeup = page('student/academic-affairs/makeup.vue')
  const request = source('services/request.js')
  assert.match(makeup, /retakeStatusLabel\(r\.status\)/)
  assert.match(makeup, /exemptionStatusLabel\(e\.status, e\.currentNode\)/)
  assert.match(makeup, /已编入教学班/)
  assert.match(makeup, /任课教师审核中/)
  assert.match(makeup, /已退回，待补充材料/)
  assert.match(request, /INTERNAL_ERROR_CODE_PREFIX/)
})
