import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8')
const weeklyList = read('../src/modules/internship/views/WeeklyReportListView.vue')
const weeklyDetail = read('../src/modules/internship/views/WeeklyReportDetailView.vue')
const processDetail = read('../src/modules/internship/views/ProcessReportDetailView.vue')
const guidanceVisit = read('../src/modules/internship/views/GuidanceVisitView.vue')
const guidanceForm = read('../src/modules/internship/views/GuidanceRecordFormView.vue')
const guidanceApi = read('../src/modules/internship/api/guidance-visit.api.js')
const internshipService = read('../../backend/app/modules/internship/services/internship_service.py')
const guidanceService = read('../../backend/app/modules/internship/services/internship_guidance_service.py')
const visitService = read('../../backend/app/modules/internship/services/internship_visit_service.py')
const visitPlanService = read('../../backend/app/modules/internship/services/internship_visit_plan_service.py')
const processReportService = read('../../backend/app/modules/internship/services/internship_process_report_service.py')
const studentReportContextService = read('../../backend/app/modules/internship/services/internship_student_report_context_service.py')
const router = read('../../backend/app/modules/internship/routers/internship.py')
const studentPortal = read('../../student-portal/src/views/internship/InternshipView.vue')
const mobileInternshipApi = read('../../miniapp/src/services/internshipApi.js')
const mobileWeekly = read('../../miniapp/src/pages/student/weekly-report/index.vue')
const mobileProcess = read('../../miniapp/src/pages/student/internship/process-report/index.vue')

test('W8 resubmitted weekly report shows real before and after bodies on one screen', () => {
  assert.match(weeklyDetail, /resubmitComparison\(\)/)
  assert.match(weeklyDetail, /versions\[versions\.length - 2\]/)
  assert.match(weeklyDetail, /versions\[versions\.length - 1\]/)
  assert.match(weeklyDetail, />BEFORE</)
  assert.match(weeklyDetail, />AFTER</)
  assert.match(weeklyDetail, /上次退回意见/)
  assert.match(internshipService, /def _report_versions\(trail, w: WeeklyReport\)/)
  assert.match(internshipService, /snap = \(t\.detail_json or \{\}\)\.get\("snapshot"\)/)
  assert.match(internshipService, /detail\["snapshot"\] = _report_snapshot\(w\)/)
})

test('W8 report decisions retain server-returned truthful receipts', () => {
  assert.match(weeklyList, /<ActionReceipt :receipt="lastReceipt"/)
  assert.match(weeklyDetail, /<ActionReceipt :receipt="lastReceipt"/)
  assert.match(processDetail, /<ActionReceipt :receipt="lastReceipt"/)
  assert.match(weeklyDetail, /id: res\.data\?\.id[\s\S]*?version: res\.data\?\.version/)
  assert.match(processDetail, /id: res\.data\?\.id[\s\S]*?version: res\.data\?\.version/)
})

test('W8 guidance creation retains the existing receipt path', () => {
  assert.match(guidanceVisit, /<ActionReceipt :receipt="lastReceipt"/)
  assert.match(guidanceForm, /receipt: 'created'/)
  assert.match(guidanceVisit, /this\.\$route\.query\.receipt === 'created'/)
})

test('W8 guidance void and visit rectification carry the version that the user saw', () => {
  assert.match(guidanceVisit, /kind: 'void'[\s\S]*?expectedVersion: d\.version/)
  assert.match(guidanceVisit, /kind: 'rectify'[\s\S]*?expectedVersion: d\.version/)
  assert.match(guidanceVisit, /voidGuidance\(p\.id, \{ reason, expectedVersion: p\.expectedVersion \}\)/)
  assert.match(guidanceVisit, /rectifyVisit\(p\.id,[\s\S]*?expectedVersion: p\.expectedVersion/)
  assert.match(guidanceApi, /voidGuidance\(id, \{ reason, expectedVersion, version \} = \{\}\)/)
  assert.match(guidanceApi, /rectifyVisit\(id, \{ status, note, expectedVersion, version \}\)/)
  assert.match(router, /def void_guidance[\s\S]*?b = body or \{\}[\s\S]*?expected_version=b\.get\("expectedVersion"/)
  assert.match(router, /def visit_rectify[\s\S]*?b = body or \{\}[\s\S]*?expected_version=b\.get\("expectedVersion"/)
})

test('W8 guidance, visit and visit-plan list truth includes version and writes are conditional', () => {
  for (const source of [guidanceService, visitService, visitPlanService]) {
    assert.match(source, /"version": int\([a-z]+\.version or 0\)/)
  }
  assert.match(guidanceService, /def void_guidance[\s\S]*?versioned_update\(/)
  assert.match(guidanceService, /expected_version=current_version/)
  assert.match(visitService, /def rectify_follow[\s\S]*?versioned_update\(/)
  assert.match(visitService, /extra_where=\(InternshipVisit\.rectify_status == current_status,\)/)
})

test('stage 5C student PC can continue returned weekly and process reports in place', () => {
  assert.match(studentPortal, /editWeekly\(item\)/)
  assert.match(studentPortal, /editProcessReport\(item\)/)
  assert.match(studentPortal, /expectedVersion: existing\?\.version \?\? 0/)
  assert.match(studentPortal, /const periodKey = reportType === 'SUMMARY' \? 'FINAL' : reportForm\.periodKey/)
  assert.match(studentPortal, /reportReceipt/)
  assert.match(studentPortal, /processType\.value === 'SUMMARY' \? 300 : 100/)
})

test('stage 5C student mobile uses contextual report contracts and preserves returned versions', () => {
  assert.match(mobileInternshipApi, /context\/weekly-reports/)
  assert.match(mobileInternshipApi, /context\/reports/)
  assert.match(mobileWeekly, /getInternshipWeeklyReports/)
  assert.match(mobileWeekly, /expectedVersion: current\?\.version \?\? 0/)
  assert.match(mobileWeekly, /status === 'RETURNED'/)
  assert.match(mobileProcess, /getInternshipProcessReports/)
  assert.match(mobileProcess, /expectedVersion: current\?\.version \?\? 0/)
  assert.match(mobileProcess, /currentReport\.status === 'RETURNED'/)
  assert.match(mobileProcess, /receipt/)
  assert.match(studentReportContextService, /item\["content"\] = row\.content or ""/)
  assert.match(processReportService, /operator=_op_name\(user\)/)
})
