import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('T6 internship evidence API stays on additive teacher-mobile routes', () => {
  const api = read('src/services/teacherInternshipEvidenceV3Api.js')
  assert.match(api, /\/teacher-mobile\/internship\/visit-targets/)
  assert.match(api, /\/teacher-mobile\/internship\/weekly-reports\/\$\{enc/)
  assert.match(api, /\/teacher-mobile\/internship\/visits\/\$\{enc/)
  assert.doesNotMatch(api, /\/mobile\/teacher\/internship\/visits\/.*POST/)
})

test('巡访表单固定计划与学生版本，定位默认关闭并由教师主动选择', () => {
  const form = read('src/components/teacher/InternshipVisitEvidenceForm.vue')
  assert.match(form, /teacherInternshipEvidenceV3Api\.visitTargets\(t\.batchId, \{ planId: t\.planId, internshipId: t\.internshipId \}\)/)
  assert.match(form, /expectedVersion/)
  assert.match(form, /planId/)
  assert.match(form, /location: null/)
  assert.match(form, /fileIds:/)
  assert.match(form, /expectedPlanVersion: p\.expectedPlanVersion/)
  assert.match(form, /@click="captureLocation"/)
  assert.match(form, /主动获取本次位置/)
  assert.match(form, /location: this\.location \? \{ \.\.\.this\.location \} : null/)
  assert.match(form, /if \(!this\.active/)
})

test('T6/T8 file evidence is uploaded first by shared picker but formal binding remains server owned', () => {
  const form = read('src/components/teacher/InternshipVisitEvidenceForm.vue')
  const picker = read('src/components/MobileAttachmentPicker.vue')
  assert.match(picker, /fileSdk\.upload/)
  assert.match(picker, /readyForBusiness/)
  assert.match(picker, /扫描/)
  assert.match(form, /uploadBusinessFile/)
  assert.match(read('src/services/fileApi.js'), /return fileSdk\.upload\(file, options\)/)
  assert.match(form, /pendingEvidence\?\.readyForBusiness \? \[String\(this\.pendingEvidence\.fileId\)\] : \[\]/)
  assert.doesNotMatch(form, /bindFile|bind_file|\/files\/.*\/bind/)
})

test('T6 internship review uses real reminder, visit evidence and high-risk command then reloads truth', () => {
  const page = read('src/pages/teacher-internship/internship-review/index.vue')
  assert.match(page, /InternshipVisitEvidenceForm/)
  assert.match(page, /teacherInternshipEvidenceV3Api\.remindWeekly/)
  assert.match(page, /teacherInternshipEvidenceV3Api\.createVisit/)
  assert.match(page, /await Promise\.allSettled\(\[this\.load\(\), this\.loadVisits\(\)\]\)/)
  assert.match(page, /handleCheckinV3\(c\.id, action, r\.content\.trim\(\), 'HIGH'\)/)
  assert.match(page, /return this\.load\(\)\.then/)
  assert.doesNotMatch(page, /催交提醒将随消息推送功能开放/)
  assert.doesNotMatch(page, /recordInternshipVisit\(s\.internshipId\)/)
})

test('T6 abnormal risk confirmation keeps exact T5 snapshot version and invalidates it after success', () => {
  const adapter = read('src/services/teacherSequentialV3Api.js')
  assert.match(adapter, /handleCheckin\(id, action, comment, riskLevel = null\)/)
  assert.match(adapter, /action === 'TO_RISK' && riskLevel !== 'HIGH'/)
  assert.match(adapter, /data: \{ action, comment: comment \|\| '', expectedVersion, riskLevel \}/)
  assert.match(adapter, /exceptionVersions\.delete\(key\)/)
  assert.doesNotMatch(adapter, /localStorage|setStorageSync|itemIds|exceptionIds/)
})
