import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..', '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

test('change approval resets the formal relationship to re-onboard in one transaction', () => {
  const source = read('backend/app/modules/internship/services/internship_change_service.py')
  assert.match(source, /record\.intern_start_date = None/)
  assert.match(source, /record\.status = _next_record_status\(record\)/)
  assert.match(source, /_void_prior_compliance\(db, record, change/)
  assert.match(source, /validate_target_position\(/)
  assert.match(source, /requiresReonboard/)
})

test('staff review leads with exact objects and preserves 409 input with a receipt', () => {
  const page = read('frontend/src/modules/internship/views/ChangeRequestListView.vue')
  const api = read('frontend/src/modules/internship/api/internship.api.js')
  assert.ok(page.indexOf('CHANGE NOW') < page.indexOf('mp-tabs'))
  assert.match(page, /ActionReceipt/)
  assert.match(page, /ConflictNotice/)
  assert.match(page, /captureConflict/)
  assert.match(page, /recordExpectedVersion/)
  assert.match(api, /recordExpectedVersion/)
})

test('teacher Mini uses explicit batch and both application and record versions', () => {
  const page = read('miniapp/src/pages/teacher/internship-change/index.vue')
  const api = read('miniapp/src/services/internshipApi.js')
  assert.match(page, /useInternshipContextStore/)
  assert.match(page, /teacherInternshipChanges/)
  assert.match(page, /expectedVersion: c\.version/)
  assert.match(page, /recordExpectedVersion: c\.recordVersionSnapshot/)
  assert.match(page, /initialComment/)
  assert.match(api, /context\/changes/)
})

test('student Mini selects a canonical candidate instead of asking for a raw database id', () => {
  const page = read('miniapp/src/pages/student/internship/change/index.vue')
  assert.doesNotMatch(page, /岗位库 ID|目标岗位编号/)
  assert.match(page, /studentInternshipChangeTargets/)
  assert.match(page, /selectedTarget/)
  assert.match(page, /batchId: this\.context\.batchId/)
  assert.match(page, /internshipId: this\.context\.recordId/)
  assert.match(page, /studentInternshipChangeWithdraw/)
})

test('student candidate facade filters by batch, capacity, company and rights', () => {
  const service = read('backend/app/modules/internship/services/internship_student_change_context_service.py')
  assert.match(service, /InternshipPosition\.batch_id == selected_batch_id/)
  assert.match(service, /InternshipPosition\.allocated_count < InternshipPosition\.headcount/)
  assert.match(service, /EmpCompany\.blacklist\.is_\(False\)/)
  assert.match(service, /evaluate_position_publishability/)
  assert.match(service, /if not rights\["passed"\]/)
})

test('modern student and teacher routes are registered behind the permission gate', () => {
  const student = read('backend/app/api/v1/mobile_internship_student.py')
  const teacher = read('backend/app/api/v1/mobile_internship_context.py')
  const gate = read('backend/app/core/mobile_internship_permission_gate.py')
  assert.match(student, /context\/changes\/target-positions/)
  assert.match(teacher, /@router\.get\("\/changes"/)
  assert.match(teacher, /record_expected_version=payload\.get\("recordExpectedVersion"\)/)
  assert.match(gate, /context\/changes/)
})
