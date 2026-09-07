import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8')
const attendance = read('../src/modules/internship/views/AttendanceView.vue')
const exceptionDetail = read('../src/modules/internship/views/AttendanceExceptionDetailView.vue')
const leave = read('../src/modules/internship/views/LeaveReviewView.vue')
const receipt = read('../src/modules/internship/views/components/ActionReceipt.vue')
const attendanceApi = read('../src/modules/internship/api/attendance.api.js')
const leaveApi = read('../src/modules/internship/api/leave-risk.api.js')
const router = read('../../backend/app/modules/internship/routers/internship.py')
const leaveContext = read('../../backend/app/modules/internship/services/internship_student_leave_context_service.py')
const studentPortal = read('../../student-portal/src/views/internship/InternshipView.vue')
const studentMobile = read('../../miniapp/src/pages/student/internship/leave/index.vue')
const teacherMobile = read('../../miniapp/src/pages/teacher/internship-approval/ApprovalCore.vue')

test('W7 thin attendance table routes exception decisions to full evidence detail', () => {
  assert.match(attendance, /openExceptionDetail\(row\)/)
  assert.match(attendance, /`\/admin\/internship\/exceptions\/\$\{row\.id\}`/)
  assert.doesNotMatch(attendance, /openHandle\(row, 'REASONABLE'\)/)
  assert.doesNotMatch(attendance, /openHandle\(row, 'ABNORMAL'\)/)
  assert.doesNotMatch(attendance, /openHandle\(row, 'TO_RISK'\)/)
  assert.match(exceptionDetail, /定位精度/)
  assert.match(exceptionDetail, /客户端报告模拟定位/)
  assert.match(exceptionDetail, /学生说明/)
  assert.match(exceptionDetail, /expectedVersion: this\.detail\.version/)
})

test('W7 makeup approval requires full request and current-version evidence acknowledgement', () => {
  assert.match(attendance, /getMakeupDetail\(sid\)/)
  assert.match(attendance, /previousReviewComment/)
  assert.match(attendance, /evidenceRequirementLabel/)
  assert.match(attendance, /markMakeupEvidenceViewed\(d\.id\)/)
  assert.match(attendance, /:disabled="!makeupCanApprove"/)
  assert.match(attendanceApi, /\/makeups\/\$\{id\}\/evidence-viewed/)
  assert.match(router, /def makeup_evidence_viewed[\s\S]*?mk\.mark_evidence_viewed\(user, makeup_id\)/)
})

test('W7 leave workbench leads with exact requests and protects evidence plus 409 recovery', () => {
  assert.match(leave, /markEvidenceViewed\(current\.id\)/)
  assert.match(leave, /:disabled="!leaveCanApprove"/)
  assert.match(leave, /isConflict\(res\)/)
  assert.match(leave, /captureConflict\(/)
  assert.match(leaveApi, /\/leaves\/\$\{id\}\/evidence-viewed/)
  assert.match(router, /def leave_evidence_viewed[\s\S]*?lv\.mark_evidence_viewed\(user, leave_id\)/)
})

test('W7 successful critical writes retain a truthful page receipt', () => {
  assert.match(attendance, /lastReceipt = \{/)
  assert.match(exceptionDetail, /lastReceipt = \{/)
  assert.match(leave, /lastReceipt = \{/)
  for (const field of ['receipt.id', 'receipt.statusLabel', 'receipt.version']) {
    assert.match(receipt, new RegExp(field.replace('.', '\\.')))
  }
  assert.doesNotMatch(receipt, /receipt\.auditId/)
  assert.match(receipt, /不伪造 auditId 或服务端时间/)
})

test('W8 leave return closes the student and teacher PC story with versioned risk sync', () => {
  for (const text of ['待审批', '返岗确认', '已批准', '全部台账']) assert.match(leave, new RegExp(text))
  assert.match(leave, /getReturnQueue\(this\.batchStore\.selectedBatchId\)/)
  assert.match(leave, /ackReturn\(this\.pending\.id/)
  assert.match(leaveApi, /\/leaves\/return-queue/)
  assert.match(leaveApi, /\/leaves\/\$\{id\}\/ack-return/)
  assert.match(router, /def leave_return_queue[\s\S]*?list_teacher_overdue/)
  assert.match(router, /def leave_ack_return[\s\S]*?ack_overdue_return/)
  assert.match(leaveContext, /acknowledged_ids[\s\S]*?ACK_OVERDUE_RETURN_VERSIONED/)
  assert.match(leaveContext, /_expected\(payload\.get\("expectedVersion"\), row\.version\)/)
})

test('W8 student leave and mobile approval keep evidence, receipts and inline return notes', () => {
  assert.match(studentPortal, /leaveEvidenceRequired/)
  assert.match(studentPortal, /uploadLeaveEvidence/)
  assert.match(studentPortal, /leaveReceipt/)
  assert.match(studentPortal, /returnDraft/)
  assert.doesNotMatch(studentPortal, /window\.prompt\('请填写销假说明/)
  assert.match(studentMobile, /lv__receipt/)
  assert.match(studentMobile, /submitReturn/)
  assert.match(teacherMobile, /reviewDraft\.kind === 'leave'/)
  assert.match(teacherMobile, /returnDraft\.visible/)
  assert.match(teacherMobile, /核实说明已保留/)
})
