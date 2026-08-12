import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const apiUrl = new URL('../src/modules/academicAffairs/api/roster-registration-convenience.api.js', import.meta.url)
const panelUrl = new URL('../src/modules/academicAffairs/components/AaRegistrationBulkPanel.vue', import.meta.url)
const detailUrl = new URL('../src/modules/academicAffairs/views/AaRegistrationDetailView.vue', import.meta.url)

async function source(url) {
  return readFile(url, 'utf8')
}

test('D2-U PC helper exposes candidate → preview → canonical confirm endpoints', async () => {
  const api = await source(apiUrl)
  assert.match(api, /registration-candidates`/)
  assert.match(api, /bulk-register-preview`/)
  assert.match(api, /bulk-register`/)
  assert.match(api, /previewBulkRegistration/)
  assert.match(api, /confirmBulkRegistration/)
  assert.match(api, /studentIds: \(studentIds \|\| \[\]\)\.map\(Number\)/)
})

test('D2-U registration detail replaces immediate single-student submit with batch panel', async () => {
  const detail = await source(detailUrl)
  assert.match(detail, /AaRegistrationBulkPanel/)
  assert.match(detail, /:batch-id="batchId"/)
  assert.match(detail, /@applied="load"/)
  assert.doesNotMatch(detail, /AppStudentPicker/)
  assert.doesNotMatch(detail, /registerStudent\(/)
  assert.doesNotMatch(detail, /逐个注册/)
})

test('D2-U batch panel is human-readable and enforces preview before confirm', async () => {
  const panel = await source(panelUrl)
  for (const field of ['studentNo', 'realName', 'className', 'majorName', 'currentStatusLabel', 'eligibilityExplanation']) {
    assert.match(panel, new RegExp(`row\\.${field}`), `${field} must be visible in the batch workspace`)
  }
  assert.doesNotMatch(panel, /row\.classId/)
  assert.doesNotMatch(panel, /row\.majorId/)
  assert.match(panel, /预览不会写库/)
  assert.match(panel, /makePreview/)
  assert.match(panel, /reviewed/)
  assert.match(panel, /confirmBulkRegistration/)
  assert.match(panel, /单次最多 100 人/)
  assert.match(panel, /系统没有把部分失败伪装成整批成功/)
})
