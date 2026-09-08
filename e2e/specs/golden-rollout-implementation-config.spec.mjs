import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { loadInternshipFixture } from '../lib/internship-fixture.mjs'
import { items, loginApi } from '../lib/api-fixture.mjs'
import { openGoldenStaffPage } from '../lib/golden-staff-page.mjs'

const VIEWPORT = { width: 1440, height: 1000 }
const counselorLogin = 'e2e_counselor_a'
const responsibilityStudentNo = 'E2E20260002'

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

async function findStudent(admin, studentNo) {
  const rows = items(await admin.get('/students', { keyword: studentNo, page: 1, pageSize: 50 }))
  const student = rows.find((item) => String(item.studentNo || item.loginName || '') === studentNo)
  if (!student) throw new Error(`Golden implementation student ${studentNo} not found`)
  return student
}

async function findSystemUser(admin, loginName) {
  for (let page = 1; page <= 20; page += 1) {
    const data = await admin.get('/system/users', { page, page_size: 50 })
    const rows = items(data)
    const user = rows.find((item) => String(item.loginName || item.userNo || '') === loginName)
    if (user) return user
    const total = Number(data?.total || 0)
    if (!rows.length || page * 50 >= total) break
  }
  throw new Error(`Golden implementation user ${loginName} not found`)
}

async function prepareCounselorResponsibilityFixture(admin) {
  const student = await findStudent(admin, responsibilityStudentNo)
  const classId = String(student.classId || student.class?.id || '')
  if (!classId) throw new Error(`Golden implementation student ${responsibilityStudentNo} has no classId`)

  const counselor = await findSystemUser(admin, counselorLogin)
  const userId = String(counselor.id || counselor.userId || '')
  if (!userId) throw new Error(`Golden implementation counselor ${counselorLogin} has no User.id`)

  const active = items(await admin.get('/student-affairs/counselor-assignments', {
    classId, userId, status: 'ACTIVE', page: 1, pageSize: 50
  })).find((item) => String(item.classId || '') === classId && String(item.userId || '') === userId)

  if (!active) {
    await admin.post('/student-affairs/counselor-assignments', {
      classId: Number(classId),
      userId: Number(userId),
      dutyType: 'TEMP',
      effectiveFrom: isoDay(-1),
      effectiveTo: isoDay(7),
      reason: 'Golden UI 实施配置截图：临时代班责任关系，不替换学校主辅导员'
    })
  }

  const ledger = items(await admin.get('/student-affairs/counselor-ledger', { page: 1, pageSize: 50 }))
  if (!ledger.some((item) => String(item.userId || '') === userId)) {
    throw new Error('Golden counselor responsibility fixture did not appear in the real ledger')
  }

  return { classId, userId, loginName: counselorLogin }
}

async function prepareGraduationDraftBatch(admin) {
  const marker = runId()
  const batchNo = `PW-GOLD-CONFIG-${marker}`
  let batch = items(await admin.get('/graduation/batches', { keyword: batchNo, page: 1, pageSize: 50 }))
    .find((item) => item.batchNo === batchNo)

  if (!batch) {
    const year = new Date().getUTCFullYear()
    batch = await admin.post('/graduation/batches', {
      batchName: `Golden 毕设实施配置 ${marker}`,
      batchNo,
      academicYear: academicYear(),
      gradeYear: `${year + 1}届`,
      plannedCount: 120,
      remark: 'Golden implementation/config screenshot only; isolated E2E database'
    })
  }

  if (String(batch.status || '').toUpperCase() !== 'DRAFT') {
    throw new Error(`Golden implementation batch must remain DRAFT, got ${batch.status || 'UNKNOWN'}`)
  }
  return { batchId: String(batch.id), batchName: batch.batchName, batchNo }
}

test.describe.serial('Golden rollout · implementation / configuration · Batch 5', () => {
  let adminApi
  let counselorFixture
  let internshipFixture
  let graduationFixture

  test.beforeAll(async () => {
    // This suite is visual evidence, not an authentication load test. One real admin
    // login is reused so the official login throttle remains fully enforced.
    adminApi = await loginApi(config.sandboxAdmin)
    counselorFixture = await prepareCounselorResponsibilityFixture(adminApi)
    internshipFixture = await loadInternshipFixture()
    graduationFixture = await prepareGraduationDraftBatch(adminApi)
  })

  test('Student Affairs counselor responsibility · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openGoldenStaffPage(page, '/admin/student-affairs/counselor-assignments')

    await expect(page).toHaveURL(/\/admin\/student-affairs\/counselor-assignments/)
    await expect(page.getByRole('heading', { name: '辅导员责任台账', exact: true })).toBeVisible()
    await expect(page.getByRole('tablist', { name: '责任台账视图' })).toBeVisible()
    await expect(page.locator('.dt__td').first()).toBeVisible()
    expect(counselorFixture.userId).not.toBe('')
    await expect(page.getByRole('button', { name: '分配责任', exact: true })).toBeEnabled()
    await expect(page.locator('.responsibility-note')).toContainText('历史记录保留')

    await capture(page, testInfo, 'rollout-config-affairs-counselor-b')
  })

  test('Internship batch configuration · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openGoldenStaffPage(page, `/admin/internship/batches?panel=list&batchId=${encodeURIComponent(internshipFixture.batchId)}&keyword=${encodeURIComponent(internshipFixture.batchName)}`)

    await expect(page).toHaveURL(/\/admin\/internship\/batches/)
    await expect(page.locator('.dt')).toBeVisible()
    const target = page.locator('.dt__tr').filter({ hasText: internshipFixture.batchName }).first()
    await expect(target).toBeVisible()

    await expect(page.getByRole('region', { name: '实习批次列表' })).toBeVisible()
    const detailLink = target.getByRole('link', { name: internshipFixture.batchName, exact: true })
    await expect(detailLink).toBeVisible()
    await expect(detailLink).toHaveAttribute('href', /\/admin\/internship\/batches\//)
    const box = await page.locator('.ibl-workspace').boundingBox()
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(VIEWPORT.width)

    await capture(page, testInfo, 'rollout-config-internship-batches-b')
  })

  test('Graduation batch implementation · Screenshot B', async ({ page }, testInfo) => {
    await page.setViewportSize(VIEWPORT)
    await openGoldenStaffPage(page, '/admin/graduation/batches?panel=list')

    await expect(page).toHaveURL(/\/admin\/graduation\/batches/)
    await expect(page.locator('.dt')).toBeVisible()
    const target = page.locator('.dt__tr').filter({ hasText: graduationFixture.batchName }).first()
    await expect(target).toBeVisible()

    const graduationContract = await page.evaluate(() => {
      const root = document.querySelector('.mps:has(.mp-actions):has(> .mp-stack > .af)')
      if (!root) return null
      const header = root.querySelector(':scope > .mps__head')
      const filter = root.querySelector(':scope > .mp-stack > .af')
      const table = root.querySelector(':scope > .mp-stack > .dt')
      if (!header || !filter || !table) return null
      return {
        headerRadius: getComputedStyle(header).borderRadius,
        filterShadow: getComputedStyle(filter).boxShadow,
        tableRadius: getComputedStyle(table).borderRadius
      }
    })
    expect(graduationContract).not.toBeNull()
    expect(graduationContract.headerRadius).toBe('18px')
    expect(graduationContract.filterShadow).toBe('none')
    expect(graduationContract.tableRadius).toBe('16px')

    await capture(page, testInfo, 'rollout-config-graduation-batches-b')
  })
})
