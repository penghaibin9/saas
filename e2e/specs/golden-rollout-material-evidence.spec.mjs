import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const VIEWPORT = { width: 1440, height: 1000 }
const graduationMaterialStudent = { tenant: 'sandbox-school', username: 'E2E20260003', password: 'E2eTest@2026' }

function runId() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  return String(raw).replace(/\D/g, '').slice(-12) || String(Date.now()).slice(-12)
}

function isoDay(offset) {
  const date = new Date()
  date.setUTCHours(0, 0, 0, 0)
  date.setUTCDate(date.getUTCDate() + offset)
  return date.toISOString().slice(0, 10)
}

function academicYear() {
  const year = new Date().getUTCFullYear()
  return `${year}-${year + 1}`
}

async function dismissGuide(page) {
  for (const mask of [page.locator('.app-step-guide__mask'), page.locator('.tour-mask')]) {
    if (await mask.isVisible().catch(() => false)) {
      const skip = page.getByRole('button', { name: /跳过引导|跳过/ }).first()
      if (await skip.isVisible().catch(() => false)) await skip.click()
      await mask.waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {})
    }
  }
}

async function settleVisual(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
}

async function capture(page, testInfo, name) {
  await dismissGuide(page)
  await settleVisual(page)
  const viewportPath = testInfo.outputPath(`${name}-1440x1000.png`)
  const fullPath = testInfo.outputPath(`${name}-full.png`)
  await page.screenshot({ path: viewportPath, fullPage: false, animations: 'disabled', caret: 'hide' })
  await page.screenshot({ path: fullPath, fullPage: true, animations: 'disabled', caret: 'hide' })
  await testInfo.attach(`${name}-viewport`, { path: viewportPath, contentType: 'image/png' })
  await testInfo.attach(`${name}-full`, { path: fullPath, contentType: 'image/png' })
}

async function setBatchStorage(page, key, value) {
  await page.evaluate(({ storageKey, storageValue }) => {
    window.localStorage.setItem(storageKey, String(storageValue))
  }, { storageKey: key, storageValue: value })
}

async function findStudent(api, studentNo) {
  const profiles = items(await api.get('/students', { keyword: studentNo, page: 1, pageSize: 50 }))
  const profile = profiles.find((item) => String(item.studentNo || item.loginName || '') === studentNo)
  if (!profile) throw new Error(`Golden material student ${studentNo} not found`)
  return profile
}

async function prepareStudentAffairsArchiveFixture() {
  const admin = await loginApi(config.sandboxAdmin)
  const marker = runId()
  const student = await findStudent(admin, graduationMaterialStudent.username)
  const created = await admin.post('/student-affairs/archive/batches', {
    batchName: `Golden 学工归档 ${marker}`,
    yearCode: academicYear(),
    scope: { source: 'GOLDEN_MATERIAL_SCREENSHOT', studentNo: graduationMaterialStudent.username }
  })
  const batchId = String(created.id || created.batchId || '')
  if (!batchId) throw new Error('Golden Student Affairs archive batch has no id')
  const detail = await admin.get(`/student-affairs/archive/batches/${batchId}`)
  const collected = await admin.post(`/student-affairs/archive/batches/${batchId}/collect`, {
    studentIds: [String(student.id || student.studentId)],
    version: Number(detail.version ?? created.version ?? 0)
  })
  return {
    batchId,
    batchName: created.batchName || `Golden 学工归档 ${marker}`,
    status: collected.status || 'COLLECTING',
    studentNo: graduationMaterialStudent.username
  }
}

async function prepareInternshipMaterialFixture() {
  const fixture = await loadInternshipFixture()
  const admin = await loginApi(config.sandboxAdmin)
  const synced = await admin.post(`/internship/material-center/${fixture.internshipId}/sync`, {})
  return { ...fixture, syncedCount: (synced.items || []).length, unsafeCount: (synced.unsafe || []).length }
}

