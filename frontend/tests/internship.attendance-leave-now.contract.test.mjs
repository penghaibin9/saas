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

test('W7 attendance leads with bounded exact objects before metrics', () => {
  assert.match(attendance, /priorityRows\(\)\s*\{[\s\S]*?\.slice\(0, 3\)/)
  assert.match(attendance, /为什么到这里/)
  assert.match(attendance, /判定事实/)
  assert.match(attendance, /下一责任人/)
  const nowIndex = attendance.indexOf('class="att-now"')
  const kpiIndex = attendance.indexOf('<ModuleSummaryStrip')
  assert.ok(nowIndex >= 0 && kpiIndex > nowIndex)
})

test('W7 thin attendance table routes exception decisions to full evidence detail', () => {
  assert.match(attendance, /openExceptionDetail\(row\)/)
  assert.match(attendance, /`\/admin\/internship\/exceptions\/\$\{row\.id\}`/)
  assert.doesNotMatch(attendance, /openHandle\(row, 'REASONABLE'\)/)
  assert.doesNotMatch(attendance, /openHandle\(row, 'ABNORMAL'\)/)
  assert.doesNotMatch(attendance, /openHandle\(row, 'TO_RISK'\)/)
  assert.match(exceptionDetail, /定位精度/)
  assert.match(exceptionDetail, /模拟定位检测/)
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
  assert.match(leave, /priorityRows\(\)\s*\{[\s\S]*?\.slice\(0, 3\)/)
  const nowIndex = leave.indexOf('class="leave-now"')
  const kpiIndex = leave.indexOf('<ModuleSummaryStrip')
  assert.ok(nowIndex >= 0 && kpiIndex > nowIndex)
  assert.match(leave, /markEvidenceViewed\(this\.detail\.data\.id\)/)
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
