import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const apiUrl = new URL('../src/modules/academicAffairs/api/roster-registration-convenience.api.js', import.meta.url)
const legacyApiUrl = new URL('../src/modules/academicAffairs/api/academic-affairs.api.js', import.meta.url)
const panelUrl = new URL('../src/modules/academicAffairs/components/AaRegistrationBulkPanel.vue', import.meta.url)
const detailUrl = new URL('../src/modules/academicAffairs/views/AaRegistrationDetailView.vue', import.meta.url)
const workbenchUrl = new URL('../src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue', import.meta.url)

async function source(url) {
  return readFile(url, 'utf8')
}

test('D2-U PC helper exposes candidate → preview → token-bound confirm while legacy single API remains', async () => {
  const [api, legacyApi] = await Promise.all([source(apiUrl), source(legacyApiUrl)])
  assert.match(api, /registration-candidates`/)
  assert.match(api, /bulk-register-preview`/)
  assert.match(api, /bulk-register`/)
  assert.match(api, /previewBulkRegistration/)
  assert.match(api, /result\.data\?\.previewToken/)
  assert.match(api, /confirmBulkRegistration\(batchId\)/)
  assert.match(api, /body: \{ previewToken \}/)
  assert.match(api, /请先重新预览本次批量注册名单/)

  // 老的单笔 API 是兼容合同，D2-U 不能删除或偷偷改 URL。
  assert.match(legacyApi, /registerStudent\(batchId, studentId\)/)
  assert.match(legacyApi, /\/registration-batches\/\$\{batchId\}\/register/)
  assert.match(legacyApi, /body: \{ studentId \}/)
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

test('D2-U batch panel is human-readable and has an explicit preview review gate', async () => {
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

test('D2-U eligibility table displays readable class name instead of raw class id', async () => {
  const workbench = await source(workbenchUrl)
  assert.match(workbench, /\{ key: 'className', title: '班级' \}/)
  assert.doesNotMatch(workbench, /title: '班级ID'/)
  assert.doesNotMatch(workbench, /\{ key: 'classId', title:/)
})
