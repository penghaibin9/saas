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

test('T6 visit form carries exact plan and record version and never captures teacher location', () => {
  const form = read('src/components/teacher/InternshipVisitEvidenceForm.vue')
  assert.match(form, /teacherInternshipEvidenceV3Api\.visitTargets\(\)/)
  assert.match(form, /expectedVersion/)
  assert.match(form, /planId/)
  assert.match(form, /location: null/)
  assert.match(form, /fileIds:/)
  assert.match(form, /fileSdk\.choose/)
  assert.match(form, /fileSdk\.upload/)
  assert.match(form, /readyForBusiness/)
  assert.match(form, /TEMP_PRIVATE/)
  assert.doesNotMatch(form, /uni\.getLocation|getLocation\(|chooseLocation\(|latitude|longitude|captureLocation/)
})

test('T6 file evidence is uploaded first but formal binding remains server owned', () => {
  const form = read('src/components/teacher/InternshipVisitEvidenceForm.vue')
  assert.match(form, /fileSdk\.metadata/)
  assert.match(form, /等待安全扫描|安全扫描/)
  assert.match(form, /保存巡访时由后端业务事务正式绑定/)
  assert.doesNotMatch(form, /bindFile|bind_file|\/files\/.*\/bind/)
})

test('T6 internship review uses real reminder, visit evidence and high-risk command then reloads truth', () => {
  const page = read('src/pages/teacher/internship-review/index.vue')
  assert.match(page, /InternshipVisitEvidenceForm/)
  assert.match(page, /teacherInternshipEvidenceV3Api\.remindWeekly/)
  assert.match(page, /teacherInternshipEvidenceV3Api\.createVisit/)
  assert.match(page, /return this\.loadVisits\(\)/)
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
