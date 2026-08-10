import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const VIEWPORT = { width: 1440, height: 1000 }
const saAdmin = config.sandboxAdmin
const counselorA = { tenant: 'sandbox-school', username: 'e2e_counselor_a', password: 'E2eTest@2026' }
const studentB = { tenant: 'sandbox-school', username: 'E2E20260002', password: 'E2eTest@2026' }

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

function runId() {
  const raw = process.env.GITHUB_RUN_ID || `${Date.now()}`
  return String(raw).replace(/\D/g, '').slice(-12) || String(Date.now()).slice(-12)
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

async function ensureLeaveCounselorAssignment() {
  const admin = await loginApi(saAdmin)
  const profiles = items(await admin.get('/students', { keyword: studentB.username, page: 1, pageSize: 50 }))
  const profile = profiles.find((item) => String(item.studentNo || item.loginName || '') === studentB.username)
  if (!profile) throw new Error(`Golden leave student ${studentB.username} not found`)
  const classId = String(profile.classId || profile.class?.id || '')
  if (!classId) throw new Error(`Golden leave student ${studentB.username} has no classId`)

  const teachers = items(await admin.get('/directory/teachers', { keyword: counselorA.username }))
  const teacher = teachers.find((item) => String(item.loginName || '') === counselorA.username)
    || teachers.find((item) => String(item.label || item.name || '').includes('辅导员A'))
  const userId = String(teacher?.value || teacher?.id || teacher?.userId || '')
  if (!userId) throw new Error(`Golden counselor ${counselorA.username} not found in teacher directory`)

  const active = items(await admin.get('/student-affairs/counselor-assignments', {
    classId, userId, status: 'ACTIVE', page: 1, pageSize: 50
  })).find((item) => String(item.userId || '') === userId && String(item.classId || '') === classId)

  if (!active) {
    await admin.post('/student-affairs/counselor-assignments', {
      classId: Number(classId),
      userId: Number(userId),
      dutyType: 'TEMP',
      effectiveFrom: isoDay(-1),
      effectiveTo: isoDay(7),
      reason: 'Golden UI 隔离截图：临时代办请假初审，不替换学校主辅导员'
    })
  }

  return { classId, userId }
}

async function prepareLeaveFixture() {
  const assignment = await ensureLeaveCounselorAssignment()
  const api = await loginApi(studentB)
  const marker = runId()
  const applied = await api.post('/portal/affairs/leave', {
    leaveType: 'PERSONAL',
    startTime: isoDay(40),
    endTime: isoDay(41),
    reason: `Golden UI 连续审批验收 ${marker} · 学生返乡办理家庭事务`
  })
  return { leaveId: String(applied.id || applied.leaveId || ''), marker, assignment }
}

async function prepareGraduationOpsFixture() {
  const admin = await loginApi(config.sandboxAdmin)
  const marker = runId()
  const batchNo = `PW-GOLD-OPS-${marker}`
  let batch = items(await admin.get('/graduation/batches', { keyword: batchNo, page: 1, pageSize: 50 }))
    .find((item) => item.batchNo === batchNo)

  if (!batch) {
    const year = new Date().getUTCFullYear()
    batch = await admin.post('/graduation/batches', {
      batchName: `Golden 毕设学生台账 ${marker}`,
      batchNo,
      academicYear: academicYear(),
      gradeYear: `${year + 1}届`,
      plannedCount: 1,
      remark: 'Golden business ops screenshot only; isolated E2E database'
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

  const profiles = items(await admin.get('/students', { keyword: config.student.username, page: 1, pageSize: 50 }))
  const profile = profiles.find((item) => String(item.studentNo || item.loginName || '') === config.student.username)
  if (!profile) throw new Error(`Golden ops student ${config.student.username} not found`)

  let gdStudent = items(await admin.get('/graduation/gd-students', {
    batchId: String(batch.id), keyword: config.student.username, page: 1, pageSize: 50
  })).find((item) => String(item.studentNo || '') === config.student.username)

  if (!gdStudent) {
    gdStudent = await admin.post('/graduation/gd-students', {
      studentId: String(profile.id || profile.studentId),
      batchId: String(batch.id),
      remark: 'Golden business ops screenshot fixture'
    })
  }

  try {
    await admin.post(`/graduation/gd-students/${gdStudent.id}/eligibility`, {
      status: 'QUALIFIED', reason: 'Golden UI 台账验收独立资格准备'
    })
  } catch (error) {
    if (!/状态|已认定|无需|QUALIFIED/.test(error.message)) throw error
  }

  return { batchId: String(batch.id), batchName: batch.batchName, gdStudentId: String(gdStudent.id) }
}

test.describe.serial('Golden rollout · high-frequency operations · Batch 2', () => {
  let leaveFixture
  let internshipFixture
  let graduationFixture

  test.beforeAll(async () => {
    leaveFixture = await prepareLeaveFixture()
    internshipFixture = await loadInternshipFixture()
    graduationFixture = await prepareGraduationOpsFixture()
  })

  test('Student Affairs leave approval · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(counselorA)
    await page.goto(`${config.staffBaseUrl}/admin/student-affairs/leave`)

    await expect(page).toHaveURL(/\/admin\/student-affairs\/leave/)
    await expect(page.locator('.lv-list')).toBeVisible()
    const target = page.locator('.lv-item').filter({ hasText: /E2E20260002|Golden UI/ }).first()
    const first = (await target.count()) ? target : page.locator('.lv-item').first()
    await expect(first).toBeVisible()
    await first.click()
    await expect(page.locator('.lv-main__body')).toBeVisible()
    await expect(page.locator('.lv-foot')).toBeVisible()
    expect(leaveFixture.leaveId).not.toBe('')

    await capture(page, testInfo, 'rollout-ops-leave-a')
  })

  test('Internship student ledger · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await setBatchStorage(page, 'internship.selectedBatchId', internshipFixture.batchId)
    await page.goto(`${config.staffBaseUrl}/admin/internship/students?batchId=${encodeURIComponent(internshipFixture.batchId)}`)

    await expect(page).toHaveURL(/\/admin\/internship\/students/)
    await expect(page.locator('.isl-viewnav')).toBeVisible()
    await expect(page.locator('.dt')).toBeVisible()
    await expect(page.locator('.dt__td').first()).toBeVisible()

    await capture(page, testInfo, 'rollout-ops-internship-students-a')
  })

  test('Graduation student ledger · Screenshot A', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await new StaffLoginPage(page, config.staffBaseUrl).login(config.sandboxAdmin)
    await setBatchStorage(page, 'graduation.selectedBatchId', graduationFixture.batchId)
    await page.goto(`${config.staffBaseUrl}/admin/graduation/students?batchId=${encodeURIComponent(graduationFixture.batchId)}&panel=roster`)

    await expect(page).toHaveURL(/\/admin\/graduation\/students/)
    await expect(page.locator('.mp-tabs')).toBeVisible()
    await expect(page.locator('.dt')).toBeVisible()
    await expect(page.locator('.dt__td').first()).toBeVisible()

    await capture(page, testInfo, 'rollout-ops-graduation-students-a')
  })
})