async function prepareGraduationMaterialFixture() {
  const admin = await loginApi(config.sandboxAdmin)
  const marker = runId()
  const batchNo = `PW-GOLD-MAT-${marker}`
  const year = new Date().getUTCFullYear()
  let batch = items(await admin.get('/graduation/batches', { keyword: batchNo, page: 1, pageSize: 50 }))
    .find((item) => item.batchNo === batchNo)

  if (!batch) {
    batch = await admin.post('/graduation/batches', {
      batchName: `Golden 毕设材料中心 ${marker}`,
      batchNo,
      academicYear: academicYear(),
      gradeYear: `${year + 1}届`,
      plannedCount: 1,
      remark: 'Golden material-center screenshot only; isolated E2E database'
    })
  }

  if (String(batch.status || '').toUpperCase() !== 'RUNNING') {
    await admin.post(`/graduation/batches/${batch.id}/rules`, {
      rules: {
        score: { advisorWeight: 0.4, reviewerWeight: 0.3, defenseWeight: 0.3 },
        plagiarism: { thresholdPercent: 20, mustPassToDefense: true }
      }
    })
    await admin.post(`/graduation/batches/${batch.id}/stages`, {
      stages: [
        { code: 'TOPIC', name: '选题', startDate: isoDay(-45), endDate: isoDay(-1) },
        { code: 'PROPOSAL', name: '开题', startDate: isoDay(0), endDate: isoDay(30) },
        { code: 'MIDTERM', name: '中期', startDate: isoDay(31), endDate: isoDay(60) },
        { code: 'SUBMISSION', name: '成果', startDate: isoDay(61), endDate: isoDay(90) },
        { code: 'PLAGIARISM', name: '查重', startDate: isoDay(91), endDate: isoDay(100) },
        { code: 'REVIEW', name: '评阅', startDate: isoDay(101), endDate: isoDay(110) },
        { code: 'DEFENSE', name: '答辩', startDate: isoDay(111), endDate: isoDay(125) },
        { code: 'GRADE', name: '成绩', startDate: isoDay(126), endDate: isoDay(145) }
      ]
    })
    batch = { ...batch, ...(await admin.post(`/graduation/batches/${batch.id}/activate`, {})), status: 'RUNNING' }
  }

  const profile = await findStudent(admin, graduationMaterialStudent.username)
  let gdStudent = items(await admin.get('/graduation/gd-students', {
    batchId: String(batch.id), keyword: graduationMaterialStudent.username, page: 1, pageSize: 50
  })).find((item) => String(item.studentNo || '') === graduationMaterialStudent.username)

  if (!gdStudent) {
    gdStudent = await admin.post('/graduation/gd-students', {
      studentId: String(profile.id || profile.studentId),
      batchId: String(batch.id),
      remark: 'Golden material-center screenshot fixture'
    })
  }

  try {
    await admin.post(`/graduation/gd-students/${gdStudent.id}/eligibility`, {
      status: 'QUALIFIED', reason: 'Golden UI 材料中心验收独立资格准备'
    })
  } catch (error) {
    if (!/状态|已认定|无需|QUALIFIED/.test(error.message)) throw error
  }

  const students = await admin.get('/graduation/material-center/students', {
    batchId: String(batch.id), keyword: graduationMaterialStudent.username, page: 1, pageSize: 20
  })
  if (!items(students).length) {
    throw new Error('Golden graduation material-center fixture did not produce a real student completeness row')
  }

  return { batchId: String(batch.id), batchName: batch.batchName, gdStudentId: String(gdStudent.id) }
}

async function closeGraduationMaterialFixture(fixture) {
  if (!fixture?.batchId) return
  const admin = await loginApi(config.sandboxAdmin)
  try {
    await admin.post(`/graduation/batches/${fixture.batchId}/close`, {})
  } catch (error) {
    if (!/仅「进行中」批次可结束|已结束|CLOSED/.test(error.message)) throw error
  }
}

test.describe.serial('Golden rollout · materials / archive / evidence · Batch 4', () => {
  let affairsFixture
  let internshipFixture
  let graduationFixture

  test.beforeAll(async () => {
    affairsFixture = await prepareStudentAffairsArchiveFixture()
    internshipFixture = await prepareInternshipMaterialFixture()
    graduationFixture = await prepareGraduationMaterialFixture()
  })

  test.afterAll(async () => {
    await closeGraduationMaterialFixture(graduationFixture)
  })

  test('Student Affairs archive · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await page.goto(`${config.staffBaseUrl}/admin/student-affairs/archive`)

    await expect(page).toHaveURL(/\/admin\/student-affairs\/archive/)
    await expect(page.locator('.ar-list')).toBeVisible()
    const batch = page.locator('.ar-item').filter({ hasText: affairsFixture.batchName }).first()
    await expect(batch).toBeVisible()
    await batch.click()
    await expect(page.locator('.ar-flow')).toBeVisible()
    await expect(page.locator('.ar-main')).toBeVisible()
    await expect(page.locator('.ar-packages')).toBeVisible()

    await capture(page, testInfo, 'rollout-material-affairs-archive-a')
  })

  test('Internship student materials · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await setBatchStorage(page, 'internship.selectedBatchId', internshipFixture.batchId)
    await page.goto(`${config.staffBaseUrl}/admin/internship/students/${encodeURIComponent(internshipFixture.internshipId)}/materials`)

    await expect(page).toHaveURL(/\/admin\/internship\/students\/[^/]+\/materials/)
    await expect(page.locator('.ism-summary')).toBeVisible()
    await expect(page.locator('.ism-card').first()).toBeVisible()
    await expect(page.getByText(/真实版本与归档证据/)).toBeVisible()

    await capture(page, testInfo, 'rollout-material-internship-student-a')
  })

  test('Graduation material center · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await setBatchStorage(page, 'graduation.selectedBatchId', graduationFixture.batchId)
    await page.goto(`${config.staffBaseUrl}/admin/graduation/material-center?tab=students`)

    await expect(page).toHaveURL(/\/admin\/graduation\/material-center/)
    await expect(page.locator('.mc-hero')).toBeVisible()
    await expect(page.locator('.mc-summary')).toBeVisible()
    await expect(page.locator('.mc-tabs')).toBeVisible()
    await expect(page.locator('.mc-panel table')).toBeVisible()
    await expect(page.locator('.mc-panel tbody tr').first()).toBeVisible()

    await capture(page, testInfo, 'rollout-material-graduation-center-a')
  })
})