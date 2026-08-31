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
const router = read('../../backend/app/modules/internship/routers/internship.py')

test('W8 report workbench leads with bounded exact objects before metrics', () => {
  assert.match(weeklyList, /priorityRows\(\)\s*\{[\s\S]*?\.slice\(0, 3\)/)
  const nowIndex = weeklyList.indexOf('class="report-now"')
  const kpiIndex = weeklyList.indexOf('<ModuleSummaryStrip')
  assert.ok(nowIndex >= 0 && kpiIndex > nowIndex)
  assert.match(weeklyList, /为什么到这里/)
  assert.match(weeklyList, /最近变化/)
  assert.match(weeklyList, /下一责任人/)
  assert.match(weeklyList, /goDetail\(row\)/)
})

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

test('W8 guidance and visit workbench leads with bounded real collaboration objects', () => {
  assert.match(guidanceVisit, /priorityRows\(\)\s*\{[\s\S]*?\.slice\(0, 3\)/)
  const nowIndex = guidanceVisit.indexOf('class="guidance-now"')
  const kpiIndex = guidanceVisit.indexOf('<ModuleSummaryStrip')
  assert.ok(nowIndex >= 0 && kpiIndex > nowIndex)
  assert.match(guidanceVisit, /为什么到这里/)
  assert.match(guidanceVisit, /最近事实/)
  assert.match(guidanceVisit, /下一责任人/)
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
